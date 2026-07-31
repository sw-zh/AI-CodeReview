"""Worker process baseline; job polling is added with the AnalysisJob aggregate."""

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.infrastructure.persistence.models import AnalysisJob, AnalysisRun, RunEvent

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
    """Durable lease baseline; workflow execution is attached in the next slice."""
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
        else:
            job.job_status = "RUNNING"
            job.lease_owner = worker_id
            job.lease_expires_at = now + timedelta(seconds=lease_seconds)
            job.heartbeat_at = now
            job.attempt_no += 1
            run.run_status = "RUNNING"
            run.started_at = run.started_at or now
            # A later LangGraph slice replaces this terminal transition with typed workflow execution.
            job.job_status = "PARTIALLY_COMPLETED"
            run.run_status = "PARTIALLY_COMPLETED"
            run.finished_at = datetime.now(UTC)
        session.add(RunEvent(run_id=run.id, node_id=None, event_type="JOB_EXECUTION", status=run.run_status, correlation_id=str(run.id), payload_redacted={"workerId": worker_id, "attempt": job.attempt_no}))


if __name__ == "__main__":
    main()
