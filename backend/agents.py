"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

Each agent is a PydanticAI agent with:
  - a prompt:   backend/prompts/<agent>.md
  - a model:    gpt-6-luna via Portkey (config.py)
  - tools:      its slice of the campus-customs MCP server (mcp_client.py)
  - delegate(): hand a task to ANY other agent (full connectivity)
  - a loop:     agent.iter(), capped by request / tool-call limits

run_ticket(ticket_id) starts the Boss on one ticket. Specialists can delegate
straight to each other (e.g. Inventory -> Accounting) without going back
through the Boss. Every loop step is appended to output/audit_trail.json.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic_ai import Agent, NativeOutput, RunContext
from pydantic_ai.messages import TextPart, ToolCallPart
from pydantic_ai.usage import UsageLimits

import audit
from config import (
    BOSS_EFFORT,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_TICKET,
    MAX_MODEL_REQUESTS_PER_RUN,
    MAX_TOOL_CALLS_PER_RUN,
    MODEL_NAME,
    SPECIALIST_EFFORT,
    TICKET_TOKEN_BUDGET,
    build_model,
    load_prompt,
    settings,
)
from mcp_client import AGENT_TOOLS, toolset_for, triage_toolset
from models import (
    AGENT_NAMES,
    AGENT_TITLES,
    AgentName,
    AgentReport,
    CustomerDraft,
    Handoff,
    PaymentRequest,
    PurchaseOrderDraft,
    TicketDecision,
    TicketRunResult,
    TriageResult,
    UsageTotals,
)

Emit = Callable[[str, dict], Awaitable[None]]

# One line per teammate, shown to every agent so it knows whom to ask.
ROLES = {
    "boss": "reads each ticket, decides who works it, and makes the final call",
    "inventory": "checks stock by SKU and size, spots shortfalls, finds the vendor that can restock",
    "accounting": "watches cash and invoices, checks margins and discounts, prepares payments and purchase orders for human approval",
    "facilities": "handles the shop space: leases, rent amounts and due dates",
    "customer_service": "drafts messages to customers (drafts stay on the board, never sent)",
}


async def _no_emit(_type: str, _data: dict) -> None:
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- Shared state for one ticket run ----------

@dataclass
class RunState:
    ticket_id: int
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    started_at: str = field(default_factory=_now)
    emit_fn: Emit = _no_emit
    handoffs: list[Handoff] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    payment_requests: dict[tuple, PaymentRequest] = field(default_factory=dict)
    purchase_orders: dict[tuple, PurchaseOrderDraft] = field(default_factory=dict)
    customer_drafts: list[CustomerDraft] = field(default_factory=list)
    usage: UsageTotals = field(default_factory=UsageTotals)

    async def emit(self, type_: str, data: dict) -> None:
        await self.emit_fn(type_, {"run_id": self.run_id, "ticket_id": self.ticket_id, **data})

    def log(self, deps: "AgentDeps | None", event: str, **fields: Any) -> None:
        who = {}
        if deps is not None:
            who = {
                "agent": deps.agent,
                "depth": deps.depth,
                "delegated_by": deps.delegated_by,
                "chain": list(deps.chain),
            }
        audit.append(event, run_id=self.run_id, ticket_id=self.ticket_id, model=MODEL_NAME, **who, **fields)

    def capture_board_item(self, agent: str, tool: str, data: Any) -> None:
        """Payment requests and purchase orders come from real MCP results, never model text."""
        if not isinstance(data, dict):
            return
        if tool == "prepare_payment" and data.get("prepared"):
            req = PaymentRequest(**{k: data.get(k) for k in PaymentRequest.model_fields if k in data}, requested_by=agent)
            self.payment_requests[(req.kind, req.ref_id)] = req
        elif tool == "draft_purchase_order" and data.get("drafted"):
            po = PurchaseOrderDraft(**{k: data.get(k) for k in PurchaseOrderDraft.model_fields if k in data}, requested_by=agent)
            self.purchase_orders[(po.vendor_id, po.sku, po.size)] = po


@dataclass
class AgentDeps:
    state: RunState
    agent: AgentName
    depth: int = 0
    delegated_by: str | None = None
    chain: tuple[str, ...] = ()
    steps: int = 0


# ---------- Building the five agents ----------

