"""Data types for the Campus Customs agent team.

Agent outputs (AgentReport, TicketDecision) are what the model must return.
Board items (PaymentRequest, PurchaseOrderDraft, CustomerDraft) are built by
the backend from real MCP tool results, so amounts and dates are never typed
by the model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[str, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")
AGENT_TITLES = {
    "boss": "Boss",
    "inventory": "Inventory",
    "accounting": "Accounting",
    "facilities": "Facilities",
    "customer_service": "Customer Service",
}
TicketStatus = Literal["open", "in_progress", "resolved"]


# ---------- What agents return ----------

class AgentReport(BaseModel):
    """A specialist's answer to a delegated task."""

    summary: str = Field(description="One or two sentences: the answer to the task you were given.")
    findings: list[str] = Field(
        default_factory=list,
        description="Facts you checked, each with its number and source tool, e.g. 'CC-TEE-WHITE S qty 0 (check_stock)'.",
    )
    recommendations: list[str] = Field(default_factory=list, description="What you recommend doing next.")
    needs_human: list[str] = Field(
        default_factory=list,
        description="Anything a human must approve or decide (payments, purchase orders, discounts).",
    )


class TicketDecision(BaseModel):
    """The Boss's final call on a ticket."""

    ticket_id: int
    decision: str = Field(description="The final call, in plain words.")
    reasoning: str = Field(description="Why, citing the facts the team found.")
    final_status: TicketStatus = Field(
        description="resolved when the team finished its work (items needing a human signature wait on the board); "
        "in_progress only if the work stopped partway."
    )
    agents_used: list[AgentName] = Field(default_factory=list, description="Agents that worked this ticket.")
    next_steps: list[str] = Field(default_factory=list, description="What happens next, and who does it.")


class TriageItem(BaseModel):
    """One ticket's place in the Boss's suggested order."""

    rank: int = Field(description="1 = work this ticket first.")
    ticket_id: int
    reason: str = Field(description="One short sentence with the real numbers (amount, due date, days overdue).")


class TriageResult(BaseModel):
    """The Boss's suggested order for the open tickets (a recommendation; nothing is changed)."""

    order: list[TriageItem]
    summary: str = Field(description="One line on how far the cash goes, e.g. what's left after rent and the overdue bill.")


# ---------- Items that wait on the board for a human ----------

class PaymentRequest(BaseModel):
    """Built from a prepare_payment result. Only a human can turn this into a payment."""

    kind: Literal["invoice", "rent"]
    ref_id: int
    payee: str
    description: str | None = None
    amount: float
    due_date: str
    overdue: bool
    account: str
    cash_before: float
    cash_after_if_paid: float
    can_afford: bool
    below_buffer: bool = False
    requested_by: AgentName
    status: Literal["awaiting_human_approval", "approved", "rejected", "paid", "refused"] = "awaiting_human_approval"


class PurchaseOrderDraft(BaseModel):
    """Built from a draft_purchase_order result. Nothing is sent to the vendor."""

    vendor_id: int
    vendor_name: str
    sku: str
    size: str
    qty: int
    unit_cost: float
    total_cost: float
    lead_days: int
    can_ship: bool
    earliest_arrival: str | None
    requested_by: AgentName
    status: Literal["draft_needs_human_review", "approved", "rejected"] = "draft_needs_human_review"


class CustomerDraft(BaseModel):
    """A message for a customer. It stays on the board; nothing is emailed."""

    ticket_id: int | None
    to: str
    subject: str
    body: str
    drafted_by: AgentName = "customer_service"
    status: Literal["draft"] = "draft"


# ---------- One ticket run ----------

class Handoff(BaseModel):
    """One agent-to-agent delegation and its result."""

    from_agent: AgentName
    to_agent: AgentName
    depth: int
    task: str
    report: AgentReport | None = None
    error: str | None = None


class UsageTotals(BaseModel):
    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class TicketRunResult(BaseModel):
    run_id: str
    ticket_id: int
    model: str
    ok: bool
    decision: TicketDecision | None = None
    error: str | None = None
    handoffs: list[Handoff] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    payment_requests: list[PaymentRequest] = Field(default_factory=list)
    purchase_orders: list[PurchaseOrderDraft] = Field(default_factory=list)
    customer_drafts: list[CustomerDraft] = Field(default_factory=list)
    usage: UsageTotals = Field(default_factory=UsageTotals)
    started_at: str
    finished_at: str | None = None
