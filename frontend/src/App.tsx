import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { TicketRail, railOrder } from "./components/TicketRail";
import { Dan } from "./components/Dan";
import { DraftReview } from "./components/DraftReview";
import { ShiftReports } from "./components/Reports";
import { CashCounter } from "./components/Till";
import { Transcript } from "./components/Transcript";
import { shopDate } from "./money";
import { isMuted, setMuted, sounds } from "./sound";
import { buildHumanSteps, type HumanStep } from "./steps";
import {
  type BoardRun,
  type Triage,
  type Approval, type AuditEvent, type DeskState, type Draft, type Ticket, type TicketDetail,
} from "./types";

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [dateToday, setDateToday] = useState<string>();
  const [checking, setChecking] = useState<number | null>(null);
  // Optional deep link: ?ticket=101&tab=summary opens the desk on that ticket (used for the resolved-board screenshots).
  const params = new URLSearchParams(window.location.search);
  const [logTab, setLogTab] = useState<"log" | "summary">(params.get("tab") === "summary" ? "summary" : "log");
  const [triage, setTriage] = useState<Triage | null>(null);
  const [manualOrder, setManualOrder] = useState<number[] | null>(null);
  const [boardRun, setBoardRun] = useState<BoardRun | null>(null);
  const [ready, setReady] = useState(false); // the Boss just finished: make step 1 pop
  const railRef = useRef<HTMLDivElement>(null);
  const prevBoardState = useRef<string | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [runningTicket, setRunningTicket] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(params.get("ticket") ? Number(params.get("ticket")) : null);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [offline, setOffline] = useState(false);
  const [muted, setMutedState] = useState(isMuted());
  const [night, setNight] = useState(localStorage.getItem("desk-night") === "1");
  const [signer, setSigner] = useState(localStorage.getItem("desk-signer") ?? "");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [freshStamps, setFreshStamps] = useState<Set<number>>(new Set());
  const [reviewing, setReviewing] = useState<Draft | null>(null);

  const lastSeq = useRef(0);
  const loaded = useRef(false);
  const inflight = useRef(false);
  const firstSeq = useRef<number | null>(null); // events at or below this were already on the desk at load
  const prevStates = useRef<Record<number, DeskState>>({});
  const selectedRef = useRef<number | null>(null);
  selectedRef.current = selectedId;

  // Every human action, in work order: cards left to right, each card top to bottom.
  const railIds = useMemo(() => railOrder(tickets, triage, manualOrder).map((t) => t.id), [tickets, triage, manualOrder]);
  const steps = useMemo(() => buildHumanSteps(approvals, drafts, railIds, checking, dateToday), [approvals, drafts, railIds, checking, dateToday]);
  const openSteps = steps.filter((s) => s.open).length;

  useEffect(() => {
    document.title = openSteps ? `(${openSteps}) to do · Campus Customs` : "Campus Customs · Back Office Desk";
  }, [openSteps]);

  useEffect(() => {
    document.documentElement.dataset.theme = night ? "night" : "day";
    localStorage.setItem("desk-night", night ? "1" : "0");
  }, [night]);

  const flash = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4200);
  };

  const refresh = useCallback(async () => {
    if (inflight.current) return;
    inflight.current = true;
    try {
      const [t, c, ap, dr, ev] = await Promise.all([
        api.tickets(), api.cash(), api.approvals(), api.drafts(), api.events(lastSeq.current),
      ]);
      api.triage().then((r) => setTriage(r.triage)).catch(() => undefined);
      api.boardRun().then((r) => {
        const b = r.board_run;
        // The Boss just finished the board: tell the human it's their turn, and where to start.
        if (prevBoardState.current === "running" && b.state === "done") {
          const n = ap.approvals.filter((a) => a.status === "pending" || a.status === "refused").length
            + dr.drafts.filter((d) => d.status !== "approved").length;
          sounds.signed();
          flash(n ? `The Boss is done. Your turn: ${n} step${n > 1 ? "s" : ""}, start at ① and go left to right.` : "The Boss is done. Nothing needs you.");
          setReady(true);
          setTimeout(() => setReady(false), 7000);
          setTimeout(() => railRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 400);
        }
        prevBoardState.current = b.state;
        setBoardRun(b);
      }).catch(() => undefined);
      setOffline(false);
      setTickets(t.tickets);
      setManualOrder(t.manual_order);
      setDateToday(t.date_today);
      setChecking(c.checking);
      setApprovals(ap.approvals);
      setDrafts(dr.drafts);
      // Deep link ?review=<draft id> opens that draft's review once (used for screenshots).
      if (!loaded.current && params.get("review")) {
        const d = dr.drafts.find((x) => x.id === params.get("review"));
        if (d) setReviewing(d);
      }
      setRunningTicket(ev.running_ticket);

      // New events: a paper-slide sound per handoff; the note slides down the arrow in the ticket's flow tree.
      if (firstSeq.current === null) {
        firstSeq.current = ev.last_seq;
      }
      if (ev.events.length) {
        lastSeq.current = ev.last_seq;
        setEvents((old) => [...old, ...ev.events.filter((e) => !old.some((o) => o.seq === e.seq))].slice(-3000));
        if (loaded.current) {
          const handoffs = ev.events.filter(
            (e) => e.event === "delegation_start" && e.agent && e.to_agent && e.seq > (firstSeq.current ?? 0),
          );
          handoffs.forEach((_e, i) => setTimeout(() => sounds.slide(), i * 650));
        }
      }

      // Stamp + sound when a ticket turns resolved or all done.
      for (const tk of t.tickets) {
        const before = prevStates.current[tk.id];
        if (loaded.current && before && before !== tk.desk_state) {
          if (tk.desk_state === "resolved") {
            sounds.resolved();
            if (before === "running") {
              setSelectedId(tk.id);
              setLogTab("summary");
            }
          }
          if (tk.desk_state === "signed") sounds.signed();
          if (tk.desk_state === "resolved" || tk.desk_state === "signed") {
            setFreshStamps((s) => new Set(s).add(tk.id));
            setTimeout(() => setFreshStamps((s) => { const n = new Set(s); n.delete(tk.id); return n; }), 1400);
          }
        }
        prevStates.current[tk.id] = tk.desk_state;
      }
      if (ev.running_ticket !== null && selectedRef.current !== ev.running_ticket) setSelectedId(ev.running_ticket);
      if (selectedRef.current === null && t.tickets.length) setSelectedId(t.tickets[0].id);
      loaded.current = true;

      const sel = ev.running_ticket ?? selectedRef.current ?? t.tickets[0]?.id;
      if (sel) setDetail(await api.ticket(sel));
    } catch {
      setOffline(true);
    } finally {
      inflight.current = false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll quickly while agents are working, slowly otherwise.
  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const loop = async () => {
      await refresh();
      if (!stop) timer = setTimeout(loop, runningTicket !== null ? 900 : 3500);
    };
    void loop();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [refresh, runningTicket]);

  useEffect(() => {
    if (selectedId !== null) api.ticket(selectedId).then(setDetail).catch(() => undefined);
  }, [selectedId]);

  const selected = tickets.find((t) => t.id === selectedId) ?? null;
  const viewRunId = selected?.last_run?.run_id;
  const viewEvents = useMemo(() => {
    if (!viewRunId) return [];
    // Human sign/void lines count only if they came after this ticket's current run started.
    const runStart = events.find((e) => e.run_id === viewRunId && e.event === "ticket_run_start")?.seq ?? Infinity;
    return events.filter((e) => e.run_id === viewRunId ||
      (e.event === "approval_decided" && e.seq > runStart && ((e as any).ticket_ids ?? []).includes(selectedId)));
  }, [events, viewRunId, selectedId]);
  const isRunning = runningTicket !== null;
  const waiting = boardRun?.state === "running" || isRunning;
  const date = shopDate(dateToday);
  const runResult = detail?.ticket.id === selectedId && detail?.run?.status !== "running" ? detail?.run?.result ?? null : null;
  const why = selected ? triage?.order.find((o) => o.ticket_id === selected.id) : undefined;
  const reviewTicket = tickets.find((t) => t.id === reviewing?.ticket_id);
  const reviewEvents = reviewTicket?.last_run ? events.filter((e) => e.run_id === reviewTicket.last_run!.run_id) : [];

  async function runBoard() {
    try {
      await api.runBoard();
      setLogTab("log");
      prevBoardState.current = "running";
      setBoardRun((b) => ({ ...(b ?? { order: [], finished: [], error: null }), state: "running", current: "triage" }));
      sounds.slide();
      flash("The Boss is deciding the order, then working every ticket. You'll be told when it's your turn.");
      void refresh();
    } catch (e) {
      flash(String((e as Error).message));
    }
  }

  async function reorder(order: number[]) {
    setManualOrder(order);
    flash(`Recalculating… the Boss will work #${order.join(" → #")}.`);
    sounds.slide();
    try {
      await api.setOrder(order);
    } catch (e) {
      flash(String((e as Error).message));
    }
    void refresh();
  }

  async function startRun(id: number) {
    setSelectedId(id);
    setLogTab("log");
    try {
      await api.run(id);
      sounds.slide();
      setRunningTicket(id);
      void refresh();
    } catch (e) {
      flash(String((e as Error).message));
    }
  }

  async function sign(s: HumanStep) {
    const a = s.approval!;
    localStorage.setItem("desk-signer", signer);
    setBusy(true);
    try {
      const r = await api.approve(a.id, signer.trim());
      if (r.paid) {
        sounds.kaching();
        flash(`Step ${s.n} done: paid ${a.title}`);
      } else {
        sounds.thud();
        flash(r.message ?? "The pay tool refused this check.");
      }
    } catch (e) {
      sounds.thud();
      flash(String((e as Error).message));
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  async function voidCheck(s: HumanStep) {
    const a = s.approval!;
    setBusy(true);
    try {
      await api.reject(a.id, signer.trim(), "Voided at the desk");
      flash(`Step ${s.n} done: voided ${a.title}`);
    } catch (e) {
      flash(String((e as Error).message));
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  async function approveDraft(body: string) {
    if (!reviewing) return;
    localStorage.setItem("desk-signer", signer);
    setBusy(true);
    try {
      await api.approveDraft(reviewing.id, signer.trim(), body);
      sounds.signed();
      flash(`Draft to ${reviewing.to} approved. It stays on the board; nothing was emailed.`);
      setReviewing(null);
    } catch (e) {
      flash(String((e as Error).message));
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  async function undoDraft(d: Draft) {
    setBusy(true);
    try {
      await api.unapproveDraft(d.id, signer.trim() || "human");
      sounds.thud();
      flash(`Approval undone: the draft to ${d.to} is back in your steps.`);
      setReviewing((r) => (r && r.id === d.id ? { ...r, status: "draft" } : r));
    } catch (e) {
      flash(String((e as Error).message));
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  async function resetDesk() {
    if (!window.confirm("Reset the shop database to the original values and clear the board? (The audit trail is kept.)")) return;
    try {
      await api.reset();
      prevStates.current = {};
      flash("Fresh start: database restored, board cleared.");
      void refresh();
    } catch (e) {
      flash(String((e as Error).message));
    }
  }

  return (
    <div className="desk">
      <header className="topbar">
        <div className="brand">
          <Dan badge size={50} />
          <div>
            <h1>Campus Customs</h1>
            <div className="brand-sub">Chapel Street · New Haven</div>
          </div>
          <span className="pennant">Back office</span>
        </div>
        <div className="topbar-right">
          <CashCounter checking={checking} />
          <div className="calendar" title="The shop's date (desk.date_today), not today's">
            <span className="cal-month">{date.month}</span>
            <span className="cal-day">{date.day}</span>
            <span className="cal-year">{date.weekday} · {date.year}</span>
          </div>
          <button className="icon-btn" onClick={() => { setMuted(!muted); setMutedState(!muted); }} title={muted ? "Sounds off" : "Sounds on"}>
            {muted ? "🔕" : "🔔"}
          </button>
          <button className={`icon-btn lamp-btn ${night ? "lamp-on" : ""}`} onClick={() => setNight(!night)} title="Desk lamp: night shift">
            💡
          </button>
          <button className="btn btn-ghost" onClick={resetDesk} disabled={isRunning}>Reset desk</button>
        </div>
      </header>

      {offline && <div className="offline">Can't reach the backend at http://localhost:8000. Start it from backend/ with <code>uvicorn main:app --reload --port 8000</code>.</div>}

      <div ref={railRef}>
        <TicketRail
          tickets={tickets}
          events={events}
          selectedId={selectedId}
          runningId={runningTicket}
          freshStamps={freshStamps}
          onSelect={setSelectedId}
          onRun={startRun}

          triage={triage}
          manualOrder={manualOrder}
          boardRun={boardRun}
          steps={steps}
          signer={signer}
          onSigner={setSigner}
          onSign={sign}
          onVoid={voidCheck}
          busy={busy}
          waiting={waiting}
          ready={ready}
          onRunBoard={runBoard}
          onReorder={reorder}
          onReviewDraft={setReviewing}
          onUndoDraft={undoDraft}
        />
      </div>

      <main className={`layout layout-single ${selected ? `viewing-${selected.type}` : ""}`}>
        <div className="center">
          <Transcript
            events={viewEvents}
            running={isRunning && runningTicket === selectedId}
            ticketId={selectedId}
            summary={runResult ? (
              <ShiftReports result={runResult} events={viewEvents}
                why={why ? { rank: railIds.indexOf(selected!.id) + 1, reason: why.reason, overridden: manualOrder?.includes(selected!.id) ?? false } : null} />
            ) : null}
            tab={runResult ? logTab : "log"}
            onTab={setLogTab}
          />
        </div>
      </main>

      {reviewing && (
        <DraftReview
          draft={drafts.find((d) => d.id === reviewing.id) ?? reviewing}
          ticket={reviewTicket}
          events={reviewEvents}
          signer={signer}
          onSigner={setSigner}
          onApprove={approveDraft}
          onUndo={undoDraft}
          onClose={() => setReviewing(null)}
          busy={busy}
        />
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
