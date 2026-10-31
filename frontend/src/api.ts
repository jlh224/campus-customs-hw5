import type { Approval, AuditEvent, BoardRun, Draft, Ticket, TicketDetail, Triage } from "./types";

/** The FastAPI backend from Problem 7. */
export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
  return body as T;
}

export const api = {
  tickets: () => request<{ date_today: string; tickets: Ticket[]; manual_order: number[] | null }>("/api/tickets"),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),
  run: (id: number) => request<{ started: boolean; run_id: string }>(`/api/tickets/${id}/run`, { method: "POST" }),
  events: (since: number) =>
    request<{ events: AuditEvent[]; last_seq: number; running: boolean; running_ticket: number | null }>(
      `/api/events?since=${since}&limit=1000`,
    ),
  approvals: () => request<{ approvals: Approval[] }>("/api/approvals"),
  approve: (id: string, approvedBy: string) =>
    request<{ paid: boolean; message?: string; approval: Approval; tickets_signed: number[] }>(
      `/api/approvals/${id}/approve`,
      { method: "POST", body: JSON.stringify({ approved_by: approvedBy }) },
    ),
  reject: (id: string, decidedBy: string, reason: string) =>
    request<{ approval: Approval; tickets_signed: number[] }>(`/api/approvals/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ decided_by: decidedBy, reason }),
    }),
  drafts: () => request<{ drafts: Draft[] }>("/api/drafts"),
  approveDraft: (id: string, approvedBy: string, body: string) =>
    request<{ draft: Draft; tickets_signed: number[] }>(`/api/drafts/${id}/approve`, {
      method: "POST", body: JSON.stringify({ approved_by: approvedBy, body }),
    }),
  unapproveDraft: (id: string, by: string) =>
    request<{ draft: Draft }>(`/api/drafts/${id}/unapprove`, { method: "POST", body: JSON.stringify({ by }) }),
  setOrder: (order: number[] | null) => request<{ manual_order: number[] | null }>("/api/order", { method: "PUT", body: JSON.stringify({ order }) }),
  cash: () => request<{ checking: number; as_of: string }>("/api/cash"),
  reset: () => request<{ reset: boolean; message: string }>("/api/reset", { method: "POST" }),
  triage: () => request<{ triage: Triage | null }>("/api/triage"),
  askTriage: () => request<{ triage: Triage }>("/api/triage", { method: "POST" }),
  boardRun: () => request<{ board_run: BoardRun; running_ticket: number | null }>("/api/run-board"),
  runBoard: () => request<{ started: boolean }>("/api/run-board", { method: "POST" }),
};
