"""Worker process baseline; job polling is added with the AnalysisJob aggregate."""

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.infrastructure.persistence.models import AnalysisJob, AnalysisRun, InputSnapshot, RunEvent, VerificationCycle, VerificationResult
from app.workflows.verification_graph import run_verification_graph

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("worker_started worker_id=%s", settings.worker_id)
    while True:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            _claim_and_complete_one(settings.worker_id, settings.job_lease_seconds)
            logger.info("worker_heartbeat worker_id=%s", settings.worker_id)
        except SQLAlchemyError:
            logger.exception("worker_database_unavailable worker_id=%s", settings.worker_id)
        time.sleep(15)


def _claim_and_complete_one(worker_id: str, lease_seconds: int) -> None:
    """Claim one job, persist graph output, then derive only the cycle's business view."""
    now = datetime.now(UTC)
    with SessionLocal.begin() as session:
        job = (
            session.query(AnalysisJob)
            .filter(
                or_(AnalysisJob.job_status == "QUEUED", (AnalysisJob.job_status == "RUNNING") & (AnalysisJob.lease_expires_at < now))
            )
            .order_by(AnalysisJob.created_at)
            .with_for_update(skip_locked=True)
            .first()
        )
        if job is None:
            return
        run = session.get(AnalysisRun, job.run_id)
        if run is None:
            job.job_status = "FAILED"
            job.last_error_code = "RUN_MISSING"
            return
        if run.cancel_requested_at is not None:
            job.job_status = "CANCELLED"
            run.run_status = "CANCELLED"
            run.finished_at = now
            snapshot = session.get(InputSnapshot, run.snapshot_id)
            cycle = session.get(VerificationCycle, snapshot.cycle_id) if snapshot else None
            if cycle is not None:
                cycle.business_status = "DRAFT"
        else:
            job.job_status = "RUNNING"
            job.lease_owner = worker_id
            job.lease_expires_at = now + timedelta(seconds=lease_seconds)
            job.heartbeat_at = now
            job.attempt_no += 1
            run.run_status = "RUNNING"
            run.started_at = run.started_at or now
            try:
                graph_state = run_verification_graph(session, run.id, run.snapshot_id)
                job.job_status = "SUCCEEDED"
                run.run_status = "PARTIALLY_COMPLETED" if graph_state.get("node_errors") else "SUCCEEDED"
                _derive_cycle_status(session, run)
            except Exception:
                logger.exception("workflow_failed run_id=%s", run.id)
                job.last_error_code = "WORKFLOW_FAILED"
                job.job_status = "FAILED" if job.attempt_no >= job.max_attempts else "QUEUED"
                run.run_status = "FAILED" if job.job_status == "FAILED" else "QUEUED"
                if run.run_status == "FAILED":
                    _derive_cycle_status(session, run)
            if run.run_status in {"SUCCEEDED", "PARTIALLY_COMPLETED", "FAILED"}:
                run.finished_at = datetime.now(UTC)
        session.add(RunEvent(run_id=run.id, node_id=None, event_type="JOB_EXECUTION", status=run.run_status, correlation_id=str(run.id), payload_redacted={"workerId": worker_id, "attempt": job.attempt_no}))


def _derive_cycle_status(session, run: AnalysisRun) -> None:
    """Run status remains technical; the cycle exposes evidence readiness separately."""
    snapshot = session.get(InputSnapshot, run.snapshot_id)
    cycle = session.get(VerificationCycle, snapshot.cycle_id) if snapshot else None
    if cycle is None:
        return
    results = session.query(VerificationResult).filter_by(analysis_run_id=run.id).all()
    if not results:
        cycle.business_status = "NEEDS_EVIDENCE"
    elif any(item.requires_human_confirmation for item in results):
        cycle.business_status = "NEEDS_CONFIRMATION"
    elif all(item.status == "INSUFFICIENT_EVIDENCE" for item in results):
        cycle.business_status = "NEEDS_EVIDENCE"
    else:
        cycle.business_status = "DRAFT_READY"


if __name__ == "__main__":
    main()
