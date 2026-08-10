"""Project-source connection, GitHub synchronization and source-derived delivery item services."""

import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.core.config import get_settings
from app.domain.enums import (
    DeliveryPlanningStatus,
    DeliveryVerificationStatus,
    ExternalConnectionProvider,
    ExternalResourceType,
    ProjectRole,
    SourceSyncStatus,
)
from app.domain.errors import DomainError
from app.infrastructure.github_source_client import GitHubSourceClient
from app.infrastructure.persistence.models import (
    DeliveryItem,
    DeliveryItemSourceLink,
    ExternalConnection,
    ExternalResource,
    ExternalResourceRevision,
    SourceSyncRun,
)


_GITHUB_API_BASE_URL = "https://api.github.com"
_GITHUB_REPOSITORY_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SECRET_REF = re.compile(r"^[A-Z][A-Z0-9_]{2,159}$")


def _canonical_hash(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _normalize_repository_slug(value: str) -> str:
    slug = value.strip().strip("/")
    if not _GITHUB_REPOSITORY_SLUG.fullmatch(slug):
        raise DomainError("INPUT_INVALID", "GitHub 仓库标识必须是 owner/repository")
    return slug


def _normalize_secret_ref(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    secret_ref = value.strip()
    if not _SECRET_REF.fullmatch(secret_ref):
        raise DomainError("INPUT_INVALID", "密钥引用必须是服务端环境变量名称")
    return secret_ref


def _parse_source_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _planning_status(*, state: object, state_reason: object) -> str:
    if state == "closed" and state_reason == "not_planned":
        return DeliveryPlanningStatus.CANCELLED.value
    if state == "closed":
        return DeliveryPlanningStatus.DECLARED_DONE.value
    return DeliveryPlanningStatus.OPEN.value


def _normalize_resource_payload(item: dict, *, resource_type: str) -> dict:
    milestone = item.get("milestone")
    milestone_key = str(milestone.get("number")) if isinstance(milestone, dict) and milestone.get("number") is not None else None
    return {
        "resourceType": resource_type,
        "externalKey": str(item.get("number")),
        "title": str(item.get("title") or ""),
        "body": str(item.get("body") or item.get("description") or ""),
        "state": str(item.get("state") or "UNKNOWN"),
        "stateReason": str(item.get("state_reason") or ""),
        "webUrl": str(item.get("html_url") or ""),
        "milestoneKey": milestone_key,
        "sourceUpdatedAt": str(item.get("updated_at") or ""),
        "labels": [str(label.get("name")) for label in item.get("labels", []) if isinstance(label, dict) and label.get("name")],
    }


def create_connection(
    session: Session,
    *,
    project_id: UUID,
    actor_id: UUID,
    correlation_id: str,
    provider: str,
    name: str,
    repository_slug: str,
    secret_ref: str | None,
) -> ExternalConnection:
    require_project_role(session, project_id, actor_id, {ProjectRole.ADMIN})
    if provider != ExternalConnectionProvider.GITHUB.value:
        raise DomainError("INPUT_INVALID", "当前仅支持 GitHub 只读来源")
    normalized_name = name.strip()
    if not normalized_name:
        raise DomainError("INPUT_INVALID", "来源连接名称不能为空")
    slug = _normalize_repository_slug(repository_slug)
    normalized_secret_ref = _normalize_secret_ref(secret_ref)
    if session.query(ExternalConnection).filter_by(
        project_id=project_id,
        provider=provider,
        repository_slug=slug,
    ).one_or_none() is not None:
        raise DomainError("STATE_CONFLICT", "该项目已登记此 GitHub 仓库来源")
    connection = ExternalConnection(
        project_id=project_id,
        provider=provider,
        name=normalized_name,
        repository_slug=slug,
        api_base_url=_GITHUB_API_BASE_URL,
        secret_ref=normalized_secret_ref,
        created_by=actor_id,
    )
    session.add(connection)
    session.flush()
    append_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        aggregate_type="ExternalConnection",
        aggregate_id=connection.id,
        action="EXTERNAL_CONNECTION_CREATED",
        correlation_id=correlation_id,
        payload={"provider": connection.provider, "repositorySlug": connection.repository_slug},
    )
    return connection


def list_connections(session: Session, *, project_id: UUID, actor_id: UUID) -> list[ExternalConnection]:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    return session.query(ExternalConnection).filter_by(project_id=project_id).order_by(ExternalConnection.created_at).all()


def _connection_for_project(session: Session, *, project_id: UUID, connection_id: UUID) -> ExternalConnection:
    connection = session.get(ExternalConnection, connection_id)
    if connection is None or connection.project_id != project_id:
        raise DomainError("RESOURCE_NOT_FOUND", "外部来源连接不存在")
    if not connection.is_active:
        raise DomainError("STATE_CONFLICT", "外部来源连接已停用")
    return connection


def _upsert_resource(
    session: Session,
    *,
    connection: ExternalConnection,
    source: dict,
    resource_type: str,
) -> tuple[ExternalResource, ExternalResourceRevision, bool]:
    normalized = _normalize_resource_payload(source, resource_type=resource_type)
    external_key = normalized["externalKey"]
    if external_key in {"", "None"}:
        raise DomainError("SOURCE_RESPONSE_INVALID", "GitHub 资源缺少编号")
    resource = session.query(ExternalResource).filter_by(
        connection_id=connection.id,
        resource_type=resource_type,
        external_key=external_key,
    ).one_or_none()
    if resource is None:
        resource = ExternalResource(
            connection_id=connection.id,
            resource_type=resource_type,
            external_key=external_key,
            logical_key=f"github:{connection.repository_slug}:{resource_type.lower()}:{external_key}",
        )
        session.add(resource)
        session.flush()
    content_hash = _canonical_hash(normalized)
    latest = session.query(ExternalResourceRevision).filter_by(resource_id=resource.id).order_by(ExternalResourceRevision.revision_no.desc()).first()
    if latest is not None and latest.content_hash == content_hash:
        return resource, latest, False
    revision = ExternalResourceRevision(
        resource_id=resource.id,
        revision_no=(latest.revision_no if latest else 0) + 1,
        content_hash=content_hash,
        title=normalized["title"],
        body=normalized["body"],
        state=normalized["state"],
        web_url=normalized["webUrl"],
        milestone_key=normalized["milestoneKey"],
        source_updated_at=_parse_source_time(normalized["sourceUpdatedAt"]),
        payload=normalized,
    )
    session.add(revision)
    session.flush()
    return resource, revision, True


def _project_delivery_item(
    session: Session,
    *,
    project_id: UUID,
    resource: ExternalResource,
    revision: ExternalResourceRevision,
    source: dict,
    actor_id: UUID,
    changed: bool,
) -> bool:
    item = session.query(DeliveryItem).filter_by(project_id=project_id, external_key=resource.logical_key).one_or_none()
    created = item is None
    if item is None:
        item = DeliveryItem(
            project_id=project_id,
            external_resource_id=resource.id,
            external_key=resource.logical_key,
            title=revision.title,
            planning_status=_planning_status(state=source.get("state"), state_reason=source.get("state_reason")),
            verification_status=DeliveryVerificationStatus.NOT_ASSESSED.value,
            source_updated_at=revision.source_updated_at,
        )
        session.add(item)
        session.flush()
    else:
        item.external_resource_id = resource.id
        item.title = revision.title
        item.planning_status = _planning_status(state=source.get("state"), state_reason=source.get("state_reason"))
        item.source_updated_at = revision.source_updated_at
    if created or changed:
        session.add(
            DeliveryItemSourceLink(
                delivery_item_id=item.id,
                external_resource_revision_id=revision.id,
                link_role="PRIMARY",
                created_by=actor_id,
            )
        )
    return created or changed


def sync_connection(
    session: Session,
    *,
    project_id: UUID,
    connection_id: UUID,
    actor_id: UUID,
    correlation_id: str,
) -> SourceSyncRun:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    connection = _connection_for_project(session, project_id=project_id, connection_id=connection_id)
    sync = SourceSyncRun(connection_id=connection.id, status=SourceSyncStatus.RUNNING.value)
    session.add(sync)
    session.flush()
    try:
        payload = GitHubSourceClient(
            repository_slug=connection.repository_slug,
            api_base_url=connection.api_base_url,
            secret_ref=connection.secret_ref,
            settings=get_settings(),
        ).fetch()
        fetched_count = 0
        changed_count = 0
        for source in payload.issues:
            resource_type = ExternalResourceType.PULL_REQUEST.value if isinstance(source.get("pull_request"), dict) else ExternalResourceType.ISSUE.value
            resource, revision, changed = _upsert_resource(session, connection=connection, source=source, resource_type=resource_type)
            fetched_count += 1
            changed_count += int(changed)
            if resource_type == ExternalResourceType.ISSUE.value:
                changed_count += int(_project_delivery_item(session, project_id=project_id, resource=resource, revision=revision, source=source, actor_id=actor_id, changed=changed))
        for source in payload.milestones:
            _, _, changed = _upsert_resource(session, connection=connection, source=source, resource_type=ExternalResourceType.MILESTONE.value)
            fetched_count += 1
            changed_count += int(changed)
        sync.status = SourceSyncStatus.PARTIALLY_SUCCEEDED.value if payload.truncated else SourceSyncStatus.SUCCEEDED.value
        sync.fetched_count = fetched_count
        sync.changed_count = changed_count
    except DomainError as exc:
        sync.status = SourceSyncStatus.FAILED.value
        sync.error_code = exc.code
        sync.error_message = exc.message
    sync.finished_at = datetime.now(UTC)
    append_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        aggregate_type="SourceSyncRun",
        aggregate_id=sync.id,
        action="SOURCE_SYNC_COMPLETED" if sync.status != SourceSyncStatus.FAILED.value else "SOURCE_SYNC_FAILED",
        correlation_id=correlation_id,
        payload={"connectionId": str(connection.id), "status": sync.status, "fetchedCount": sync.fetched_count, "changedCount": sync.changed_count, "errorCode": sync.error_code},
    )
    return sync


