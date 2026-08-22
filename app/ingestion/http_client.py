"""HTTP client that can only reach allowlisted government hosts."""

from __future__ import annotations

import httpx

from app.ingestion.allowlist import ensure_allowed

USER_AGENT = "DidimHeart-Ingest/0.1 (+https://github.com/matdathon-2026)"


async def _enforce_allowlist(request: httpx.Request) -> None:
    ensure_allowed(str(request.url))


def build_client(timeout_seconds: float) -> httpx.AsyncClient:
    """Create a client that refuses non-allowlisted hosts, including redirects."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        event_hooks={"request": [_enforce_allowlist]},
    )
