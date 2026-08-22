"""Agent runtime: builds the two MAF agents backed by the GitHub Copilot SDK.

Security:
- The default permission handler is deny-all. MAF function tools are gated as
  PermissionRequestCustomTool, so we install an on_permission_request handler that
  approves ONLY our four tools by exact name and denies shell/write/url/mcp/etc.
- The GitHub token is read by the SDK from the environment (COPILOT_GITHUB_TOKEN
  preferred). It is never logged or returned to clients.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from app.agents.tools import ALL_TOOLS, ALLOWED_TOOL_NAMES

_TOKEN_ENV_VARS = (
    "COPILOT_GITHUB_TOKEN",
    "GITHUB_COPILOT_API_TOKEN",
    "GH_TOKEN",
    "GITHUB_TOKEN",
)


def token_present() -> bool:
    # Foundry uses the Container App's managed identity, so it needs no GitHub
    # token. Keep the function name for the existing service contract.
    return bool(os.environ.get("FOUNDRY_RESOURCE_URL")) or any(
        os.environ.get(v) for v in _TOKEN_ENV_VARS
    )


def runtime_binary_present() -> bool:
    try:
        import copilot  # noqa: WPS433

        base = Path(copilot.__file__).resolve().parent
        for name in ("copilot.exe", "copilot"):
            if (base / "bin" / name).exists():
                return True
        # Fallback: extract dir override
        override = os.environ.get("COPILOT_CLI_EXTRACT_DIR")
        return bool(override and Path(override).exists())
    except Exception:
        return False


def _permission_handler():
    """Return an on_permission_request callback that allowlists our tools only."""
    from copilot.generated.rpc import (
        PermissionDecisionApproveOnce,
        PermissionDecisionUserNotAvailable,
    )
    from copilot.session_events import PermissionRequestCustomTool

    def handler(request: Any, _invocation: dict[str, str]):
        tool_name = getattr(request, "tool_name", None)
        if isinstance(request, PermissionRequestCustomTool) and tool_name in ALLOWED_TOOL_NAMES:
            return PermissionDecisionApproveOnce()
        # Deny everything else (shell/write/url/mcp/unknown tools) by default.
        return PermissionDecisionUserNotAvailable()

    return handler


def _build_provider():
    """Optional Foundry BYOK provider. Returns None to use ambient Copilot auth."""
    foundry_url = os.environ.get("FOUNDRY_RESOURCE_URL", "").strip()
    if not foundry_url:
        return None
    try:
        from azure.identity.aio import DefaultAzureCredential
        from copilot.session import ProviderConfig

        credential = DefaultAzureCredential()

        async def get_bearer_token(_args=None) -> str:
            token = await credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
            return token.token

        return ProviderConfig(
            type="openai",
            base_url=f"{foundry_url.rstrip('/')}/openai/v1/",
            bearer_token_provider=get_bearer_token,
            wire_api="responses",
        )
    except Exception:
        return None


class AgentRuntime:
    """Lazily constructs and caches the matcher and planner agents."""

    def __init__(self, *, timeout: float = 30.0, model: str = "") -> None:
        self._timeout = timeout
        self._model = model
        self._matcher = None
        self._planner = None
        self._import_error: Optional[str] = None

    def _base_options(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "timeout": self._timeout,
            "on_permission_request": _permission_handler(),
        }
        if self._model:
            opts["model"] = self._model
        provider = _build_provider()
        if provider is not None:
            opts["provider"] = provider
        return opts

    def _ensure_agents(self) -> None:
        if self._matcher is not None and self._planner is not None:
            return
        from agent_framework.github import GitHubCopilotAgent

        from app.agents.matcher import MATCHER_INSTRUCTIONS
        from app.agents.planner import PLANNER_INSTRUCTIONS

        self._matcher = GitHubCopilotAgent(
            MATCHER_INSTRUCTIONS,
            name="BenefitMatcherAgent",
            tools=ALL_TOOLS,
            default_options=self._base_options(),
        )
        self._planner = GitHubCopilotAgent(
            PLANNER_INSTRUCTIONS,
            name="ActionPlannerAgent",
            tools=ALL_TOOLS,
            default_options=self._base_options(),
        )

    async def run_matcher(self, prompt: str) -> str:
        self._ensure_agents()
        result = await self._matcher.run(prompt)
        return getattr(result, "text", str(result))

    async def run_planner(self, prompt: str) -> str:
        self._ensure_agents()
        result = await self._planner.run(prompt)
        return getattr(result, "text", str(result))

    def status(self) -> dict[str, Any]:
        return {
            "runtime": "ready" if runtime_binary_present() else "missing",
            "auth": "configured" if token_present() else "missing",
            "model": self._model or "copilot-default",
        }


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first top-level JSON object from a model response."""
    text = text.strip()
    if text.startswith("```"):
        # strip code fences
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model output")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unbalanced JSON object in model output")
