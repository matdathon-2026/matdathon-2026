"""Raw response archive in Azure Blob Storage.

Keeping the untouched upstream payload lets us diff changes over time and prove
what a recommendation was derived from. Archiving is best-effort: losing the
archive must not stop the catalog from updating.
"""

from __future__ import annotations

import json
import logging

from azure.core.exceptions import AzureError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from app.domain.benefit import RawRecord

logger = logging.getLogger(__name__)


class RawArchive:
    def __init__(self, account_url: str, container: str) -> None:
        self._account_url = account_url
        self._container = container
        self._credential: DefaultAzureCredential | None = None
        self._client: BlobServiceClient | None = None

    @property
    def configured(self) -> bool:
        return bool(self._account_url)

    async def __aenter__(self) -> "RawArchive":
        if self.configured:
            self._credential = DefaultAzureCredential()
            self._client = BlobServiceClient(
                account_url=self._account_url, credential=self._credential
            )
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        if self._client is not None:
            await self._client.close()
        if self._credential is not None:
            await self._credential.close()

    async def store(self, record: RawRecord) -> bool:
        if self._client is None:
            return False
        blob = self._client.get_blob_client(
            container=self._container, blob=record.archive_blob_name()
        )
        body = json.dumps(
            {
                "sourceSystem": record.source_system,
                "sourceId": record.source_id,
                "sourceUrl": record.source_url,
                "fetchedAt": record.fetched_at.isoformat(),
                "contentHash": record.content_hash,
                "payload": record.payload,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        try:
            await blob.upload_blob(body, overwrite=True)
            return True
        except AzureError:
            logger.warning(
                "raw archive upload failed",
                extra={"sourceSystem": record.source_system},
                exc_info=True,
            )
            return False
