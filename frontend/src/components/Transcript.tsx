import { useEffect, useRef, useState, type ReactNode } from "react";
import { Dan } from "./Dan";
import { clock, rawCall, toolLabel } from "../labels";
import { AGENT_INFO, type AgentName, type AuditEvent } from "../types";

const title = (a?: string | null) => (a ? AGENT_INFO[a as AgentName]?.title ?? a : "Desk");

type Item = { key: string; kind: "say" | "tools" | "note" | "report" | "draft" | "final" | "warn"; node: ReactNode };
type Block = { key: string; agent: AgentName | null; ts: string; items: Item[] };

/** Long text gets a "more" toggle so the log stays calm. */
function Clamp({ text, lines = 3 }: { text: string; lines?: number }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 220;
  return (
    <span className="clamp">
      <span className={open || !long ? "" : `clamped clamp-${lines}`}>{text}</span>
      {long && (
        <button className="more" onClick={() => setOpen(!open)}>{open ? "less" : "more"}</button>
      )}
    </span>
  );
}

/** One event -> zero or one item in its agent's block. */
function toItem(e: AuditEvent): { agent: AgentName | null; item: Item } | null {
  const k = String(e.seq);
  const agent = (e.agent ?? null) as AgentName | null;
  switch (e.event) {
    case "model_step": {
      const text = e.text && !e.text.trim().startsWith("{") ? e.text : "";
      const calls = (e.tool_calls ?? []).filter((c) => c.tool !== "delegate");
      if (text) return { agent, item: { key: k, kind: "say", node: <Clamp text={text} /> } };
      if (!calls.length) return null;
      return {
        agent,
        item: {
          key: k, kind: "tools",
          node: calls.map((c, i) => (
            <span key={i} className="tool-chip" title={rawCall(c.tool, c.args)}>{toolLabel(c.tool, c.args)}</span>
          )),
        },
      };
    }
    case "delegation_start":
      return {
        agent,
        item: {
          key: k, kind: "note",
          node: (
            <>
              <span className="note-head">📝 Note to {title(e.to_agent)}</span>
              <Clamp text={e.task ?? ""} lines={2} />
            </>
          ),
        },
      };
    case "delegation_end":
      return {
        agent: (e.to_agent ?? null) as AgentName | null,
        item: {
          key: k, kind: "report",
          node: (
            <>
              <span className="note-head">↩ Report to {title(agent)}</span>
              <Clamp text={e.report?.summary ?? ""} lines={2} />
            </>
          ),
        },
      };
    case "customer_draft_saved":
      return { agent, item: { key: k, kind: "draft", node: <>✉️ Saved a draft for <b>{e.draft?.to}</b> · not sent</> } };
    case "agent_end":
      return agent === "boss"
        ? { agent, item: { key: k, kind: "final", node: <Clamp text={String(e.output?.decision ?? "")} lines={4} /> } }
        : null;
    case "agent_error":
    case "delegation_failed":
    case "delegation_refused":
      return { agent, item: { key: k, kind: "warn", node: <>⚠️ {e.error ?? e.reason}</> } };
    default:
      return null;
  }
}

function buildBlocks(events: AuditEvent[]): (Block | { key: string; meta: ReactNode })[] {
  const out: (Block | { key: string; meta: ReactNode })[] = [];
  for (const e of events) {
    if (e.event === "ticket_run_start") {
      out.push({ key: `m${e.seq}`, meta: <>🔔 Ticket #{e.ticket_id} handed to the Boss · {clock(e.ts)}</> });
      continue;
    }
    if (e.event === "ticket_run_end") {
      out.push({ key: `m${e.seq}`, meta: <>{e.ok ? "✅ Run finished" : "⚠️ Run stopped"} · {clock(e.ts)}</> });
      continue;
    }
    if (e.event === "approval_decided") {
      out.push({ key: `m${e.seq}`, meta: <>🖋️ {e.decided_by} {e.status === "paid" ? "signed" : e.status} {e.approval_id}</> });
      continue;
    }
    const r = toItem(e);
    if (!r) continue;
    const last = out[out.length - 1];
    if (last && "items" in last && last.agent === r.agent) last.items.push(r.item);
    else out.push({ key: `b${e.seq}`, agent: r.agent, ts: e.ts, items: [r.item] });
  }
  return out;
}

export function Transcript({ events, running, ticketId, summary, tab, onTab }: {
  events: AuditEvent[];
  running: boolean;
  ticketId: number | null;
  summary: ReactNode;
  tab: "log" | "summary";
  onTab: (tab: "log" | "summary") => void;
}) {
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Scroll only the log box (not the whole page) to the newest line.
    const el = log.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  const blocks = buildBlocks(events);
  return (
    <section className="card transcript">
      <div className="tabs">
        <button className={`tab ${tab === "log" ? "tab-on" : ""}`} onClick={() => onTab("log")}>
          Live log{ticketId ? ` · #${ticketId}` : ""} {running && <span className="live">● live</span>}
        </button>
        <button className={`tab ${tab === "summary" ? "tab-on" : ""}`} onClick={() => onTab("summary")} disabled={!summary}>
          Summary
        </button>
      </div>
      {tab === "summary" && summary ? <div className="summary-pane">{summary}</div> : (
      <div className="log" ref={log}>
        {blocks.length === 0 && <p className="hint">Press “Let the Boss run the board.” Every agent's words and tool calls show up here as they work.</p>}
        {blocks.map((b) =>
          "meta" in b ? (
            <div key={b.key} className="log-meta">{b.meta}</div>
          ) : (
            <div key={b.key} className={`entry entry-${b.agent ?? "desk"}`}>
              <div className="entry-avatar">{b.agent ? <Dan outfit={b.agent} size={34} /> : null}</div>
              <div className="entry-body">
                <div className="entry-head">
                  <span className="entry-name">{title(b.agent)}</span>
                  <span className="entry-time">{clock(b.ts)}</span>
                </div>
                {b.items.map((it) => (
                  <div key={it.key} className={`item item-${it.kind}`}>{it.node}</div>
                ))}
              </div>
            </div>
          ),
        )}
      </div>
      )}
    </section>
  );
}
