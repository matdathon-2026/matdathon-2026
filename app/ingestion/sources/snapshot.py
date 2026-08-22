"""Repository snapshot source.

Guarantees the pipeline and the demo keep working when API keys are missing or
an upstream service is down, which PRD section 11.1 requires.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.domain.benefit import RawRecord
from app.ingestion.sources.base import SourceError

NAME = "snapshot"


class SnapshotSource:
    name = NAME

    def __init__(self, path: str, enabled: bool) -> None:
        self._path = Path(path)
        self._enabled = enabled

    def enabled(self) -> bool:
        return self._enabled and self._path.is_file()

    async def fetch(self, client: httpx.AsyncClient) -> list[RawRecord]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SourceError(NAME, f"cannot read {self._path}: {exc}") from exc

        if not isinstance(raw, list):
            raise SourceError(NAME, "snapshot root must be a JSON array")

        return [
            RawRecord(
                source_system=NAME,
                source_id=str(item.get("id") or index),
                source_url=str(item.get("sourceUrl", "")),
                source_agency=str(item.get("sourceAgency", "")),
                payload=item,
            )
            for index, item in enumerate(raw)
            if isinstance(item, dict)
        ]
