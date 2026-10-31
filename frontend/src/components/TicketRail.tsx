import { useState } from "react";
import type React from "react";
import { Dan } from "./Dan";
import { AgentStrip, TicketArt } from "./TicketArt";
import { money } from "../money";
import type { HumanStep } from "../steps";
import { OWNER_BY_TYPE, type AuditEvent, type BoardRun, type Draft, type Ticket, type Triage } from "../types";

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

/** The inked rubber stamp. Green "SIGNED" only when nothing at all is left for a human. */
export function Stamp({ ticket, fresh }: { ticket: Ticket; fresh: boolean }) {
  const owner = OWNER_BY_TYPE[ticket.type];
  if (ticket.desk_state === "signed") {
    return (
      <div className={`stamp stamp-signed ${fresh ? "stamp-fresh" : ""}`}>
        <Dan outfit="boss" mono size={34} />
        <div>
          <div className="stamp-word">ALL DONE</div>
          <div className="stamp-sub">by {ticket.signed_by}</div>
        </div>
      </div>
    );
  }
  if (ticket.desk_state === "resolved") {
    return (
      <div className={`stamp stamp-resolved ${fresh ? "stamp-fresh" : ""}`}>
        <Dan outfit={owner} mono size={34} />
        <div>
          <div className="stamp-word">RESOLVED</div>
          <div className="stamp-sub">{ticket.action_needed ? "your action needed" : "nothing waiting"}</div>
        </div>
      </div>
    );
  }
  return null;
}

const BUFFER = 100;

