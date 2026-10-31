import { toolLabel } from "../labels";
import { AGENT_INFO, AGENTS, type AgentName, type AuditEvent } from "../types";

export type SeatState = "off" | "waiting" | "thinking" | "tool" | "handing" | "done" | "error";

export interface Seat {
  state: SeatState;
  line: string;
  tools: number;
}


const short = (s: string, n = 110) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
/** Work out what each seat is doing from one run's events. */
export function seatsFromEvents(events: AuditEvent[]): Record<AgentName, Seat> {
  const seats = Object.fromEntries(AGENTS.map((a) => [a, { state: "off", line: "", tools: 0 }])) as Record<AgentName, Seat>;
  for (const e of events) {
    const a = e.agent as AgentName | undefined;
    if (!a || !seats[a]) continue;
    const seat = seats[a];
    switch (e.event) {
      case "agent_start":
        seat.state = "thinking";
        seat.line = `Picked up: ${short(e.task ?? "", 90)}`;
        break;
      case "model_step":
        if (e.text && !e.text.trim().startsWith("{")) seat.line = short(e.text);
        seat.state = "thinking";
        break;
      case "tool_call":
        seat.state = "tool";
        seat.tools += 1;
        seat.line = toolLabel(e.tool ?? "", e.args);
        break;
      case "delegation_start":
        seat.state = "handing";
        seat.line = `→ ${AGENT_INFO[e.to_agent as AgentName]?.title}: ${short(e.task ?? "", 90)}`;
        break;
      case "delegation_end":
        seat.state = "thinking";
        seat.line = `Got ${AGENT_INFO[e.to_agent as AgentName]?.title}'s report`;
        break;
      case "customer_draft_saved":
        seat.line = `Drafted a message to ${e.draft?.to}`;
        break;
      case "agent_end":
        seat.state = "done";
        seat.line = short(String(e.output?.summary ?? e.output?.decision ?? "Finished."), 140);
        break;
      case "agent_error":
        seat.state = "error";
        seat.line = short(e.error ?? "error");
        break;
    }
  }
  // While a teammate works for you, your seat shows "waiting".
  for (const e of events) {
    if (e.event === "delegation_start" && e.agent && seats[e.agent].state === "handing") {
      const helper = seats[e.to_agent as AgentName];
      if (helper && helper.state !== "done" && helper.state !== "off") seats[e.agent].state = "waiting";
    }
  }
  return seats;
}
