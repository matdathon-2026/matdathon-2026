"""공공데이터포털 (data.go.kr) welfare service adapter.

UNVERIFIED: every probe returns an empty HTTP 400 without a real service key,
including deliberately bogus paths, so the endpoint path could not be
confirmed. This source is disabled by default; turn it on only after a live
call succeeds with an issued key.
"""

from __future__ import annotations

import httpx

from app.domain.benefit import RawRecord
from app.ingestion.sources.base import (
    SourceError,
    find_record_list,
    pick_source_id,
)

NAME = "data_go_kr"
ENDPOINT = "https://apis.data.go.kr/B554287/NationalWelfareInformations/NationalWelfarelist"
AGENCY = "한국사회보장정보원"
DETAIL_URL = (
    "https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do"
    "?wlfareInfoId={id}"
)


class DataGoKrSource:
    name = NAME

    def __init__(self, service_key: str, enabled: bool, max_records: int) -> None:
        self._service_key = service_key
        self._enabled = enabled
        self._max_records = max_records

    def enabled(self) -> bool:
        return self._enabled and bool(self._service_key)

    async def fetch(self, client: httpx.AsyncClient) -> list[RawRecord]:
        params = {
            "serviceKey": self._service_key,
            "callTp": "L",
            "pageNo": 1,
            "numOfRows": self._max_records,
            "srchKeyCode": "003",
        }
        try:
            response = await client.get(ENDPOINT, params=params)
        except httpx.HTTPError as exc:
            raise SourceError(NAME, f"request failed: {exc.__class__.__name__}") from exc

        if response.status_code >= 400:
            raise SourceError(NAME, f"HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError(NAME, "response was not JSON (XML fallback unsupported)") from exc

        records = find_record_list(payload)[: self._max_records]
        return [
            RawRecord(
                source_system=NAME,
                source_id=(source_id := pick_source_id(record, fallback=str(index))),
                source_url=DETAIL_URL.format(id=source_id),
                source_agency=AGENCY,
                payload=record,
            )
            for index, record in enumerate(records)
        ]
