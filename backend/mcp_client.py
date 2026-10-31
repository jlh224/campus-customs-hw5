"""The agents' only path to shop data: the campus-customs MCP server.

One MCPToolset attaches mcp_server/server.py in-process (FastMCP in-memory
transport, the same tools listed in .mcp.json). Each agent sees a filtered
view with only the tools its role needs. There is no other shop-tools layer.

Every MCP call goes through audit_tool_call(), which:
  - blocks `pay` (money moves only through the human approval route),
  - writes the call and its result to the audit trail,
  - puts prepare_payment / draft_purchase_order results on the board,
  - trims long results before they go back to the model.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any

from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset

import audit
from config import ROOT, TOOL_RESULT_CHARS

if TYPE_CHECKING:
    from agents import AgentDeps

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from mcp_server.server import mcp as campus_mcp  # noqa: E402

# Tools no agent may call. `pay` is only for the human approval route.
HUMAN_ONLY_TOOLS = {"pay"}

# Which MCP tools each agent sees.
AGENT_TOOLS: dict[str, set[str]] = {
    "boss": {"list_open_tickets", "get_ticket", "get_cash_balance", "update_ticket"},
    "inventory": {"get_ticket", "check_stock", "get_vendor_status", "draft_purchase_order"},
    "accounting": {
        "get_ticket", "get_cash_balance", "get_invoice", "get_pricing", "get_lease",
        "get_vendor_status", "get_payments", "prepare_payment", "draft_purchase_order",
    },
    "facilities": {"get_ticket", "get_lease", "get_payments"},
    "customer_service": {"get_ticket", "check_stock", "get_vendor_status"},
}
assert not any(tools & HUMAN_ONLY_TOOLS for tools in AGENT_TOOLS.values()), "pay must never be given to an agent"


def _as_data(result: Any) -> Any:
    """MCP results arrive as dicts or JSON text; normalise to Python data when possible."""
    if isinstance(result, (dict, list)):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result
    return result


async def audit_tool_call(ctx: RunContext["AgentDeps"], call_tool: CallToolFunc, name: str, args: dict[str, Any]) -> Any:
    deps = ctx.deps
    if name in HUMAN_ONLY_TOOLS:
        deps.state.log(deps, "tool_blocked", tool=name, args=args, reason="human-only tool")
        return {"error": f"'{name}' is human-only. Use prepare_payment; a human approves and pays on the board."}

    deps.steps += 1
    deps.state.tools_used.append(name)
    deps.state.log(deps, "tool_call", step=deps.steps, tool=name, args=args)
    await deps.state.emit("tool_call", {"agent": deps.agent, "tool": name, "args": args})

    try:
        result = await call_tool(name, args)
    except Exception as exc:  # the model sees the error and can correct itself
        deps.state.log(deps, "tool_error", step=deps.steps, tool=name, args=args, error=str(exc))
        raise

    data = _as_data(result)
    deps.state.log(deps, "tool_result", step=deps.steps, tool=name, result=audit.clip(json.dumps(data, default=str)))
    deps.state.capture_board_item(deps.agent, name, data)
    await deps.state.emit("tool_result", {"agent": deps.agent, "tool": name, "result": data})

    text = json.dumps(data, default=str) if not isinstance(data, str) else data
    if len(text) > TOOL_RESULT_CHARS:
        return text[:TOOL_RESULT_CHARS] + f"... [cut: {len(text) - TOOL_RESULT_CHARS} more chars]"
    return result


_shop_toolset = MCPToolset(campus_mcp, process_tool_call=audit_tool_call, id="campus-customs")


def toolset_for(agent: str):
    """The MCP tools one agent may use (never the human-only ones)."""
    allowed = AGENT_TOOLS[agent] - HUMAN_ONLY_TOOLS
    return _shop_toolset.filtered(lambda _ctx, tool_def: tool_def.name in allowed)


# The Boss's board triage only looks: read-only tools, no writes, no delegation.
TRIAGE_TOOLS = {"list_open_tickets", "get_ticket", "get_cash_balance", "get_lease", "get_invoice"}


def triage_toolset():
    return _shop_toolset.filtered(lambda _ctx, tool_def: tool_def.name in TRIAGE_TOOLS)


async def call_tool(name: str, args: dict[str, Any] | None = None) -> Any:
    """Call one MCP tool from a backend route (the board, the human approval route).

    Routes use the same MCP server as the agents, so even the human 'pay' click
    goes through the MCP pay tool, never straight to the database.
    """
    from fastmcp import Client

    async with Client(campus_mcp) as client:
        result = await client.call_tool(name, args or {}, raise_on_error=False)
    if result.is_error:
        raise RuntimeError(f"MCP tool {name} failed: {result.content[0].text if result.content else 'unknown error'}")
    return result.structured_content if result.structured_content is not None else _as_data(result.content[0].text)
