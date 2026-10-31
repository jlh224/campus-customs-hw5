import { Dan } from "./Dan";
import { seatsFromEvents } from "./Team";
import { AGENT_INFO, EXPECTED_HANDOFFS, type AgentName, type AuditEvent, type Ticket } from "../types";

/** A drawn white Bulldog tee (we have no photo of the exact "Classic Bulldog Tee"). */
function TeeDrawing() {
  return (
    <svg viewBox="0 0 200 150" className="art-svg" role="img" aria-label="Classic Bulldog Tee (drawing)">
      <path d="M62 22 L84 14 Q100 26 116 14 L138 22 L166 46 L150 66 L138 58 L138 136 L62 136 L62 58 L50 66 L34 46 Z"
        fill="#ffffff" stroke="#00356b" strokeWidth="3" strokeLinejoin="round" />
      <path d="M84 14 Q100 30 116 14" fill="none" stroke="#00356b" strokeWidth="3" />
      <g transform="translate(76 52) scale(0.4)"><Dan size={120} /></g>
      <text x="100" y="124" textAnchor="middle" fontSize="11" fontWeight="800" fill="#00356b" letterSpacing="2">BULLDOGS</text>
    </svg>
  );
}

/** A drawn Chapel Street storefront for the rent ticket. */
function ShopDrawing() {
  const stripes = Array.from({ length: 8 }, (_, i) => (
    <rect key={i} x={30 + i * 17.5} y="40" width="17.5" height="18" fill={i % 2 ? "#ffffff" : "#00356b"} />
  ));
  return (
    <svg viewBox="0 0 200 150" className="art-svg" role="img" aria-label="Campus Customs shop on Chapel Street (drawing)">
      <rect x="22" y="22" width="156" height="114" rx="4" fill="#e9f0fa" stroke="#00356b" strokeWidth="3" />
      <rect x="30" y="26" width="140" height="14" fill="#00356b" />
      <text x="100" y="37" textAnchor="middle" fontSize="10" fontWeight="800" fill="#fff" letterSpacing="1.5">CAMPUS CUSTOMS</text>
      {stripes}
      <path d="M30 58 Q38 64 47.5 58 Q56 64 65 58 Q73 64 82.5 58 Q91 64 100 58 Q108 64 117.5 58 Q126 64 135 58 Q143 64 152.5 58 Q161 64 170 58" fill="none" stroke="#00356b" strokeWidth="2" />
      <rect x="40" y="72" width="62" height="46" rx="3" fill="#cfe0f6" stroke="#00356b" strokeWidth="2.5" />
      <path d="M71 72 L71 118 M40 95 L102 95" stroke="#00356b" strokeWidth="1.5" />
      <rect x="116" y="72" width="40" height="64" rx="3" fill="#286dc0" stroke="#00356b" strokeWidth="2.5" />
      <circle cx="148" cy="106" r="2.6" fill="#fff" />
      <rect x="18" y="134" width="164" height="6" rx="2" fill="#00356b" />
      <text x="71" y="131" textAnchor="middle" fontSize="8" fill="#00356b" fontWeight="700">CHAPEL ST</text>
    </svg>
  );
}

/** What the ticket is about, at a glance: the real hoodie photo, a drawn tee, or the shop. */
export function TicketArt({ ticket }: { ticket: Ticket }) {
  const caption = ticket.sku ? `${ticket.qty} × size ${ticket.size}` : ticket.type === "rent_notice" ? "Rent · Chapel Street shop" : "";
  return (
    <div className={`art art-${ticket.type}`}>
      {ticket.sku === "CC-HOOD-NAVY" ? (
        <img className="art-photo" src="/products/basic-hoodie-big-yale.jpg" alt="Basic Hoodie Big Yale (navy)" />
      ) : ticket.sku === "CC-TEE-WHITE" ? (
        <TeeDrawing />
      ) : (
        <ShopDrawing />
      )}
      {caption && <span className="art-caption">{caption}</span>}
    </div>
  );
}

/**
 * The team on this ticket, as a tiny row of Dans in the order they joined.
 * Each one lights up while it works. Before a run, the planned agents show faded.
 */
export function AgentStrip({ ticketId, events }: { ticketId: number; events: AuditEvent[] }) {
  const ran = events.length > 0;
  const seats = seatsFromEvents(events);
  const order: AgentName[] = [];
  for (const e of events) if (e.event === "agent_start" && e.agent && !order.includes(e.agent as AgentName)) order.push(e.agent as AgentName);
  if (!ran) {
    for (const [a, b] of EXPECTED_HANDOFFS[ticketId] ?? []) for (const x of [a, b]) if (!order.includes(x)) order.push(x);
  }
  return (
    <div className={`strip ${ran ? "" : "strip-planned"}`} aria-label="Agents on this ticket">
      {order.map((a, i) => {
        const st = ran ? seats[a].state : "off";
        return (
          <span key={a} className={`strip-agent strip-${st}`} title={`${AGENT_INFO[a].title}${seats[a].line ? ` · ${seats[a].line}` : ran ? "" : " (planned)"}`}>
            {i > 0 && <span className="strip-arrow">›</span>}
            <span className="strip-dan"><Dan outfit={a} size={26} />{ran && <span className={`lamp lamp-${st}`} />}</span>
          </span>
        );
      })}
      <span className="strip-label">{ran ? "Agents · see Summary for details" : "Planned team"}</span>
    </div>
  );
}
