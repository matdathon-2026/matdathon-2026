"""Outbound host allowlist for the ingestion job.

Enforced at the HTTP client layer rather than at each call site, so a bug or a
crafted upstream payload cannot redirect the job at an arbitrary host.
"""

from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "www.youthcenter.go.kr",
        "apis.data.go.kr",
        "www.bokjiro.go.kr",
        "www.mohw.go.kr",
        "www.ncrc.or.kr",
    }
)


class HostNotAllowedError(RuntimeError):
    def __init__(self, host: str) -> None:
        super().__init__(f"host not in ingestion allowlist: {host!r}")
        self.host = host


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_allowed(url: str) -> bool:
    return host_of(url) in ALLOWED_HOSTS


def ensure_allowed(url: str) -> None:
    if not is_allowed(url):
        raise HostNotAllowedError(host_of(url))
