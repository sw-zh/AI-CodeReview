"""Worker process baseline; job polling is added with the AnalysisJob aggregate."""

import logging
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db import engine

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("worker_started worker_id=%s", settings.worker_id)
    while True:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("worker_heartbeat worker_id=%s", settings.worker_id)
        except SQLAlchemyError:
            logger.exception("worker_database_unavailable worker_id=%s", settings.worker_id)
        time.sleep(15)


if __name__ == "__main__":
    main()
