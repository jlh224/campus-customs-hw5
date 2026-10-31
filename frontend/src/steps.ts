import { money } from "./money";
import type { Approval, Draft } from "./types";

/** One thing the human has to do: sign/void a check or purchase order, or review a customer draft. */
export interface HumanStep {
  key: string;
  n: number; // 1, 2, 3 ... across the whole board, left to right
  home: number; // the card it lives on (the first ticket in work order that needs it)
  others: number[]; // other tickets that share it
  open: boolean;
  approval?: Approval;
  draft?: Draft;
  after?: number; // checking after this step (checks only)
  covered?: boolean; // false = the pay tool will refuse it
  waitsFor?: number; // step number that must happen first (a PO whose vendor bill is unpaid)
  why: string; // shown on hover: why this step comes here
}

const KIND_ORDER = (a: Approval) => (a.item.kind === "rent" ? 0 : a.type === "payment" ? 1 : 2);

/**
 * Lay every human action out in work order: cards left to right, and on each card
 * rent, then bills, then purchase orders (a vendor won't ship until its bill is paid),
 * then the customer draft. Cash is projected through the open checks in that order.
 */
export function buildHumanSteps(approvals: Approval[], drafts: Draft[], railIds: number[], checking: number | null, today?: string): HumanStep[] {
  const pos = (id: number) => (railIds.indexOf(id) === -1 ? 99 + id : railIds.indexOf(id));
  const home = (ids: number[]) => [...ids].sort((a, b) => pos(a) - pos(b))[0];
  const items: { sortKey: [number, number]; step: Omit<HumanStep, "n" | "why"> }[] = [];
  for (const a of approvals) {
    const h = home(a.ticket_ids);
    items.push({
      sortKey: [pos(h), KIND_ORDER(a)],
      step: { key: a.id, home: h, others: a.ticket_ids.filter((t) => t !== h), open: a.status === "pending" || a.status === "refused", approval: a },
    });
  }
  for (const d of drafts) {
    items.push({ sortKey: [pos(d.ticket_id), 3], step: { key: d.id, home: d.ticket_id, others: [], open: d.status !== "approved", draft: d } });
  }
  items.sort((x, y) => x.sortKey[0] - y.sortKey[0] || x.sortKey[1] - y.sortKey[1]);
  const steps: HumanStep[] = items.map((x, i) => ({ ...x.step, n: i + 1, why: "" }));

  let cash = checking ?? 0;
  for (const s of steps) {
    if (!s.open || !s.approval) continue;
    const after = cash - s.approval.amount;
    s.after = after;
    s.covered = after >= 0;
    if (s.covered) cash = after;
    if (s.approval.type === "purchase_order") {
      const bill = steps.find((b) => b.open && b.approval?.type === "payment" && b.approval.item.kind === "invoice"
        && b.approval.item.payee === s.approval!.item.vendor_name);
      if (bill) s.waitsFor = bill.n;
    }
  }
  for (const s of steps) s.why = whyText(s, steps, today);
  return steps;
}

const BUFFER = 100;

function daysBetween(from: string | undefined, to: string | undefined): number | null {
  if (!from || !to) return null;
  return Math.round((new Date(`${to}T12:00:00`).getTime() - new Date(`${from}T12:00:00`).getTime()) / 86400000);
}

function shortDate(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Plain-English reason this step sits where it does, from the real numbers. */
function whyText(s: HumanStep, steps: HumanStep[], today?: string): string {
  if (s.draft) {
    return `${s.draft.to} is waiting to hear back. Read the draft, fix anything that sounds off, and approve it. It is never emailed; it stays on the board.`;
  }
  const a = s.approval!;
  const it = a.item;
  const tail = s.after === undefined ? "" : s.covered === false ? "" : ` Leaves ${money(s.after)}${s.after < BUFFER ? ", below the $100 buffer" : ", above the $100 buffer"}.`;
  if (a.type === "payment" && it.kind === "rent") {
    const d = daysBetween(today, it.due_date);
    return `Rent comes first: it keeps the shop space. ${money(a.amount)} is due ${shortDate(it.due_date)}${d !== null ? (d >= 0 ? ` (in ${d} day${d === 1 ? "" : "s"})` : ` (${-d} days late)`) : ""}.${tail}`;
  }
  if (a.type === "payment") {
    const d = daysBetween(it.due_date, today);
    const blocked = steps.filter((x) => x.waitsFor === s.n).map((x) => x.n);
    return `${it.overdue && d ? `Overdue ${d} day${d === 1 ? "" : "s"}. ` : ""}${it.payee} won't ship any restock while this bill is open${blocked.length ? `, so it goes before step${blocked.length > 1 ? "s" : ""} ${blocked.join(" and ")}` : ""}.${tail}`;
  }
  if (s.covered === false) {
    return `Not enough cash: after the steps before it, checking would be ${money(s.after ?? 0)}. The pay tool refuses negative balances, so void it (or leave it for when cash comes in).`;
  }
  return `Restocks ${it.qty} \u00d7 ${it.sku} ${it.size} for ticket #${a.ticket_ids.join(", #")}.${s.waitsFor ? ` ${it.vendor_name} ships only after its bill is paid (step ${s.waitsFor}).` : ""}${tail}`;
}
