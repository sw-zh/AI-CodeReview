from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep, correlation_id, idempotency_key
from app.api.schemas import (
    DeliveryChangeLinkCreateRequest,
    DeliveryChangeLinkResponse,
    DeliveryItemDocumentSourceLinkCreateRequest,
    DeliveryItemSourceLinkResponse,
    PlatformLinkDiscoveryResponse,
)
from app.application.services.delivery_association_service import (
    confirm_change_link,
    discover_platform_links,
    link_document_source,
    list_change_links,
    list_item_source_links,
)
from app.domain.errors import DomainError


router = APIRouter(prefix="/projects/{project_id}/delivery-items")


def _failure(exc: DomainError) -> HTTPException:
    if exc.code == "AUTH_FORBIDDEN":
        status_code = status.HTTP_403_FORBIDDEN
    elif exc.code == "RESOURCE_NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code in {"INPUT_INVALID", "SOURCE_RESPONSE_INVALID"}:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message})


@router.get("/{delivery_item_id}/change-links", response_model=list[DeliveryChangeLinkResponse])
def get_change_links(project_id: UUID, delivery_item_id: UUID, session: SessionDep, user: CurrentUserDep) -> list[DeliveryChangeLinkResponse]:
    try:
        return [
            DeliveryChangeLinkResponse(**item)
            for item in list_change_links(session, project_id=project_id, delivery_item_id=delivery_item_id, actor_id=user.id)
        ]
    except DomainError as exc:
        raise _failure(exc)


@router.post("/{delivery_item_id}/change-links", response_model=DeliveryChangeLinkResponse, status_code=status.HTTP_201_CREATED)
def create_confirmed_change_link(
    project_id: UUID,
    delivery_item_id: UUID,
    payload: DeliveryChangeLinkCreateRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
    _: str = Depends(idempotency_key),
) -> DeliveryChangeLinkResponse:
    try:
        link = confirm_change_link(
            session,
            project_id=project_id,
            delivery_item_id=delivery_item_id,
            pull_request_resource_id=payload.pull_request_resource_id,
            git_snapshot_id=payload.git_snapshot_id,
            reason=payload.reason,
            actor_id=user.id,
            correlation_id=correlation_id(request),
        )
        session.commit()
        items = list_change_links(session, project_id=project_id, delivery_item_id=delivery_item_id, actor_id=user.id)
        item = next(entry for entry in items if entry["id"] == link.id)
        return DeliveryChangeLinkResponse(**item)
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@router.post("/{delivery_item_id}/discover-platform-links", response_model=PlatformLinkDiscoveryResponse)
def discover_links(
    project_id: UUID,
    delivery_item_id: UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
    _: str = Depends(idempotency_key),
) -> PlatformLinkDiscoveryResponse:
    try:
        result = discover_platform_links(
            session,
            project_id=project_id,
            delivery_item_id=delivery_item_id,
            actor_id=user.id,
            correlation_id=correlation_id(request),
        )
        session.commit()
        return PlatformLinkDiscoveryResponse(**result)
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@router.get("/{delivery_item_id}/source-links", response_model=list[DeliveryItemSourceLinkResponse])
def get_source_links(project_id: UUID, delivery_item_id: UUID, session: SessionDep, user: CurrentUserDep) -> list[DeliveryItemSourceLinkResponse]:
    try:
        return [
            DeliveryItemSourceLinkResponse(**item)
            for item in list_item_source_links(session, project_id=project_id, delivery_item_id=delivery_item_id, actor_id=user.id)
        ]
    except DomainError as exc:
        raise _failure(exc)


@router.post("/{delivery_item_id}/source-links", response_model=DeliveryItemSourceLinkResponse, status_code=status.HTTP_201_CREATED)
def create_document_source_link(
    project_id: UUID,
    delivery_item_id: UUID,
    payload: DeliveryItemDocumentSourceLinkCreateRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
    _: str = Depends(idempotency_key),
) -> DeliveryItemSourceLinkResponse:
    try:
        link = link_document_source(
            session,
            project_id=project_id,
            delivery_item_id=delivery_item_id,
            source_revision_id=payload.source_revision_id,
            link_role=payload.link_role,
            actor_id=user.id,
            correlation_id=correlation_id(request),
        )
        session.commit()
        items = list_item_source_links(session, project_id=project_id, delivery_item_id=delivery_item_id, actor_id=user.id)
        item = next(entry for entry in items if entry["id"] == link.id)
        return DeliveryItemSourceLinkResponse(**item)
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)
