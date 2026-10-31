# Campus Customs MCP Server

**What it's for:** This is the one shared toolbox for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Agents never query the database directly. They call these MCP tools, which return only what is in the database. If a row doesn't exist, the tool says `found: false` instead of guessing.

**Database:** `data/campus_customs_new.db`, the working copy. The original `data/campus_customs.db` is never touched by the server; it is the reset point. Read tools open the working copy read-only. Only `update_ticket` and `pay` write. There are 14 tools.

**Built with:** [FastMCP](https://gofastmcp.com) (`server.py`).

## Tools

### Read tools (never change the database)

| Tool | Reads | Returns |
|---|---|---|
| `list_tickets()` | `tickets`, `desk` | Every ticket, open or resolved, with its status (used by the board). |
| `list_open_tickets()` | `tickets`, `desk` | Every unresolved ticket, oldest first, with the shop date. |
| `get_ticket(ticket_id)` | `tickets`, `desk` | One ticket with its link fields (`sku`/`size`, `lease_id`, `invoice_id`). |
| `check_stock(sku, size=None)` | `inventory` | Item name, and for each size: qty on hand, location, `in_stock`. |
| `get_pricing(sku, offered_unit_price=None, qty=None)` | `pricing` | Unit cost, list price, margin; with an offer, the discount %, margin, order total, and `below_cost`. |
| `get_vendor_status(vendor_id=None)` | `vendors`, `invoices`, `desk` | Specialty, `lead_days`, open invoices with days overdue, `can_ship` (False while any invoice is open). |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | Vendor, amount, due date, status, days overdue. |
| `get_lease(lease_id)` | `leases`, `desk` | Space, landlord, monthly rent, next due date, `days_until_due`. |
| `get_cash_balance()` | `cash_accounts` | Each account's balance and the total. |
| `get_payments(kind=None, ref_id=None)` | `payments` | Payments already made (who approved, when, how much). Used to catch duplicates. |
| `prepare_payment(kind, ref_id, account="checking")` | `invoices`/`vendors` or `leases`, `cash_accounts`, `desk` | A payment request for **human approval**: payee, amount, cash before/after, `can_afford`, and `below_buffer` (checking would drop under the shop's $100 cushion). Pays nothing. |
| `draft_purchase_order(vendor_id, sku, size, qty)` | `vendors`, `invoices`, `pricing`, `inventory`, `desk` | A restock draft: total cost, lead time, `can_ship`, earliest arrival. Sends nothing. |

### Write tools

| Tool | Writes | Rules |
|---|---|---|
| `update_ticket(ticket_id, status, note)` | `tickets` | Status is one of `open`, `in_progress`, `resolved` (the team uses `resolved` when its work is done; human sign-off is tracked on the board as **signed**). Notes are added with the shop date; the original request is kept. |
| `pay(kind, ref_id, approved_by, account="checking", sku=None, size=None, qty=None)` | `payments`, `cash_accounts`, `invoices` or `leases` | **Human approval required.** `approved_by` must be a human's name, not an agent's. Refuses if cash would go negative, if the invoice isn't open, if the rent is already paid ahead, or (for a purchase order) if the vendor still has an unpaid invoice. Pays and updates all rows in one transaction (invoice → `paid`; rent → `next_due` moves one month ahead; purchase order → paid up front, stock arrives after the vendor's lead days). **No agent is given this tool.** Only the backend's human approval route (`POST /api/approvals/{id}/approve`) calls it. |

`kind` is `"invoice"` (ref_id = `invoices.id`), `"rent"` (ref_id = `leases.id`), or for `pay` only, `"purchase_order"` (ref_id = `vendors.id`, plus `sku`, `size`, `qty`). Dates such as "overdue" and "days until due" are measured from `desk.date_today`, the shop's today, not the computer clock.

## Run

```bash
python server.py          # stdio
python server.py --http   # HTTP at http://127.0.0.1:8001/mcp
```
