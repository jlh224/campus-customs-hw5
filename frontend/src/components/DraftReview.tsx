import { useEffect, useState } from "react";
import { toolLabel } from "../labels";
import { money } from "../money";
import { AGENT_INFO, type AuditEvent, type Draft, type Ticket } from "../types";

/** One line of plain facts from a tool result, so the reviewer sees what the agents actually looked up. */
function fact(tool: string, raw: unknown): string | null {
  let r: any = raw;
  try {
    if (typeof raw === "string") r = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!r || typeof r !== "object") return null;
  switch (tool) {
    case "check_stock":
      return r.found ? `${r.name}: ${r.sizes.map((s: any) => `${s.size} ${s.qty}`).join(", ")} on hand` : null;
    case "get_pricing":
      return r.found ? `${r.sku}: cost ${money(r.unit_cost)}, list ${money(r.list_price)}` + (r.offer ? `; offer ${money(r.offer.unit_price)} (${r.offer.discount_pct}% off)` : "") : null;
    case "get_vendor_status":
      return r.vendors?.map((v: any) => `${v.name}: ${v.can_ship ? "can ship" : "can't ship (open invoice)"}, ${v.lead_days}-day lead`).join("; ") ?? null;
    case "draft_purchase_order":
      return r.drafted ? `Restock draft: ${r.qty} × ${r.sku} ${r.size} = ${money(r.total_cost)}${r.earliest_arrival ? `, earliest ${r.earliest_arrival}` : ", vendor blocked"}` : null;
    case "prepare_payment":
      return r.prepared ? `Check prepared: ${money(r.amount)} to ${r.payee}` : null;
    case "get_ticket":
      return null;
    default:
      return null;
  }
}

/**
 * Human-in-the-loop review of a customer draft. Left: the message (editable).
 * Right: what the agents actually used. "Approve" keeps it on the board; nothing is emailed.
 */
export function DraftReview({ draft, ticket, events, signer, onSigner, onApprove, onUndo, onClose, busy }: {
  draft: Draft;
  ticket: Ticket | undefined;
  events: AuditEvent[]; // the ticket's run
  signer: string;
  onSigner: (v: string) => void;
  onApprove: (body: string) => void;
  onUndo: (d: Draft) => void;
  onClose: () => void;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(draft.body);
  const approved = draft.status === "approved";
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const brief = events.find((e) => e.event === "delegation_start" && e.to_agent === "customer_service");
  const facts: { label: string; text: string }[] = [];
  const seen = new Set<string>();
  for (const e of events) {
    if (e.event !== "tool_result" || !e.tool) continue;
    const f = fact(e.tool, (e as any).result);
    if (f && !seen.has(f)) {
      seen.add(f);
      facts.push({ label: `${AGENT_INFO[e.agent as keyof typeof AGENT_INFO]?.title ?? ""} · ${toolLabel(e.tool, null).split(" · ")[0]}`, text: f });
    }
  }

  return (
    <div className="review-back" onClick={onClose}>
      <div className="review" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={`Review draft for ticket ${draft.ticket_id}`}>
        <header className="review-head">
          <div>
            <div className="review-kicker">Review customer draft · Ticket #{draft.ticket_id}</div>
            <div className="review-meta"><span>To</span> <b>{draft.to}</b> <span className="muted">(no email on file; this message is never sent)</span></div>
            <div className="review-meta"><span>Subject</span> <b>{draft.subject}</b></div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </header>

        <div className="review-panes">
          <section className="review-left">
            <div className="pane-title">The draft {approved && <span className="ok-pill">approved by {draft.approved_by}{draft.edited ? " · edited" : ""}</span>}</div>
            {editing ? (
              <textarea className="review-text" value={text} onChange={(e) => setText(e.target.value)} autoFocus />
            ) : (
              <div className="review-body">{text}</div>
            )}
            <div className="review-foot">Drafted by {AGENT_INFO[draft.drafted_by]?.title}.</div>
          </section>
          <aside className="review-right">
            <div className="pane-title">What the agents used</div>
            <div className="src">
              <div className="src-label">The request (ticket #{draft.ticket_id})</div>
              <div>“{(ticket?.notes ?? "").split("\n")[0]}” · from {ticket?.requester}</div>
            </div>
            {brief && (
              <div className="src">
                <div className="src-label">Note to Customer Service from {AGENT_INFO[brief.agent as keyof typeof AGENT_INFO]?.title}</div>
                <div className="src-quote">{brief.task}</div>
              </div>
            )}
            {facts.length > 0 && (
              <div className="src">
                <div className="src-label">Facts the team checked (from the shop database)</div>
                <ul>{facts.map((f, i) => <li key={i}>{f.text}</li>)}</ul>
              </div>
            )}
          </aside>
        </div>

        <footer className="review-actions">
          {!approved && (
            <button className="btn btn-ghost" onClick={() => setEditing(!editing)}>{editing ? "✓ Done editing" : "✎ Edit draft text"}</button>
          )}
          <span className="review-note">Approving keeps it on the board for you to send yourself. Nothing is emailed.</span>
          {!approved ? (
            <>
              <input className="signature review-sign" value={signer} placeholder="Your name" onChange={(e) => onSigner(e.target.value)} />
              <button className="action-btn action-lg" disabled={busy || !signer.trim()} onClick={() => onApprove(text)}>✓ Approve draft</button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost" disabled={busy} onClick={() => onUndo(draft)}>↶ Undo approval</button>
              <button className="btn btn-primary" onClick={onClose}>Back to the desk</button>
            </>
          )}
        </footer>
      </div>
    </div>
  );
}
