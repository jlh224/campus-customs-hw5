/** Turn raw tool calls into short, plain-English labels for the desk. */

export function parseArgs(args: unknown): Record<string, any> {
  try {
    const obj = typeof args === "string" ? JSON.parse(args) : args;
    return (obj && typeof obj === "object" ? obj : {}) as Record<string, any>;
  } catch {
    return {};
  }
}

export function rawCall(tool: string, args: unknown): string {
  const a = parseArgs(args);
  return `${tool}(${Object.entries(a).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})`;
}

export function toolLabel(tool: string, args: unknown): string {
  const a = parseArgs(args);
  const item = [a.sku, a.size].filter(Boolean).join(" ");
  switch (tool) {
    case "get_ticket": return `Read ticket #${a.ticket_id}`;
    case "list_tickets":
    case "list_open_tickets": return "Looked at the board";
    case "check_stock": return `Checked stock · ${item || "all items"}`;
    case "get_pricing": return a.offered_unit_price ? `Priced ${a.sku} at $${a.offered_unit_price}` : `Looked up price · ${a.sku}`;
    case "get_vendor_status": return a.vendor_id ? `Checked vendor #${a.vendor_id}` : "Checked all vendors";
    case "get_invoice": return `Read invoice #${a.invoice_id}`;
    case "get_lease": return `Read lease #${a.lease_id}`;
    case "get_cash_balance": return "Checked cash";
    case "get_payments": return a.kind ? `Checked past ${a.kind} payments` : "Checked past payments";
    case "prepare_payment": return `Prepared a check · ${a.kind} #${a.ref_id}`;
    case "draft_purchase_order": return `Drafted a PO · ${a.qty} × ${item}`;
    case "update_ticket": return `Set #${a.ticket_id} → ${a.status}`;
    case "save_customer_draft": return `Wrote a draft to ${a.to}`;
    default: return tool.replace(/_/g, " ");
  }
}

export const clock = (ts: string) =>
  new Date(ts).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
