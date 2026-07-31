from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep, correlation_id, idempotency_key
from app.api.schemas import ApprovalRequest, ReportDraftUpdateRequest, ReportResponse
from app.application.services.report_service import approve, create_draft, publish, reject, request_changes, submit_for_review, update_draft
from app.domain.errors import DomainError

cycle_router = APIRouter(prefix="/cycles/{cycle_id}/reports")
report_router = APIRouter(prefix="/report-versions")


def to_response(report) -> ReportResponse:
    return ReportResponse(id=report.id, cycle_id=report.cycle_id, sequence_no=report.sequence_no, status=report.status, content_hash=report.content_hash, editorial_note=report.editorial_note, version=report.version)


@cycle_router.post("/from-run/{run_id}", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def draft(cycle_id: UUID, run_id: UUID, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> ReportResponse:
    try:
        report = create_draft(session, cycle_id=cycle_id, run_id=run_id, actor_id=user.id, correlation_id=correlation_id(request)); session.commit()
        return to_response(report)
    except DomainError as exc:
        session.rollback(); raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message})


@report_router.post("/{report_id}/submit", response_model=ReportResponse)
def submit(report_id: UUID, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> ReportResponse:
    try:
        report = submit_for_review(session, report_id=report_id, actor_id=user.id, correlation_id=correlation_id(request)); session.commit(); return to_response(report)
    except DomainError as exc:
        session.rollback(); raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message})


@report_router.put("/{report_id}", response_model=ReportResponse)
def update(report_id: UUID, payload: ReportDraftUpdateRequest, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> ReportResponse:
    try:
        report = update_draft(session, report_id=report_id, editorial_note=payload.editorial_note, item_dispositions=payload.item_dispositions, expected_version=payload.expected_version, actor_id=user.id, correlation_id=correlation_id(request)); session.commit()
        return to_response(report)
    except DomainError as exc:
        session.rollback(); raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message})


@report_router.post("/{report_id}/approve", response_model=ReportResponse)
def approve_report(report_id: UUID, payload: ApprovalRequest, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> ReportResponse:
    try:
        report = approve(session, report_id=report_id, actor_id=user.id, reason=payload.reason, correlation_id=correlation_id(request)); session.commit(); return to_response(report)
    except DomainError as exc:
        session.rollback(); raise HTTPException(status_code=403 if exc.code == "AUTH_FORBIDDEN" else 409, detail={"code": exc.code, "message": exc.message})


@report_router.post("/{report_id}/request-changes", response_model=ReportResponse)
def changes(report_id: UUID, payload: ApprovalRequest, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> ReportResponse:
    try:
        report = request_changes(session, report_id=report_id, actor_id=user.id, reason=payload.reason, correlation_id=correlation_id(request)); session.commit(); return to_response(report)
    except DomainError as exc:
        session.rollback(); raise HTTPException(status_code=403 if exc.code == "AUTH_FORBIDDEN" else 409, detail={"code": exc.code, "message": exc.message})


@report_router.post("/{report_id}/reject", response_model=ReportResponse)
def reject_report(report_id: UUID, payload: ApprovalRequest, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> ReportResponse:
    try:
        report = reject(session, report_id=report_id, actor_id=user.id, reason=payload.reason, correlation_id=correlation_id(request)); session.commit(); return to_response(report)
    except DomainError as exc:
        session.rollback(); raise HTTPException(status_code=403 if exc.code == "AUTH_FORBIDDEN" else 409, detail={"code": exc.code, "message": exc.message})


@report_router.post("/{report_id}/publish", status_code=status.HTTP_201_CREATED)
def publish_report(report_id: UUID, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> dict:
    try:
        record = publish(session, report_id=report_id, actor_id=user.id, correlation_id=correlation_id(request)); session.commit(); return {"id": str(record.id), "recordNo": record.record_no, "recordHash": record.record_hash}
    except DomainError as exc:
        session.rollback(); raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message})