/** One numbered thing for the human to do, shown on the card it belongs to. */
function StepToken({ s, next, waiting, signer, busy, onSign, onVoid, onReviewDraft, onUndoDraft }: {
  s: HumanStep; next: boolean; waiting: boolean; signer: string; busy: boolean;
  onSign: (s: HumanStep) => void; onVoid: (s: HumanStep) => void; onReviewDraft: (d: Draft) => void; onUndoDraft: (d: Draft) => void;
}) {
  const stop = (fn: () => void) => (e: React.MouseEvent) => { e.stopPropagation(); fn(); };
  const a = s.approval;
  const label = s.draft ? <>Review draft to {s.draft.to}</>
    : a!.type === "purchase_order" ? <>Restock {a!.item.qty} × {a!.item.sku} {a!.item.size}</>
    : a!.item.kind === "rent" ? <>Pay rent</> : <>Pay invoice #{a!.item.ref_id}</>;
  const done = !s.open;
  const doneTag = s.draft ? "APPROVED" : a!.status === "paid" ? "PAID" : "VOID";
  return (
    <li tabIndex={done ? -1 : 0} className={`tok ${done ? "tok-done" : ""} ${next ? "tok-next" : ""} ${s.covered === false ? "tok-short" : ""} ${s.draft ? "tok-draft" : ""}`}
      onClick={(e) => e.stopPropagation()}>
      <span className="tok-n">{done ? "✓" : s.n}</span>
      <span className="tok-main">
        <span className="tok-label">
          {label}
          {a && <b className="tok-amt"> {money(a.amount)}</b>}
          {s.others.length > 0 && <span className="tok-also"> · also #{s.others.join(", #")}</span>}
        </span>
        {!done && a && s.after !== undefined && (
          <span className={`tok-after ${s.covered === false ? "bad" : s.after < BUFFER ? "warn" : ""}`}>
            {s.covered === false ? `not enough cash (${money(s.after)}): void it` : `→ ${money(s.after)} left`}
            {s.waitsFor && ` · after step ${s.waitsFor}`}
          </span>
        )}
      </span>
      {done ? (
        <span className="tok-donebox">
          <span className={`tok-tag ${doneTag === "VOID" ? "tok-void" : ""}`}>{doneTag}</span>
          {s.draft && <button className="tok-undo" disabled={busy} onClick={stop(() => onUndoDraft(s.draft!))} title="Undo the approval (the draft was never sent)">↶ undo</button>}
        </span>
      ) : waiting ? (
        <span className="tok-later">after the Boss</span>
      ) : s.draft ? (
        <button className="action-btn tok-btn" onClick={stop(() => onReviewDraft(s.draft!))}>✉ Review</button>
      ) : (
        <span className="tok-actions">
          <button className={`btn ${next ? "action-btn" : "btn-primary"} tok-btn`} disabled={busy || !signer.trim()} title={signer.trim() ? "" : "Type your name next to “Signing as” first"}
            onClick={stop(() => onSign(s))}>Sign</button>
          <button className="btn btn-ghost tok-btn" disabled={busy || !signer.trim()} onClick={stop(() => onVoid(s))}>Void</button>
        </span>
      )}
      {next && <span className="tok-here">START HERE</span>}
      {!done && <span className="tok-why" role="tooltip"><b>Why step {s.n}?</b> {s.why}</span>}
    </li>
  );
}

/** Order the cards: the human's override wins, then the Boss's order, then ticket number. */
export function railOrder(tickets: Ticket[], triage: Triage | null, manual: number[] | null): Ticket[] {
  const pos = (id: number) => {
    if (manual?.includes(id)) return manual.indexOf(id);
    const r = triage?.order.find((o) => o.ticket_id === id)?.rank;
    return r !== undefined ? 100 + r : 1000 + id;
  };
  return [...tickets].sort((a, b) => pos(a.id) - pos(b.id));
}

export function TicketRail({
  tickets, events, triage, manualOrder, boardRun, steps, signer, onSigner, onSign, onVoid, busy, waiting, ready,
  onRunBoard, onReorder, onReviewDraft, onUndoDraft, selectedId, runningId, freshStamps, onSelect, onRun,
}: {
  tickets: Ticket[];
  events: AuditEvent[];
  steps: HumanStep[];
  signer: string;
  onSigner: (v: string) => void;
  onSign: (s: HumanStep) => void;
  onVoid: (s: HumanStep) => void;
  busy: boolean;
  waiting: boolean; // the Boss is still working: steps are lining up, not your turn yet
  ready: boolean; // the Boss just finished: make step 1 pop
  triage: Triage | null;
  manualOrder: number[] | null;
  boardRun: BoardRun | null;
  onRunBoard: () => void;
  onReorder: (order: number[]) => void;
  onReviewDraft: (d: Draft) => void;
  onUndoDraft: (d: Draft) => void;
  selectedId: number | null;
  runningId: number | null;
  freshStamps: Set<number>;
  onSelect: (id: number) => void;
  onRun: (id: number) => void;
}) {
  const [noteFor, setNoteFor] = useState<number | null>(null);
  const [dragId, setDragId] = useState<number | null>(null);
  const [dropOn, setDropOn] = useState<number | null>(null);
  const boardBusy = boardRun?.state === "running";
  const openCount = tickets.filter((t) => t.desk_state === "open" || t.desk_state === "in_progress").length;
  const canReorder = !boardBusy && runningId === null && openCount > 0;
  const ordered = railOrder(tickets, triage, manualOrder);
  const nextKey = waiting ? undefined : steps.find((s) => s.open)?.key;
  const openSteps = steps.filter((s) => s.open).length;

  function drop(targetId: number) {
    if (dragId === null || dragId === targetId) return;
    const ids = ordered.map((t) => t.id).filter((id) => id !== dragId);
    ids.splice(ids.indexOf(targetId), 0, dragId);
    onReorder(ids);
  }

  return (
    <section className="ticket-rail">
      <div className="rail-head">
        <h2 className="panel-title">Ticket rail</h2>
        <span className={`rail-hint ${ready ? "rail-ready" : ""}`}>
          {waiting ? "The Boss is working through the board…"
            : openSteps > 0 ? `Your turn: ${openSteps} step${openSteps > 1 ? "s" : ""}, left to right →`
            : canReorder ? <><b className="drag-hint">⠿ Drag the cards</b> to change the order, or let the Boss decide.</>
            : steps.length > 0 ? "All done ✓" : "The Boss picks the order and works every ticket; you sign at the end."}
        </span>
        {openSteps > 0 && !waiting && (
          <label className="rail-signer">Signing as
            <input className="signature" value={signer} placeholder="Your name" onChange={(e) => onSigner(e.target.value)} />
          </label>
        )}
        <button className="btn btn-primary run-board-btn" onClick={onRunBoard} disabled={boardBusy || runningId !== null || openCount === 0}>
          <Dan outfit="boss" size={24} />
          {boardBusy
            ? boardRun?.current === "triage" ? "The Boss is deciding the order…" : `The Boss is working ticket #${boardRun?.current}…`
            : openCount === 0 ? "Board is done" : "▶ Let the Boss run the board"}
        </button>
      </div>
      <div className={`rail ${selectedId !== null ? "rail-has-selection" : ""} ${openSteps > 0 && !waiting ? "rail-flow" : ""}`}>
        {tickets.length === 0 && <p className="hint">Waiting for the backend at localhost:8000…</p>}
        {ordered.map((t, idx) => {
          const selected = t.id === selectedId;
          const running = t.id === runningId;
          const done = t.desk_state === "resolved" || t.desk_state === "signed";
          const runId = t.last_run?.run_id;
          const runEvents = runId ? events.filter((e) => e.run_id === runId) : [];
          const why = triage?.order.find((o) => o.ticket_id === t.id);
          const overridden = manualOrder?.includes(t.id) ?? false;
          const mySteps = steps.filter((s) => s.home === t.id);
          const hasNext = mySteps.some((s) => s.key === nextKey);
          const stop = (fn: () => void) => (e: React.MouseEvent) => { e.stopPropagation(); fn(); };
          return (
            <article
              key={t.id}
              className={`slip slip-${t.type} ${selected ? "slip-selected" : ""} ${running ? "slip-running" : ""} ${t.action_needed ? "slip-action" : ""} ${t.desk_state === "signed" ? "slip-done" : ""} ${dropOn === t.id ? "slip-drop" : ""} ${canReorder ? "slip-draggable" : ""} ${hasNext ? "slip-next" : ""}`}
              onClick={() => onSelect(t.id)}
              draggable={canReorder}
              onDragStart={() => setDragId(t.id)}
              onDragEnd={() => { setDragId(null); setDropOn(null); }}
              onDragOver={(e) => { if (dragId !== null) { e.preventDefault(); setDropOn(t.id); } }}
              onDragLeave={() => setDropOn((d) => (d === t.id ? null : d))}
              onDrop={(e) => { e.preventDefault(); drop(t.id); setDropOn(null); }}
            >
              <div className="slip-top">
                <span className="slip-no">
                  {canReorder && <span className="grip" title="Drag to reorder">⠿</span>}
                  {(why || overridden) && <span className="rank-badge" title="Work order">{idx + 1}</span>}
                  #{t.id}
                </span>
                <span className="slip-tags">
                  {selected && <span className="viewing-tag">Viewing in log</span>}
                  <span className="slip-type">{TYPE_LABEL[t.type] ?? t.type}</span>
                  {(why || overridden) && (
                    <button className={`note-btn ${noteFor === t.id ? "note-on" : ""}`} title="Why this order?"
                      onClick={stop(() => setNoteFor(noteFor === t.id ? null : t.id))}>📝</button>
                  )}
                </span>
              </div>
              {noteFor === t.id && (
                <div className="sticky" onClick={(e) => e.stopPropagation()}>
                  <b>{overridden ? `#${idx + 1}: your order` : `#${idx + 1}: the Boss's call`}</b>
                  {why && <span>{why.reason}</span>}
                  {overridden && why && <span className="sticky-sub">The Boss had it at #{why.rank}.</span>}
                </div>
              )}
              <div className="slip-subject">{t.subject} <span className="slip-from">· {t.requester}</span></div>
              <div className="slip-notes">“{(t.notes ?? "").split("\n")[0]}”</div>
              <TicketArt ticket={t} />
              <AgentStrip ticketId={t.id} events={runEvents} />
              <div className="slip-foot">
                <span className={`status-dot status-${t.desk_state}`}>
                  {running ? "agents working…" : t.action_needed ? "action needed" : t.desk_state === "signed" ? "all done" : t.desk_state.replace("_", " ")}
                </span>
              </div>
              {mySteps.length > 0 && (
                <ol className="tokens">
                  {mySteps.map((s) => (
                    <StepToken key={s.key} s={s} next={s.key === nextKey} waiting={waiting} signer={signer} busy={busy}
                      onSign={onSign} onVoid={onVoid} onReviewDraft={onReviewDraft} onUndoDraft={onUndoDraft} />
                  ))}
                </ol>
              )}
              {!done && !running && (
                <button
                  className="manual-run"
                  disabled={runningId !== null || boardBusy}
                  title="Manual option. The usual way is “Let the Boss run the board.”"
                  onClick={stop(() => onRun(t.id))}
                >
                  or run just this ticket
                </button>
              )}
              {running && <div className="slip-progress"><span /></div>}
              <Stamp ticket={t} fresh={freshStamps.has(t.id)} />
            </article>
          );
        })}
      </div>
    </section>
  );
}
