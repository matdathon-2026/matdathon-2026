"""온통청년 (Youth Center) policy API adapter.

Endpoint and the ``apiKeyNm`` parameter name were verified live: an
unauthenticated call returns HTTP 403 ``{"errorCode":"e001"}``. Response field
names are NOT verified, so we hand whole records to the curator agent rather
than mapping fields here.
"""

from __future__ import annotations

import httpx

from app.domain.benefit import RawRecord
from app.ingestion.sources.base import (
    SourceError,
    find_record_list,
    pick_source_id,
)

NAME = "youthcenter"
ENDPOINT = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
AGENCY = "온통청년(한국청소년정책연구원)"
DETAIL_URL = "https://www.youthcenter.go.kr/youthPolicy/ythPlcyDetail?plcyNo={id}"

# Keyword filters aimed at the 자립준비청년 cohort.
KEYWORDS = ("자립준비청년", "보호종료아동", "자립수당", "자립정착금")

PAGE_SIZE = 100


class YouthCenterSource:
    name = NAME

    def __init__(self, api_key: str, enabled: bool, max_records: int) -> None:
        self._api_key = api_key
        self._enabled = enabled
        self._max_records = max_records

    def enabled(self) -> bool:
        return self._enabled and bool(self._api_key)

    async def fetch(self, client: httpx.AsyncClient) -> list[RawRecord]:
        collected: dict[str, dict] = {}
        for keyword in KEYWORDS:
            for record in await self._fetch_keyword(client, keyword):
                source_id = pick_source_id(record, fallback=keyword)
                collected.setdefault(source_id, record)

        return [
            RawRecord(
                source_system=NAME,
                source_id=source_id,
                source_url=DETAIL_URL.format(id=source_id),
                source_agency=AGENCY,
                payload=record,
            )
            for source_id, record in list(collected.items())[: self._max_records]
        ]

    async def _fetch_keyword(
        self, client: httpx.AsyncClient, keyword: str
    ) -> list[dict]:
        params = {
            "apiKeyNm": self._api_key,
            "pageNum": 1,
            "pageSize": PAGE_SIZE,
            "rtnType": "json",
            "plcyKywdNm": keyword,
        }
        try:
            response = await client.get(ENDPOINT, params=params)
        except httpx.HTTPError as exc:
            raise SourceError(NAME, f"request failed: {exc.__class__.__name__}") from exc

        if response.status_code == 403:
            raise SourceError(NAME, "API key rejected (HTTP 403)")
        if response.status_code >= 400:
            raise SourceError(NAME, f"HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError(NAME, "response was not JSON") from exc

        return find_record_list(payload)
