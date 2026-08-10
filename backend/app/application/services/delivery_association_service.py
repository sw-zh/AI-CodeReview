"""Auditable links between source-derived delivery items, PRs, Git ranges and verification tasks."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.core.config import get_settings
from app.domain.enums import ExternalResourceType, ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.github_source_client import GitHubSourceClient
from app.infrastructure.persistence.models import (
    DeliveryChangeLink,
    DeliveryItem,
    DeliveryItemSourceLink,
    ExternalConnection,
    ExternalResource,
    ExternalResourceRevision,
    GitSnapshot,
    PublishedRecord,
    SourceRevision,
    VerificationCycle,
    VerificationTask,
)


def _item_for_project(session: Session, *, project_id: UUID, delivery_item_id: UUID) -> DeliveryItem:
    item = session.get(DeliveryItem, delivery_item_id)
    if item is None or item.project_id != project_id:
        raise DomainError("RESOURCE_NOT_FOUND", "研发事项不存在")
    return item


def bind_task_delivery_item(
    session: Session,
    *,
    project_id: UUID,
    task_id: UUID,
    delivery_item_id: UUID,
    actor_id: UUID,
    correlation_id: str,
) -> VerificationTask:
    task = session.get(VerificationTask, task_id)
    if task is None or task.project_id != project_id:
        raise DomainError("RESOURCE_NOT_FOUND", "核验任务不存在")
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    item = _item_for_project(session, project_id=project_id, delivery_item_id=delivery_item_id)
    if task.delivery_item_id != item.id and session.query(PublishedRecord).filter_by(task_id=task.id).first() is not None:
        raise DomainError("STATE_CONFLICT", "已固化正式记录的历史任务不可重新归属研发事项")
    task.delivery_item_id = item.id
    task.version += 1
    append_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        aggregate_type="VerificationTask",
        aggregate_id=task.id,
        action="TASK_DELIVERY_ITEM_BOUND",
        correlation_id=correlation_id,
        after_version=task.version,
        payload={"deliveryItemId": str(item.id)},
    )
    return task


def _pr_for_project(session: Session, *, project_id: UUID, pull_request_resource_id: UUID) -> ExternalResource:
    resource = session.get(ExternalResource, pull_request_resource_id)
    connection = session.get(ExternalConnection, resource.connection_id) if resource else None
    if resource is None or connection is None or connection.project_id != project_id or resource.resource_type != ExternalResourceType.PULL_REQUEST.value:
        raise DomainError("INPUT_INVALID", "关联目标必须是当前项目已同步的 GitHub PR")
    return resource


def _git_snapshot_for_item(session: Session, *, item: DeliveryItem, git_snapshot_id: UUID) -> GitSnapshot:
    snapshot = session.get(GitSnapshot, git_snapshot_id)
    cycle = session.get(VerificationCycle, snapshot.cycle_id) if snapshot else None
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or task.project_id != item.project_id:
        raise DomainError("INPUT_INVALID", "Git 范围不存在或不属于当前项目")
    if task.delivery_item_id != item.id:
        raise DomainError("STATE_CONFLICT", "Git 范围所属核验任务尚未绑定当前研发事项")
    return snapshot


def _existing_link(
    session: Session,
    *,
    delivery_item_id: UUID,
    pull_request_resource_id: UUID | None,
    git_snapshot_id: UUID | None,
) -> DeliveryChangeLink | None:
    query = session.query(DeliveryChangeLink).filter_by(delivery_item_id=delivery_item_id)
    if pull_request_resource_id is not None:
        return query.filter_by(pull_request_resource_id=pull_request_resource_id).one_or_none()
    return query.filter_by(git_snapshot_id=git_snapshot_id).one_or_none()


def _upsert_link(
    session: Session,
    *,
    item: DeliveryItem,
    pull_request_resource_id: UUID | None,
    git_snapshot_id: UUID | None,
    link_status: str,
    link_source: str,
    confidence: float | None,
    reason: str,
    actor_id: UUID,
) -> tuple[DeliveryChangeLink, bool]:
    existing = _existing_link(
        session,
        delivery_item_id=item.id,
        pull_request_resource_id=pull_request_resource_id,
        git_snapshot_id=git_snapshot_id,
    )
    is_confirmed = link_status == "CONFIRMED"
    if existing is None:
        link = DeliveryChangeLink(
            delivery_item_id=item.id,
            pull_request_resource_id=pull_request_resource_id,
            git_snapshot_id=git_snapshot_id,
            link_status=link_status,
            link_source=link_source,
            confidence=confidence,
            reason=reason,
            created_by=actor_id,
            confirmed_by=actor_id if is_confirmed else None,
            confirmed_at=datetime.now(UTC) if is_confirmed else None,
        )
        session.add(link)
        session.flush()
        return link, True
    if existing.link_status != "CONFIRMED" and is_confirmed:
        existing.link_status = "CONFIRMED"
        existing.link_source = link_source
        existing.confidence = confidence
        existing.reason = reason
        existing.confirmed_by = actor_id
        existing.confirmed_at = datetime.now(UTC)
        return existing, True
    return existing, False


def confirm_change_link(
    session: Session,
    *,
    project_id: UUID,
    delivery_item_id: UUID,
    pull_request_resource_id: UUID | None,
    git_snapshot_id: UUID | None,
    reason: str,
    actor_id: UUID,
    correlation_id: str,
) -> DeliveryChangeLink:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    item = _item_for_project(session, project_id=project_id, delivery_item_id=delivery_item_id)
    if (pull_request_resource_id is None) == (git_snapshot_id is None):
        raise DomainError("INPUT_INVALID", "一次只能确认一个 PR 或 Git 范围关联")
    if pull_request_resource_id is not None:
        _pr_for_project(session, project_id=project_id, pull_request_resource_id=pull_request_resource_id)
    if git_snapshot_id is not None:
        _git_snapshot_for_item(session, item=item, git_snapshot_id=git_snapshot_id)
    link, changed = _upsert_link(
        session,
        item=item,
        pull_request_resource_id=pull_request_resource_id,
        git_snapshot_id=git_snapshot_id,
        link_status="CONFIRMED",
        link_source="USER",
        confidence=1.0,
        reason=reason.strip(),
        actor_id=actor_id,
    )
    if changed:
        append_audit_event(
            session,
            project_id=project_id,
            actor_id=actor_id,
            aggregate_type="DeliveryChangeLink",
            aggregate_id=link.id,
            action="DELIVERY_CHANGE_LINK_CONFIRMED",
            correlation_id=correlation_id,
            payload={"deliveryItemId": str(item.id), "pullRequestResourceId": str(pull_request_resource_id) if pull_request_resource_id else None, "gitSnapshotId": str(git_snapshot_id) if git_snapshot_id else None},
        )
    return link


def _primary_issue_resource(session: Session, *, item: DeliveryItem) -> tuple[ExternalResource, ExternalConnection] | None:
    link = (
        session.query(DeliveryItemSourceLink)
        .filter_by(delivery_item_id=item.id, link_role="PRIMARY")
        .filter(DeliveryItemSourceLink.external_resource_revision_id.is_not(None))
        .order_by(DeliveryItemSourceLink.created_at.desc())
        .first()
    )
    revision = session.get(ExternalResourceRevision, link.external_resource_revision_id) if link else None
    resource = session.get(ExternalResource, revision.resource_id) if revision else None
    connection = session.get(ExternalConnection, resource.connection_id) if resource else None
    if resource is None or connection is None or resource.resource_type != ExternalResourceType.ISSUE.value:
        return None
    return resource, connection


def _timeline_pr_events(events: list[dict]) -> list[tuple[str, str, str]]:
    relations: list[tuple[str, str, str]] = []
    for event in events:
        source = event.get("source") if isinstance(event, dict) else None
        issue = source.get("issue") if isinstance(source, dict) else None
        if not isinstance(issue, dict) or not isinstance(issue.get("pull_request"), dict):
            continue
        number = issue.get("number")
        if not isinstance(number, int):
            continue
        event_name = str(event.get("event") or "")
        if event_name == "cross-referenced":
            relations.append((str(number), "CONFIRMED", "GitHub Issue 时间线记录该 PR 对此事项的交叉引用"))
    return relations


def discover_platform_links(
    session: Session,
    *,
    project_id: UUID,
    delivery_item_id: UUID,
    actor_id: UUID,
    correlation_id: str,
) -> dict:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    item = _item_for_project(session, project_id=project_id, delivery_item_id=delivery_item_id)
    primary = _primary_issue_resource(session, item=item)
    if primary is None:
        raise DomainError("STATE_CONFLICT", "当前研发事项没有可用于发现 PR 关联的 GitHub Issue 来源")
    issue, connection = primary
    events = GitHubSourceClient(
        repository_slug=connection.repository_slug,
        api_base_url=connection.api_base_url,
        secret_ref=connection.secret_ref,
        settings=get_settings(),
    ).fetch_issue_timeline(issue.external_key)
    changed_count = 0
    skipped_count = 0
    for pr_number, link_status, reason in _timeline_pr_events(events):
        pr_resource = session.query(ExternalResource).filter_by(
            connection_id=connection.id,
            resource_type=ExternalResourceType.PULL_REQUEST.value,
            external_key=pr_number,
        ).one_or_none()
        if pr_resource is None:
            skipped_count += 1
            continue
        _, changed = _upsert_link(
            session,
            item=item,
            pull_request_resource_id=pr_resource.id,
            git_snapshot_id=None,
            link_status=link_status,
            link_source="PLATFORM",
            confidence=1.0 if link_status == "CONFIRMED" else 0.7,
            reason=reason,
            actor_id=actor_id,
        )
        changed_count += int(changed)
    append_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        aggregate_type="DeliveryItem",
        aggregate_id=item.id,
        action="DELIVERY_PLATFORM_LINKS_DISCOVERED",
        correlation_id=correlation_id,
        payload={"changedCount": changed_count, "skippedCount": skipped_count},
    )
    return {"changedCount": changed_count, "skippedCount": skipped_count}


def list_change_links(session: Session, *, project_id: UUID, delivery_item_id: UUID, actor_id: UUID) -> list[dict]:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    _item_for_project(session, project_id=project_id, delivery_item_id=delivery_item_id)
    links = session.query(DeliveryChangeLink).filter_by(delivery_item_id=delivery_item_id).order_by(DeliveryChangeLink.created_at).all()
    result: list[dict] = []
    for link in links:
        if link.pull_request_resource_id is not None:
            resource = session.get(ExternalResource, link.pull_request_resource_id)
            revision = (
                session.query(ExternalResourceRevision)
                .filter_by(resource_id=resource.id)
                .order_by(ExternalResourceRevision.revision_no.desc())
                .first()
                if resource
                else None
            )
            target_kind = "PULL_REQUEST"
            target_id = link.pull_request_resource_id
            target_label = revision.title if revision else "已删除的 PR 来源"
            target_url = revision.web_url if revision else None
        else:
            snapshot = session.get(GitSnapshot, link.git_snapshot_id)
            target_kind = "GIT_SNAPSHOT"
            target_id = link.git_snapshot_id
            target_label = f"{snapshot.base_sha[:12]}..{snapshot.target_sha[:12]}" if snapshot else "已删除的 Git 范围"
            target_url = None
        result.append(
            {
                "id": link.id,
                "delivery_item_id": link.delivery_item_id,
                "target_kind": target_kind,
                "target_id": target_id,
                "target_label": target_label,
                "target_url": target_url,
                "link_status": link.link_status,
                "link_source": link.link_source,
                "confidence": link.confidence,
                "reason": link.reason,
                "confirmed_at": link.confirmed_at,
            }
        )
    return result


def link_document_source(
    session: Session,
    *,
    project_id: UUID,
    delivery_item_id: UUID,
    source_revision_id: UUID,
    link_role: str,
    actor_id: UUID,
    correlation_id: str,
) -> DeliveryItemSourceLink:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    item = _item_for_project(session, project_id=project_id, delivery_item_id=delivery_item_id)
    source = session.get(SourceRevision, source_revision_id)
    if source is None or source.project_id != project_id or source.processing_status != "READY":
        raise DomainError("INPUT_INVALID", "资料版本不存在、不属于当前项目或尚未完成处理")
    existing = session.query(DeliveryItemSourceLink).filter_by(
        delivery_item_id=item.id,
        source_revision_id=source.id,
        link_role=link_role,
    ).one_or_none()
    if existing is not None:
        return existing
    link = DeliveryItemSourceLink(
        delivery_item_id=item.id,
        source_revision_id=source.id,
        link_role=link_role,
        created_by=actor_id,
    )
    session.add(link)
    session.flush()
    append_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        aggregate_type="DeliveryItemSourceLink",
        aggregate_id=link.id,
        action="DELIVERY_ITEM_DOCUMENT_SOURCE_LINKED",
        correlation_id=correlation_id,
        payload={"deliveryItemId": str(item.id), "sourceRevisionId": str(source.id), "linkRole": link_role},
    )
    return link


def list_item_source_links(session: Session, *, project_id: UUID, delivery_item_id: UUID, actor_id: UUID) -> list[dict]:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    _item_for_project(session, project_id=project_id, delivery_item_id=delivery_item_id)
    links = session.query(DeliveryItemSourceLink).filter_by(delivery_item_id=delivery_item_id).order_by(DeliveryItemSourceLink.created_at).all()
    result: list[dict] = []
    for link in links:
        if link.source_revision_id is not None:
            source = session.get(SourceRevision, link.source_revision_id)
            result.append(
                {
                    "id": link.id,
                    "delivery_item_id": link.delivery_item_id,
                    "source_kind": "DOCUMENT",
                    "source_id": link.source_revision_id,
                    "source_label": f"{source.logical_name} r{source.revision_no}" if source else "已删除的资料版本",
                    "link_role": link.link_role,
                }
            )
        else:
            revision = session.get(ExternalResourceRevision, link.external_resource_revision_id)
            result.append(
                {
                    "id": link.id,
                    "delivery_item_id": link.delivery_item_id,
                    "source_kind": "EXTERNAL_RESOURCE",
                    "source_id": link.external_resource_revision_id,
                    "source_label": revision.title if revision else "已删除的外部来源版本",
                    "link_role": link.link_role,
                }
            )
    return result