def _team_instructions(ctx: RunContext[AgentDeps]) -> str:
    d = ctx.deps
    others = [a for a in AGENT_NAMES if a != d.agent]
    team = "\n".join(
        f"- {a}: {ROLES[a]}" + ("  (already working on this chain above you; do not delegate back)" if a in d.chain else "")
        for a in others
    )
    can_delegate = d.depth < MAX_DELEGATION_DEPTH
    return (
        f"## This run\n"
        f"You are the {AGENT_TITLES[d.agent]} agent. Ticket being worked: #{d.state.ticket_id}.\n"
        f"You were asked by: {d.delegated_by or 'the shop desk (you own this ticket)'}.\n"
        f"Your MCP tools: {', '.join(sorted(AGENT_TOOLS[d.agent]))}.\n\n"
        f"## Your teammates (use delegate(to_agent, task) to hand them work)\n{team}\n\n"
        f"Delegation depth {d.depth} of {MAX_DELEGATION_DEPTH}. "
        + ("You may delegate. " if can_delegate else "You are at the depth limit: do NOT delegate, answer from what you have. ")
        + f"The whole ticket may use at most {MAX_DELEGATIONS_PER_TICKET} handoffs, "
        f"and you get {MAX_MODEL_REQUESTS_PER_RUN} model calls for this task, so be direct."
    )


async def delegate(ctx: RunContext[AgentDeps], to_agent: AgentName, task: str) -> str:
    """Hand a focused task to another agent on the team and get its report back.

    Args:
        to_agent: boss, inventory, accounting, facilities, or customer_service.
        task: What you need from them, with the ticket id and any facts you already have.
    """
    d, state = ctx.deps, ctx.deps.state
    refusal = None
    if to_agent == d.agent:
        refusal = "You cannot delegate to yourself."
    elif to_agent in d.chain:
        refusal = f"{to_agent} is already working on this chain above you. Answer from what you have."
    elif d.depth >= MAX_DELEGATION_DEPTH:
        refusal = f"Delegation depth limit ({MAX_DELEGATION_DEPTH}) reached. Answer from what you have."
    elif len(state.handoffs) >= MAX_DELEGATIONS_PER_TICKET:
        refusal = f"This ticket has used all {MAX_DELEGATIONS_PER_TICKET} handoffs. Answer from what you have."
    elif state.usage.total_tokens >= TICKET_TOKEN_BUDGET:
        refusal = f"This ticket's token budget ({TICKET_TOKEN_BUDGET:,}) is spent. Answer from what you have."
    if refusal:
        state.log(d, "delegation_refused", to_agent=to_agent, task=task, reason=refusal)
        return refusal

    d.steps += 1
    handoff = Handoff(from_agent=d.agent, to_agent=to_agent, depth=d.depth + 1, task=task)
    state.handoffs.append(handoff)
    state.log(d, "delegation_start", step=d.steps, to_agent=to_agent, task=audit.clip(task))
    await state.emit("handoff", {"from": d.agent, "to": to_agent, "task": task, "depth": d.depth + 1})
    try:
        report = await run_agent(
            to_agent, task, state,
            depth=d.depth + 1, delegated_by=d.agent, chain=d.chain + (to_agent,), output_type=NativeOutput(AgentReport),
        )
    except Exception as exc:
        handoff.error = f"{type(exc).__name__}: {exc}"
        state.log(d, "delegation_failed", to_agent=to_agent, error=handoff.error)
        await state.emit("handoff_failed", {"from": d.agent, "to": to_agent, "error": handoff.error})
        return f"[{to_agent} could not finish: {handoff.error}]"

    handoff.report = report
    state.log(d, "delegation_end", step=d.steps, to_agent=to_agent, report=report.model_dump())
    await state.emit("handoff_done", {"from": d.agent, "to": to_agent, "report": report.model_dump()})
    return f"[report from {to_agent}]\n{report.model_dump_json(indent=1)}"


