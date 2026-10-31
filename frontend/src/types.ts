export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export const AGENTS: AgentName[] = ["boss", "inventory", "accounting", "facilities", "customer_service"];

export const AGENT_INFO: Record<AgentName, { title: string; role: string; icon: string }> = {
  boss: { title: "Boss", role: "Routes tickets · makes the final call", icon: "🎩" },
  inventory: { title: "Inventory", role: "Stock by SKU & size · restock vendor", icon: "📦" },
  accounting: { title: "Accounting", role: "Cash, invoices, margins · prepares checks", icon: "🧾" },
  facilities: { title: "Facilities", role: "Leases, rent, the shop space", icon: "🔑" },
  customer_service: { title: "Customer Service", role: "Drafts messages (never sent)", icon: "💬" },
};

/** Who the Boss routes each ticket type to (our Problem 5 rule). */
export const OWNER_BY_TYPE: Record<string, AgentName> = {
  customer_order: "inventory",
  rent_notice: "facilities",
  price_override: "accounting",
};

/** The handoffs we expected in Problem 6 (output/desk_tickets.html). */
export const EXPECTED_HANDOFFS: Record<number, [AgentName, AgentName][]> = {
  101: [["boss", "inventory"], ["inventory", "accounting"], ["inventory", "customer_service"]],
  102: [["boss", "facilities"], ["facilities", "accounting"]],
  103: [["boss", "accounting"], ["accounting", "inventory"], ["accounting", "customer_service"]],
};

export type DeskState = "open" | "running" | "in_progress" | "waiting_approval" | "resolved" | "signed";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: string;
  notes: string | null;
  created_at: string;
  is_resolved: boolean;
  is_running: boolean;
  desk_state: DeskState;
  awaiting_signature: boolean;
  drafts_pending: number;
  action_needed: boolean;
  signed_by: string | null;
  open_approvals: number;
  last_run: { run_id: string; status: string; started_at: string; finished_at?: string } | null;
}

export interface AgentReport {
  summary: string;
  findings: string[];
  recommendations: string[];
  needs_human: string[];
}

export interface Handoff {
  from_agent: AgentName;
  to_agent: AgentName;
  depth: number;
  task: string;
  report: AgentReport | null;
  error: string | null;
}

export interface TicketDecision {
  ticket_id: number;
  decision: string;
  reasoning: string;
  final_status: string;
  agents_used: AgentName[];
  next_steps: string[];
}

export interface RunResult {
  run_id: string;
  ticket_id: number;
  ok: boolean;
  error: string | null;
  decision: TicketDecision | null;
  handoffs: Handoff[];
  tools_used: string[];
  usage: { model_requests: number; input_tokens: number; output_tokens: number };
}

export interface RunInfo {
  run_id: string;
  status: "running" | "done" | "error";
  started_at: string;
  finished_at?: string;
  result: RunResult | null;
  signed_by?: string;
}

export interface Approval {
  id: string;
  type: "payment" | "purchase_order";
  ticket_ids: number[];
  run_id: string;
  status: "pending" | "refused" | "paid" | "rejected";
  title: string;
  amount: number;
  item: Record<string, any>;
  decided_by?: string;
  decided_at?: string;
  outcome?: Record<string, any> | null;
  note?: string | null;
}

export interface Draft {
  id: string;
  ticket_id: number;
  to: string;
  subject: string;
  body: string;
  drafted_by: AgentName;
  run_id: string;
  status: "draft" | "approved";
  approved_by?: string;
  edited?: boolean;
  original_body?: string;
}

export interface AuditEvent {
  seq: number;
  ts: string;
  event: string;
  summary: string;
  run_id?: string;
  ticket_id?: number;
  agent?: AgentName | null;
  delegated_by?: AgentName | null;
  depth?: number;
  text?: string | null;
  tool_calls?: { tool: string; args: unknown }[];
  tool?: string;
  args?: unknown;
  to_agent?: AgentName;
  task?: string;
  report?: AgentReport;
  output?: Record<string, any>;
  draft?: Draft;
  error?: string;
  reason?: string;
  ok?: boolean;
  status?: string;
  approval_id?: string;
  decided_by?: string;
}

export interface TicketDetail {
  ticket: Ticket;
  run: RunInfo | null;
  approvals: Approval[];
  drafts: Draft[];
}

export interface Triage {
  run_id: string;
  order: { rank: number; ticket_id: number; reason: string }[];
  summary: string;
  usage: { total_tokens: number; model_requests: number };
  at: string;
}

export interface BoardRun {
  state: "idle" | "running" | "done" | "error";
  order: number[];
  current: number | "triage" | null;
  finished: number[];
  error: string | null;
}