def list_sync_runs(session: Session, *, project_id: UUID, actor_id: UUID, limit: int = 50) -> list[SourceSyncRun]:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    return (
        session.query(SourceSyncRun)
        .join(ExternalConnection, ExternalConnection.id == SourceSyncRun.connection_id)
        .filter(ExternalConnection.project_id == project_id)
        .order_by(SourceSyncRun.started_at.desc())
        .limit(limit)
        .all()
    )


def list_delivery_items(session: Session, *, project_id: UUID, actor_id: UUID, limit: int = 100) -> list[dict]:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    items = (
        session.query(DeliveryItem)
        .filter_by(project_id=project_id)
        .order_by(DeliveryItem.source_updated_at.desc().nullslast(), DeliveryItem.created_at.desc())
        .limit(limit)
        .all()
    )
    result: list[dict] = []
    for item in items:
        resource = session.get(ExternalResource, item.external_resource_id)
        connection = session.get(ExternalConnection, resource.connection_id) if resource else None
        latest = (
            session.query(ExternalResourceRevision)
            .filter_by(resource_id=resource.id)
            .order_by(ExternalResourceRevision.revision_no.desc())
            .first()
            if resource
            else None
        )
        result.append(
            {
                "id": item.id,
                "project_id": item.project_id,
                "external_key": item.external_key,
                "title": item.title,
                "planning_status": item.planning_status,
                "verification_status": item.verification_status,
                "source_updated_at": item.source_updated_at,
                "provider": connection.provider if connection else "UNKNOWN",
                "repository_slug": connection.repository_slug if connection else "",
                "web_url": latest.web_url if latest else "",
                "milestone_key": latest.milestone_key if latest else None,
                "resource_revision": latest.revision_no if latest else 0,
            }
        )
    return result