async def save_customer_draft(ctx: RunContext[AgentDeps], to: str, subject: str, body: str) -> str:
    """Save a customer message as a DRAFT on the board. Nothing is emailed or sent.

    Args:
        to: The customer or group the message is for (name as it appears on the ticket).
        subject: Short subject line.
        body: The full message text.
    """
    d = ctx.deps
    d.steps += 1
    leaks = internal_leaks(f"{subject}\n{body}")
    if leaks:
        d.state.log(d, "customer_draft_refused", step=d.steps, leaks=leaks)
        return (f"NOT saved: the message contains internal text the customer must not see: {', '.join(leaks)}. "
                "Use plain product names (e.g. 'the white Bulldog tee', 'navy hoodies'), no tool names, SKU codes or "
                "source notes, then save it again.")
    draft = CustomerDraft(ticket_id=d.state.ticket_id, to=to, subject=subject, body=body, drafted_by=d.agent)
    d.state.customer_drafts.append(draft)
    d.state.log(d, "customer_draft_saved", step=d.steps, draft=draft.model_dump())
    await d.state.emit("customer_draft", draft.model_dump())
    return "Draft saved to the board. It has NOT been sent; a human reviews it."


_TOOL_NAMES = sorted({t for tools in AGENT_TOOLS.values() for t in tools} | {"pay", "delegate", "save_customer_draft"})
_SKU = re.compile(r"\bCC-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")


def internal_leaks(text: str) -> list[str]:
    """Tool names and SKU codes are for the team, never for a customer's message."""
    found = [t for t in _TOOL_NAMES if re.search(rf"\b{t}\b", text)]
    return found + sorted(set(_SKU.findall(text)))


_agents: dict[str, Agent] = {}


def get_agent(name: str) -> Agent:
    """Build each agent once: its prompt file, its MCP tools, delegate(), and its output type."""
    if name not in _agents:
        agent = Agent(
            deps_type=AgentDeps,
            output_type=NativeOutput(TicketDecision if name == "boss" else AgentReport),
            instructions=[load_prompt(name), _team_instructions],
            toolsets=[toolset_for(name)],
            retries=2,
            name=name,
        )
        agent.tool(delegate)
        if name == "customer_service":
            agent.tool(save_customer_draft)
        _agents[name] = agent
    return _agents[name]


# ---------- The agent loop ----------

async def run_agent(
    name: AgentName,
    task: str,
    state: RunState,
    *,
    depth: int = 0,
    delegated_by: str | None = None,
    chain: tuple[str, ...] | None = None,
    output_type: type | None = None,
    agent_obj: Agent | None = None,
) -> Any:
    """Run one agent's loop on one task. Each model step is audited as it happens."""
    deps = AgentDeps(state=state, agent=name, depth=depth, delegated_by=delegated_by, chain=chain or (name,))
    state.log(deps, "agent_start", task=audit.clip(task))
    await state.emit("agent_start", {"agent": name, "depth": depth, "delegated_by": delegated_by, "task": task})

    agent = agent_obj or get_agent(name)
    effort = BOSS_EFFORT if name == "boss" else SPECIALIST_EFFORT
    try:
        async with agent.iter(
            task,
            deps=deps,
            model=build_model(),
            model_settings=settings(effort),
            usage_limits=UsageLimits(request_limit=MAX_MODEL_REQUESTS_PER_RUN, tool_calls_limit=MAX_TOOL_CALLS_PER_RUN),
            output_type=output_type,
        ) as run:
            async for node in run:
                if Agent.is_call_tools_node(node):
                    deps.steps += 1
                    resp = node.model_response
                    state.usage.model_requests += 1
                    state.usage.input_tokens += resp.usage.input_tokens or 0
                    state.usage.output_tokens += resp.usage.output_tokens or 0
                    text = " ".join(p.content for p in resp.parts if isinstance(p, TextPart)).strip()
                    calls = [{"tool": p.tool_name, "args": p.args} for p in resp.parts if isinstance(p, ToolCallPart)]
                    state.log(
                        deps, "model_step", step=deps.steps,
                        text=audit.clip(text) or None, tool_calls=calls,
                        input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
                        ticket_tokens_so_far=state.usage.total_tokens,
                    )
                    await state.emit("model_step", {"agent": name, "text": text, "tool_calls": calls})
            output = run.result.output
    except Exception as exc:
        state.log(deps, "agent_error", step=deps.steps, error=f"{type(exc).__name__}: {exc}")
        await state.emit("agent_error", {"agent": name, "error": str(exc)})
        raise

    state.log(deps, "agent_end", step=deps.steps, output=output.model_dump())
    await state.emit("agent_end", {"agent": name, "output": output.model_dump()})
    return output


