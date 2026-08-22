"""Source adapter contract.

Adapters do structural extraction only: pull a list of records out of an
upstream response and tag each one with provenance. Semantic normalisation
into the catalog schema happens later in the curator agent, so an upstream
field rename degrades quality instead of crashing the job.
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable

import httpx

from app.domain.benefit import RawRecord

# Keys upstream systems commonly use for a stable record identifier.
_ID_KEYS = (
    "plcyNo",
    "bizId",
    "servId",
    "servid",
    "id",
    "policyId",
    "wlfareInfoId",
)


class SourceError(RuntimeError):
    """Upstream source failed in a way the pipeline should report, not hide."""

    def __init__(self, source: str, message: str) -> None:
        super().__init__(f"[{source}] {message}")
        self.source = source


@runtime_checkable
class SourceAdapter(Protocol):
    name: str

    def enabled(self) -> bool: ...

    async def fetch(self, client: httpx.AsyncClient) -> list[RawRecord]: ...


def find_record_list(payload: Any) -> list[dict[str, Any]]:
    """Walk a JSON response and return the largest list of dicts inside it.

    Government endpoints wrap results in varying envelopes
    (``result.youthPolicyList``, ``response.body.items.item``, ...), so we
    search structurally instead of hardcoding one envelope shape.
    """
    best: list[dict[str, Any]] = []
    stack: list[Any] = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, list):
            dicts = [item for item in node if isinstance(item, dict)]
            if len(dicts) > len(best):
                best = dicts
            stack.extend(item for item in node if not isinstance(item, dict))
    return best


def pick_source_id(record: dict[str, Any], fallback: str) -> str:
    for key in _ID_KEYS:
        value = record.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return fallback


def trim(records: Iterable[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return list(records)[:limit]
