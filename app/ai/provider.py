"""Microsoft Foundry provider wiring for the GitHub Copilot SDK.

Follows the BYOK setup in TRD section 10.2: no API keys, only Entra tokens from
a managed identity (or the Azure CLI identity when running locally).
"""

from __future__ import annotations

from typing import Any

from azure.identity.aio import DefaultAzureCredential

from app.settings import Settings

FOUNDRY_SCOPE = "https://cognitiveservices.azure.com/.default"


def build_foundry_provider(settings: Settings) -> Any:
    from copilot.session import ProviderConfig

    if not settings.foundry_resource_url:
        raise ValueError("FOUNDRY_RESOURCE_URL is not configured")

    credential = DefaultAzureCredential()

    async def get_bearer_token(_args: Any = None) -> str:
        token = await credential.get_token(FOUNDRY_SCOPE)
        return token.token

    return ProviderConfig(
        type="openai",
        base_url=f"{settings.foundry_resource_url.rstrip('/')}/openai/v1/",
        bearer_token_provider=get_bearer_token,
        wire_api="responses",
    )
