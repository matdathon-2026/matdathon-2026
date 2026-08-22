"""Entrypoint for the scheduled Azure Container Apps job.

    python -m app.ingestion

Exits non-zero when nothing could be ingested, so a failed run is visible in
the job's execution history.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from app.ingestion.pipeline import run_ingestion
from app.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger("app.ingestion.job")


async def main() -> int:
    settings = get_settings()
    logger.info("ingestion started", extra={"environment": settings.environment})

    report = await run_ingestion(settings)
    print(json.dumps({"ingestionReport": report.as_dict()}, ensure_ascii=False))

    if report.fetched == 0:
        logger.error("no records fetched from any source")
        return 1
    if report.normalized == 0:
        logger.error("no records survived validation")
        return 1
    if report.upserts.errors:
        logger.error("catalog writes failed", extra={"count": len(report.upserts.errors)})
        return 1

    logger.info("ingestion finished", extra={"written": report.upserts.written})
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
