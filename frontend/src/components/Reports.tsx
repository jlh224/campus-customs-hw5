import { Dan } from "./Dan";
import { toolLabel } from "../labels";
import { AGENT_INFO, AGENTS, type AgentName, type AuditEvent, type RunResult } from "../types";

const title = (a: AgentName) => AGENT_INFO[a].title;

interface Step {
  key: string;
  agent: AgentName;
  role: string; // "routes the ticket", "final call", or the task in a few words
  from?: AgentName; // who handed it this work
  said: string; // what it concluded
  tools: string[]; // plain-English tool labels, in order
  handedTo: AgentName[];
}

const short = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

/**
 * Turn one run's events into the order the work actually happened.
 * Each agent turn is a step; an agent called twice shows up twice. The Boss
 * shows up first (routing) and last (the final call), because that's when he works.
 */
function buildSteps(events: AuditEvent[], result: RunResult): Step[] {
  const steps: Step[] = [];
  const stack: Step[] = []; // open agent turns (delegated turns run inside their caller's)
  let bossRouting: Step | null = null;
  let bossFinal: Step | null = null;

  for (const e of events) {
    const a = e.agent as AgentName | undefined;
    if (e.event === "agent_start" && a) {
      const step: Step = {
        key: `s${e.seq}`, agent: a, from: (e.delegated_by ?? undefined) as AgentName | undefined,
        role: a === "boss" && !e.delegated_by ? "Routes the ticket" : short(e.task ?? "", 90),
        said: "", tools: [], handedTo: [],
      };
      if (a === "boss" && !e.delegated_by) bossRouting = step;
      steps.push(step);
      stack.push(step);
      continue;
    }
    const top = [...stack].reverse().find((s) => s.agent === a);
    if (!top) continue;
    if (e.event === "tool_call") {
      // After the Boss's first handoff comes back, his remaining work is the final call.
      const target = top === bossRouting && bossFinal ? bossFinal : top;
      target.tools.push(toolLabel(e.tool ?? "", e.args));
    } else if (e.event === "delegation_start" && e.to_agent) {
      (top === bossRouting && bossFinal ? bossFinal : top).handedTo.push(e.to_agent as AgentName);
    } else if (e.event === "delegation_end" && top === bossRouting && !bossFinal) {
      bossFinal = { key: `final${e.seq}`, agent: "boss", role: "Makes the final call", said: "", tools: [], handedTo: [] };
    } else if (e.event === "agent_end") {
      const out = e.output ?? {};
      if (top === bossRouting) {
        const final = bossFinal ?? { key: `final${e.seq}`, agent: "boss" as AgentName, role: "Makes the final call", said: "", tools: [], handedTo: [] };
        final.said = String(out.decision ?? "");
        steps.push(final);
        bossRouting.said = bossRouting.handedTo.length
          ? `Sent the ticket to ${bossRouting.handedTo.map(title).join(", ")}.`
          : "Read the ticket.";
      } else {
        top.said = String(out.summary ?? "");
      }
      stack.splice(stack.indexOf(top), 1);
    }
  }
  // Fallback if the log is missing (e.g. an old run): one step per handoff.
  if (steps.length === 0 && result.decision) {
    steps.push({ key: "b", agent: "boss", role: "Routes the ticket", said: "", tools: [], handedTo: [] });
    for (const h of result.handoffs) steps.push({ key: `${h.from_agent}-${h.to_agent}`, agent: h.to_agent, from: h.from_agent, role: short(h.task, 90), said: h.report?.summary ?? "", tools: [], handedTo: [] });
    steps.push({ key: "f", agent: "boss", role: "Makes the final call", said: result.decision.decision, tools: [], handedTo: [] });
  }
  return steps;
}

/** After a run: the work in the order it happened, one numbered step per agent turn. */
export function ShiftReports({ result, events, why }: {
  result: RunResult | null;
  events: AuditEvent[];
  why: { rank: number; reason: string; overridden: boolean } | null;
}) {
  if (!result) return null;
  const steps = buildSteps(events, result);
  const worked = new Set(steps.map((s) => s.agent));
  const offShift = AGENTS.filter((a) => !worked.has(a));

  return (
    <>
      {why && (
        <div className="why-line">
          <span className="why-n">{why.rank}</span>
          <span><b>{why.overridden ? "Worked #" + why.rank + " (your order)." : "Why the Boss put this ticket #" + why.rank + ":"}</b> {why.reason}</span>
        </div>
      )}
      <ol className="timeline">
        {steps.map((s, i) => (
          <li key={s.key} className={`tl-step report-${s.agent}`}>
            <div className="tl-num">{i + 1}</div>
            <div className="tl-card">
              <div className="report-head">
                <Dan outfit={s.agent} size={30} />
                <b>{title(s.agent)}</b>
                {s.from && <span className="tl-from">from {title(s.from)}</span>}
              </div>
              <div className="tl-role">{s.role}</div>
              {s.said && <p>{s.said}</p>}
              {s.tools.length > 0 && <div className="report-tools">{s.tools.map((x, k) => <span key={k} className="tool-chip">{x}</span>)}</div>}
              {s.handedTo.length > 0 && <div className="report-meta">Handed work to {s.handedTo.map(title).join(", ")}</div>}
              {s.role === "Makes the final call" && result.decision && (
                <div className="report-meta">Final status: <b>{result.decision.final_status}</b></div>
              )}
            </div>
          </li>
        ))}
      </ol>
      {offShift.length > 0 && <div className="off-line">Off shift on this ticket: {offShift.map(title).join(", ")}</div>}
      <div className="usage">
        {result.usage.model_requests} model calls · {(result.usage.input_tokens + result.usage.output_tokens).toLocaleString()} tokens · gpt-6-luna
      </div>
    </>
  );
}
