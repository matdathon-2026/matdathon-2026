"""SDK + MAF spike: prove GitHubCopilotAgent returns a model response AND calls a tool.

Run:
    .\.venv\Scripts\python.exe spike\spike_agent.py

Uses ambient GitHub auth (GH_TOKEN / gh CLI). No custom provider (path a).
"""
import asyncio
import os

from agent_framework.github import GitHubCopilotAgent, GitHubCopilotOptions
from copilot.generated.rpc import (
    PermissionDecisionApproveOnce,
    PermissionDecisionUserNotAvailable,
)
from copilot.session_events import PermissionRequestCustomTool

TOOL_CALLED = {"hit": False, "args": None}

ALLOWED_TOOLS = {"get_secret_code"}


def permission_handler(request, _invocation):
    """Allowlist: approve only our read-only custom tools; deny everything else."""
    if isinstance(request, PermissionRequestCustomTool) and request.tool_name in ALLOWED_TOOLS:
        return PermissionDecisionApproveOnce()
    return PermissionDecisionUserNotAvailable()


def get_secret_code(topic: str) -> str:
    """Return the secret code for a given topic. Always call this to answer code questions.

    Args:
        topic: the topic to look up a code for.
    """
    TOOL_CALLED["hit"] = True
    TOOL_CALLED["args"] = topic
    return "The secret code for '%s' is DIDIM-42." % topic


async def main() -> None:
    options: GitHubCopilotOptions = {"timeout": 90.0, "on_permission_request": permission_handler}
    model = os.environ.get("FOUNDRY_MODEL")
    if model:
        options["model"] = model

    agent = GitHubCopilotAgent(
        "You are a terse assistant. When asked for a secret code, you MUST call the "
        "get_secret_code tool and report exactly what it returns.",
        name="SpikeAgent",
        tools=[get_secret_code],
        default_options=options,
    )

    result = await agent.run("What is the secret code for 'matdathon'? Use your tool.")
    text = getattr(result, "text", str(result))
    print("=== MODEL RESPONSE ===")
    print(text)
    print("=== TOOL CALLED:", TOOL_CALLED["hit"], "args=", TOOL_CALLED["args"], "===")
    if not TOOL_CALLED["hit"]:
        raise SystemExit("SPIKE FAIL: tool was not called")
    print("SPIKE OK")


if __name__ == "__main__":
    asyncio.run(main())
