from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep, correlation_id, idempotency_key
from app.api.schemas import (
    AgentCapabilityCreateRequest,
    AgentCapabilityVersionCreateRequest,
    AgentToolCreateRequest,
    OrchestrationTemplateCreateRequest,
    TaskOrchestrationBindingRequest,
)
from app.application.services.orchestration_service import (
    bind_task_template,
    create_capability_version,
    create_custom_capability,
    create_custom_tool,
    create_template,
    ensure_default_orchestration,
    get_run_orchestration,
    list_orchestration,
)
from app.application.services.common import require_project_role
from app.domain.enums import ProjectRole
from app.domain.errors import DomainError


project_router = APIRouter(prefix="/projects/{project_id}/agent-orchestration")
task_router = APIRouter(prefix="/verification-tasks/{task_id}/agent-orchestration")
run_router = APIRouter(prefix="/analysis-runs")


def _failure(exc: DomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN if exc.code == "AUTH_FORBIDDEN" else status.HTTP_409_CONFLICT, detail={"code": exc.code, "message": exc.message})


@project_router.get("")
def list_project_orchestration(project_id: UUID, session: SessionDep, user: CurrentUserDep) -> dict:
    try:
        require_project_role(session, project_id, user.id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
        ensure_default_orchestration(session, project_id=project_id, actor_id=user.id)
        session.commit()
        return list_orchestration(session, project_id=project_id, actor_id=user.id)
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@project_router.post("/tools", status_code=status.HTTP_201_CREATED)
def create_tool(project_id: UUID, payload: AgentToolCreateRequest, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> dict:
    try:
        tool = create_custom_tool(session, project_id=project_id, actor_id=user.id, correlation_id=correlation_id(request), **payload.model_dump())
        session.commit()
        return {"id": str(tool.id), "key": tool.key, "name": tool.name, "toolType": tool.tool_type}
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@project_router.post("/capabilities", status_code=status.HTTP_201_CREATED)
def create_capability(project_id: UUID, payload: AgentCapabilityCreateRequest, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> dict:
    try:
        capability = create_custom_capability(session, project_id=project_id, actor_id=user.id, correlation_id=correlation_id(request), **payload.model_dump())
        session.commit()
        return {"id": str(capability.id), "key": capability.key, "name": capability.name, "coreScope": capability.core_scope}
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@project_router.post("/capabilities/{capability_id}/versions", status_code=status.HTTP_201_CREATED)
def version_capability(project_id: UUID, capability_id: UUID, payload: AgentCapabilityVersionCreateRequest, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> dict:
    try:
        version = create_capability_version(session, capability_id=capability_id, actor_id=user.id, correlation_id=correlation_id(request), **payload.model_dump())
        session.commit()
        return {"id": str(version.id), "version": version.version_no, "contentHash": version.content_hash}
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@project_router.post("/templates", status_code=status.HTTP_201_CREATED)
def create_orchestration_template(project_id: UUID, payload: OrchestrationTemplateCreateRequest, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> dict:
    try:
        template = create_template(session, project_id=project_id, actor_id=user.id, correlation_id=correlation_id(request), name=payload.name, description=payload.description, nodes=[item.model_dump() for item in payload.nodes])
        session.commit()
        return {"id": str(template.id), "name": template.name, "version": template.version}
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@task_router.put("")
def bind_orchestration_template(task_id: UUID, payload: TaskOrchestrationBindingRequest, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> dict:
    try:
        binding = bind_task_template(session, task_id=task_id, template_id=payload.template_id, actor_id=user.id, correlation_id=correlation_id(request))
        session.commit()
        return {"taskId": str(binding.task_id), "templateId": str(binding.template_id), "templateVersion": binding.template_version}
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@run_router.get("/{run_id}/orchestration")
def run_orchestration(run_id: UUID, session: SessionDep, user: CurrentUserDep) -> dict:
    try:
        return get_run_orchestration(session, run_id=run_id, actor_id=user.id)
    except DomainError as exc:
        raise _failure(exc)