async def _sync_ticket_status(state: RunState, decision: TicketDecision) -> None:
    """Safety net: the ticket row must match the Boss's final call, even if he forgot update_ticket."""
    from mcp_client import call_tool

    data = await call_tool("get_ticket", {"ticket_id": state.ticket_id})
    current = (data.get("ticket") or {}).get("status")
    if data.get("found") and current != decision.final_status:
        await call_tool("update_ticket", {
            "ticket_id": state.ticket_id,
            "status": decision.final_status,
            "note": f"Run finished: {decision.decision[:300]}",
        })
        state.log(None, "ticket_status_synced", old_status=current, status=decision.final_status)


async def run_ticket(ticket_id: int, emit: Emit = _no_emit, run_id: str | None = None) -> TicketRunResult:
    """The Boss works one ticket from start to finish, delegating as needed."""
    state = RunState(ticket_id=ticket_id, emit_fn=emit)
    if run_id:
        state.run_id = run_id
    state.log(None, "ticket_run_start", limits={
        "max_model_requests_per_run": MAX_MODEL_REQUESTS_PER_RUN,
        "max_tool_calls_per_run": MAX_TOOL_CALLS_PER_RUN,
        "max_delegation_depth": MAX_DELEGATION_DEPTH,
        "max_delegations_per_ticket": MAX_DELEGATIONS_PER_TICKET,
        "ticket_token_budget": TICKET_TOKEN_BUDGET,
    })
    result = TicketRunResult(run_id=state.run_id, ticket_id=ticket_id, model=MODEL_NAME, ok=False, started_at=state.started_at)
    try:
        result.decision = await run_agent(
            "boss",
            f"Work ticket #{ticket_id} from start to finish. Read it with get_ticket first.",
            state,
        )
        result.ok = True
        await _sync_ticket_status(state, result.decision)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    result.handoffs = state.handoffs
    result.tools_used = sorted(set(state.tools_used))
    result.payment_requests = list(state.payment_requests.values())
    result.purchase_orders = list(state.purchase_orders.values())
    result.customer_drafts = state.customer_drafts
    result.usage = state.usage
    result.finished_at = _now()
    state.log(
        None, "ticket_run_end", ok=result.ok, error=result.error,
        decision=result.decision.model_dump() if result.decision else None,
        handoffs=[f"{h.from_agent}->{h.to_agent}" for h in result.handoffs],
        payment_requests=[p.model_dump() for p in result.payment_requests],
        purchase_orders=[p.model_dump() for p in result.purchase_orders],
        customer_drafts=len(result.customer_drafts),
        usage={**result.usage.model_dump(), "total_tokens": result.usage.total_tokens},
    )
    await state.emit("ticket_done", result.model_dump(mode="json"))
    return result


# ---------- Board triage: the Boss suggests which ticket to work first ----------

TRIAGE_TASK = (
    "Triage the board: look at every open ticket and the cash, then rank the tickets in the order we should work them, "
    "using our cash rules. Only look; don't delegate or change anything."
)
_triage_agent: Agent | None = None


def get_triage_agent() -> Agent:
    """The Boss, with his own prompt, but read-only tools and no delegate(): triage only looks."""
    global _triage_agent
    if _triage_agent is None:
        _triage_agent = Agent(
            deps_type=AgentDeps,
            output_type=NativeOutput(TriageResult),
            instructions=load_prompt("boss"),
            toolsets=[triage_toolset()],
            retries=2,
            name="boss_triage",
        )
    return _triage_agent


async def run_triage() -> dict:
    """Run the Boss's triage once. Logged to the audit trail with ticket_id 0 (the whole board)."""
    state = RunState(ticket_id=0)
    state.log(None, "triage_start", task=TRIAGE_TASK)
    try:
        result: TriageResult = await run_agent("boss", TRIAGE_TASK, state, agent_obj=get_triage_agent())
    except Exception as exc:
        state.log(None, "triage_end", ok=False, error=f"{type(exc).__name__}: {exc}")
        raise
    order = sorted(result.order, key=lambda i: i.rank)
    out = {
        "run_id": state.run_id,
        "order": [i.model_dump() for i in order],
        "summary": result.summary,
        "usage": {**state.usage.model_dump(), "total_tokens": state.usage.total_tokens},
        "model": MODEL_NAME,
        "at": _now(),
    }
    state.log(None, "triage_end", ok=True, order=out["order"], summary=out["summary"], usage=out["usage"])
    return out
