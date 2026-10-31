# Campus Customs Multi-Agent Harness

The running reference for the HW5 agent team: data, tools, safety rules, and specs. Later problems add to it.

---

## 1. Database

- **Original:** `data/campus_customs.db`. Never written to; it is the reset point.
- **Working copy:** `data/campus_customs_new.db`. The MCP server and backend read and write this copy only. To reset, copy the original over it again.
- **Shop "today":** `desk.date_today` = **2026-08-31**. Every overdue / due-soon check uses this date, not the computer's clock.

### Tables and fields

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `desk` | `date_today`, `notes` | The shop's official "today". All agents use it to decide what is overdue or due soon. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | The work queue on the board. Boss reads each ticket and routes it; the link fields (`sku`/`size`, `lease_id`, `invoice_id`) point to the rows the specialists need. |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` (key: `sku` + `size`) | Inventory agent checks stock by SKU and size and spots shortfalls. |
| `pricing` | `sku`, `unit_cost`, `list_price` | Accounting checks margins on discount requests and prices restock orders (cost × qty). |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Inventory picks the right vendor by specialty; `lead_days` gives the restock arrival date. |
| `invoices` | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | Unpaid bills. A vendor with an `open` invoice will not ship new product, so this gates restocking. Accounting prepares these for payment. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | Facilities tracks rent amount and due date for the shop space. |
| `cash_accounts` | `name`, `balance`, `date` | The only cash. Every payment must fit inside `balance`; no negative balances. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | Record of money paid out. Starts empty; a row is written only after a human approves a payment. `kind` + `ref_id` point to what was paid (invoice or lease). |

### Starting data (snapshot of the original)

- **Cash:** `checking` = **$3,400.00**.
- **Invoices:** #501, Bulldog Print Co (vendor 1), **$840.00**, due 2026-08-28, `open`, "Rush reprint CC-TEE-WHITE S". This is **3 days overdue**.
- **Lease:** #1, Chapel Street shop, Elm City Properties, **$2,400.00/month**, next due **2026-09-02** (2 days away).
- **Vendors:** 1 Bulldog Print Co (apparel reprint, 5 days), 2 Elm City Gifts (mugs and small goods, 3 days), 3 QuickShip CT (local courier, 1 day).
- **Payments:** none yet.
- **Inventory and pricing:**

| SKU | Name | Sizes (qty) | Unit cost | List price |
|---|---|---|---|---|
| CC-HOOD-NAVY | Basic Hoodie Big Yale | S 4, M 8, L 14, XL 6 | $22.00 | $58.00 |
| CC-TEE-WHITE | Classic Bulldog Tee | S **0**, M 5, L 3, XL 2 | $8.00 | $28.00 |
| CC-HAT-BLUE | Yale Cap | OS 40 | $6.00 | $22.00 |
| CC-MUG-CREST | Crest Mug | OS **0** | $3.50 | $14.00 |

---

## 2. The Three Open Tickets and How They Link

### Ticket 101: customer order (Tauhid Zaman, Bulldog tee, size S, qty 1)
- **Links:** `sku`/`size` → `inventory` (CC-TEE-WHITE S = **0 in stock**); `invoice_id` → invoice **#501**.
- **Chain:** The tee is out of stock in S. The apparel vendor, Bulldog Print Co, has open invoice #501 for $840, which is overdue. That vendor won't ship until #501 is paid. Paying it needs human approval. After it's paid, a reprint takes 5 days (`lead_days`).
- **Agents:** Inventory (shortfall + vendor), Accounting (invoice, needs approval), Customer Service (draft a message to the customer with an honest timeline).

### Ticket 102: rent notice (Elm City Properties, rent due)
- **Links:** `lease_id` → lease **#1** ($2,400, due 2026-09-02).
- **Chain:** Rent is due in 2 days. Facilities confirms the amount and date; Accounting prepares the $2,400 payment for human approval.
- **Agents:** Facilities, Accounting.

### Ticket 103: price override (Yale AI Club, 20 hoodies, size M, bulk discount)
- **Links:** `sku`/`size` → `inventory` (CC-HOOD-NAVY M = **8 in stock**, short **12**); `sku` → `pricing` (cost $22, list $58).
- **Chain:** Only 8 of 20 are on hand. The other 12 come from the apparel vendor, Bulldog Print Co, which is blocked by the same open invoice #501. Any discount must keep a margin above the $22 unit cost.
- **Agents:** Inventory (shortfall), Accounting (margin check on the discount), Boss (final call on the price), Customer Service (draft reply to the club).

### What ties the tickets together: cash
| Item | Amount | Checking after |
|---|---|---|
| Start | | $3,400.00 |
| Pay invoice #501 (unblocks the apparel vendor) | $840.00 | $2,560.00 |
| Pay rent, lease #1 | $2,400.00 | $160.00 |
| Restock 12 hoodies at $22 (if paid up front) | $264.00 | **−$104.00 (not allowed)** |

Cash only goes out in this homework, so the Boss has to choose what to pay first, and the pay tool must refuse any payment that would make the balance negative.

---

## 3. MCP Server and Tools

`mcp_server/server.py` is a FastMCP server named `campus-customs`. Every agent gets its tools from here, and it only touches `data/campus_customs_new.db`. Tools return database values only: no invented stock, prices or dates. A missing row returns `found: false` with a message. Overdue and due-soon dates are measured from `desk.date_today`.

| Tool | Reads | Unlocks | Why it's the right tool |
|---|---|---|---|
| `check_stock(sku, size=None)` | `inventory` | 101, 103 | Both tickets hinge on a shortfall by SKU and size (Tee S has 0 for 101; Hoodie M has 8 of the 20 wanted for 103), and this returns the exact qty on hand. |
| `get_vendor_status(vendor_id=None)` | `vendors`, `invoices`, `desk` | 101 (also 103) | Restocking depends on the apparel vendor, and this shows that Bulldog Print Co can't ship (`can_ship: false`) because invoice #501 ($840) is open and 3 days overdue, plus its 5-day lead time. |
| `get_lease(lease_id)` | `leases`, `desk` | 102 | The rent notice links to lease #1, and this confirms the real amount ($2,400) and due date (2026-09-02, 2 days away) instead of trusting the email. |

**Connection and smoke test.** `.mcp.json` at the project root registers `campus-customs` as a stdio server (`C:\venvs\hw5\Scripts\python.exe mcp_server/server.py`), so the vibe coder can call the tools directly. `output/mcp_smoke.json` records one live call per tool (my prompt, tool name, arguments, output), and each output was checked field by field against `data/campus_customs_new.db`. All three passed.

### Tools added in Problem 5

The agents needed more than the first three tools to work every ticket, so the server now has **14 tools** (13 from Problem 5, plus `list_tickets` for the board in Problem 7). All shop facts still come only from MCP; the backend has no second shop-tools layer.

| Tool | Table(s) | Reads/Writes | Used by | Why it's needed |
|---|---|---|---|---|
| `list_open_tickets()` | `tickets`, `desk` | read | Boss | See the board. |
| `get_ticket(ticket_id)` | `tickets`, `desk` | read | all | Every agent starts from the real ticket and its links. |
| `get_pricing(sku, offered_unit_price, qty)` | `pricing` | read | Accounting | 103: margin and discount math comes from the tool, not the model. |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | read | Accounting | 101: invoice #501's amount, due date, days overdue. |
| `get_cash_balance()` | `cash_accounts` | read | Boss, Accounting | Every payment decision depends on cash on hand. |
| `get_payments(kind, ref_id)` | `payments` | read | Facilities, Accounting | Catch duplicate payments before preparing one. |
| `prepare_payment(kind, ref_id)` | `invoices`/`vendors` or `leases`, `cash_accounts`, `desk` | read | Accounting | Builds a payment request **for human approval**: amount, cash after, `can_afford`, `below_buffer` ($100 cushion). Pays nothing. |
| `draft_purchase_order(vendor_id, sku, size, qty)` | `vendors`, `invoices`, `pricing`, `inventory`, `desk` | read | Inventory, Accounting | Restock cost, lead time, `can_ship`, earliest arrival. Sends nothing. |
| `update_ticket(ticket_id, status, note)` | `tickets` | **write** | Boss | Sets the final status (`resolved` when the team's work is done; `in_progress` if it stopped partway) with a dated note; keeps the original request. |
| `pay(kind, ref_id, approved_by, sku, size, qty)` | `payments`, `cash_accounts`, `invoices` or `leases` (and `vendors`, `pricing` for purchase orders) | **write** | **no agent** (human approval route only) | The only tool that moves money. Needs a human approver, refuses if cash would go negative, refuses duplicates, and updates every row in one transaction. Since Problem 7, `kind="purchase_order"` pays a vendor up front for an approved restock, and it's refused while that vendor has an unpaid invoice. |
| `list_tickets()` *(Problem 7)* | `tickets`, `desk` | read | backend board | Every ticket, open or resolved, for the dashboard. |

---

## 4. The Agent Team

All five agents are PydanticAI agents in `backend/agents.py`. Every one uses **`gpt-6-luna`** through Portkey with `PORTKEY_API_KEY` (`backend/config.py`; the model name is fixed in code with no override). Prompts are one file per agent in `backend/prompts/`, written from my answers to the design questions. Data types are in `backend/models.py`.

| Agent | Prompt | Owns | MCP tools | Effort | Returns |
|---|---|---|---|---|---|
| **Boss** | `boss.md` | Every ticket first; routes by type and makes the final call | `list_open_tickets`, `get_ticket`, `get_cash_balance`, `update_ticket` | medium | `TicketDecision` |
| **Inventory** | `inventory.md` | `customer_order` tickets | `get_ticket`, `check_stock`, `get_vendor_status`, `draft_purchase_order` | low | `AgentReport` |
| **Accounting** | `accounting.md` | `price_override` tickets; prepares payments and POs | `get_ticket`, `get_cash_balance`, `get_invoice`, `get_pricing`, `get_lease`, `get_vendor_status`, `get_payments`, `prepare_payment`, `draft_purchase_order` | low | `AgentReport` |
| **Facilities** | `facilities.md` | `rent_notice` tickets | `get_ticket`, `get_lease`, `get_payments` | low | `AgentReport` |
| **Customer Service** | `customer_service.md` | Customer drafts | `get_ticket`, `check_stock`, `get_vendor_status`, plus `save_customer_draft` (board only, never sent) | low | `AgentReport` |

**Boss triage (added in Problem 9).** Before any ticket runs, the Boss can look at the whole board and suggest which ticket to work first, ranked by our cash rules: rent first (keep the shop space), then overdue vendor bills that block restocking, then restocks and discounts with what's left, and never below the $100 buffer. Triage is a separate, **read-only** Boss agent (same `boss.md` prompt) with only `list_open_tickets`, `get_ticket`, `get_cash_balance`, `get_lease`, and `get_invoice`, and no `delegate()`, returning a `TriageResult` (rank, ticket, one-line reason with real numbers, and a cash summary). It recommends the order; **“Let the Boss run the board”** then has the Boss work every open ticket in that order without any manual hand-off, and a human signs at the end.

**Ticket statuses.** The Boss ends every run with `resolved` (the team's work is done) or `in_progress` (it stopped partway); `waiting_approval` was removed from the schema and the MCP tool in Problem 9 after the Boss chose it once despite the prompt. Human sign-off is tracked on the board as **signed**. A backend safety net (`_sync_ticket_status`) makes the ticket row match the Boss's final decision.

**Full connectivity.** Every agent has `delegate(to_agent, task)` and can hand work to any other agent, not just back to the Boss. The Boss routes by ticket type to one owner; the owner brings in teammates directly (e.g. Facilities → Accounting on 102, Inventory → Accounting and Inventory → Customer Service on 101).

**The agent loop.** `run_agent()` runs `agent.iter()`: model call → tool calls (MCP or `delegate`) → model call, until the agent returns its structured output (OpenAI native structured output, so the reply can't drift into free text). A delegated agent runs its own full loop inside the caller's `delegate` call and returns its `AgentReport`.

**Board items come from tools, not model text.** Payment requests are built from `prepare_payment` results and purchase orders from `draft_purchase_order` results, so amounts and dates on the board are always database values. Customer messages are saved with `save_customer_draft` and stay on the board.

**Audit trail.** Every loop step is appended to `output/audit_trail.json` (one JSON array, never wiped; an unreadable file is set aside, not deleted). Each entry has `seq`, `ts`, `event`, `run_id`, `ticket_id`, `model`, `agent`, `depth`, `delegated_by`, `chain`, and `step`, plus the event's details:

| Event | Details recorded |
|---|---|
| `ticket_run_start` / `ticket_run_end` | the limits in force; final decision, handoffs, payment requests, POs, drafts, token totals |
| `agent_start` / `agent_end` / `agent_error` | the task given; the structured output or the error |
| `model_step` | the model's text, the tool calls it chose (with arguments), input/output tokens, ticket tokens so far |
| `tool_call` / `tool_result` / `tool_error` | MCP tool name, arguments, result |
| `tool_blocked` | an agent tried a human-only tool |
| `delegation_start` / `delegation_end` / `delegation_failed` / `delegation_refused` | from → to, the task, the report back, or why it was refused |
| `customer_draft_saved` | the full draft |
| `triage_start` / `triage_end` | the Boss's suggested order, reasons, cash summary, tokens |
| `ticket_status_synced` | the backend corrected a ticket row to match the Boss's final status |
| `approval_decided` | a human signed (paid), was refused by the pay tool, or voided a check / PO, with the outcome |
| `db_reset` | the working database was restored from the original |

---

## 5. Safety and Guardrails

What a real business would want when agents touch real customers and real money:

- **Humans approve all money.** No agent has the `pay` tool: it is filtered out of every agent's toolset and also blocked in the MCP call hook, so a slip in one layer can't pay. `pay` itself requires a human approver's name (agent names are rejected).
- **No negative cash, ever.** `pay` refuses any payment larger than the balance and writes nothing. On top of that, the shop keeps a $100 cushion: `prepare_payment` flags `below_buffer`, and Accounting's prompt says never go below $100.
- **No duplicates.** `pay` refuses an invoice that isn't open or rent already paid ahead; Facilities and Accounting check `get_payments` first.
- **Verify before paying.** Facilities checks a rent notice's sender, amount, due date, and payment history against the lease before Accounting prepares anything; mismatches go to the Boss.
- **Nothing leaves the shop.** Customer messages and purchase orders are drafts on the board. No tool can email a customer or contact a vendor.
- **No invented facts.** Shop facts come only from the MCP tools over `data/campus_customs_new.db`; reports cite the tool for every number. Board amounts are built from tool results, not model text.
- **Least privilege.** Each agent sees only the tools its job needs; only the Boss can change ticket status.
- **Customer messages stay honest.** No dates we can't keep, no internal money talk, no unapproved discounts; always offer an alternative.
- **Pricing guardrails.** Up to 15% bulk discount (10+ units) without approval; more needs a human; hoodies never below $45.
- **Original data is protected.** `data/campus_customs.db` is never opened by the server; `backend/reset_db.py` restores the working copy from it.
- **Statuses are enforced in code, not just in prompts.** The only ticket statuses are `open`, `in_progress`, `resolved`; the schema and the MCP tool reject anything else, and the backend syncs the row to the Boss's final call.
- **Triage only looks.** The Boss's board triage has read-only tools and no delegation; it suggests an order but can't change or pay anything.
- **One voice to the customer.** The ticket's owner asks Customer Service for drafts; the Boss doesn't call Customer Service himself (an earlier test run did and produced a duplicate draft).
- **Everything is auditable.** Every step, tool call, handoff, refusal, triage, and human decision is in the append-only audit trail.

### Limits that keep token use in check (`backend/config.py`)

| Limit | Value | Why |
|---|---|---|
| One model for everyone | `gpt-6-luna` | The assignment's model, fixed in code so nothing more expensive can run. |
| Reasoning effort | Boss `medium`, specialists `low` | Specialists do lookups; only the final call needs more thought. |
| Model calls per agent task | 10 | Stops a looping agent; an owner coordinating two teammates needs about 8. |
| Tool calls per agent task | 14 | Same, for tools. |
| Delegation depth | 3 (Boss → A → B → C) | No endless handoff chains. |
| Handoffs per ticket | 8 | Stops "everyone calls everyone". |
| No delegating back up the chain | cycle check | A → B → A ping-pong is refused. |
| Token budget per ticket | 200,000 | New handoffs are refused once a ticket has spent it. |
| Tool result size | 3,000 chars | Long results are cut before going back to the model. |
| Model call timeout | 40 s, 2 retries | A stuck request can't freeze a ticket. |
| Routing rule | one owner per ticket | The Boss doesn't call every specialist. |

Measured in the official Problem 9 run: triage 6,881 tokens; #102 10 model calls / 23,740 tokens; #101 18 calls / 46,563 tokens; #103 19 calls / 51,741 tokens. Total 128,925 tokens for the whole board, far under the 200,000-per-ticket budget.

- **Customer drafts can't leak internals:** `save_customer_draft` refuses a draft whose subject or body contains an MCP tool name or a SKU code (`internal_leaks()` in `backend/agents.py`), logs `customer_draft_refused`, and tells Customer Service to rewrite with plain product names. Added after a Problem 9 run put “check_stock” and “CC-HOOD-NAVY” in customer drafts; the prompt rule alone wasn't enough.

---

## 6. Backend Routes (`backend/main.py`)

FastAPI app for the dashboard at `http://localhost:8000`. Shop data comes through the same MCP server the agents use. Agents only prepare payments; **the approve route is the only place cash changes**, and only after a human clicks Approve.

- `GET /api/health` — the backend is up; shows the model (`gpt-6-luna`) and which ticket is running, if any.
- `GET /api/tickets` — all three tickets with their status and `desk_state`: open → running → **resolved** (the run finished) → **signed** (a human signed or voided every check on it), plus `is_resolved`, `awaiting_signature`, and the shop date.
- `GET /api/tickets/{id}` — one ticket with its last run (the Boss's decision, every handoff and each agent's report), its approval cards, and its customer drafts.
- `POST /api/tickets/{id}/run` — manual option: starts the agent team on one ticket in the background and returns a `run_id` right away (202). Only one ticket runs at a time (409 otherwise).
- `GET /api/runs/{run_id}` — a run's status (running / done / error) and its full result.
- `GET /api/events?since=<seq>&ticket_id=&run_id=` — recent agent events from the audit trail: what each agent said, which tools it called, handoffs, drafts, and human decisions, each with a one-line summary. Poll with the last `seq` to get only new ones.
- `GET /api/triage` — the Boss's latest suggested ticket order (or null since the last reset).
- `POST /api/triage` — ask the Boss to triage the board now (read-only; 409 while a ticket is running).
- `POST /api/run-board` — **the main way to work the board**: the Boss triages, then runs every open ticket in his order, one after another, in the background (202). Nothing is paid; each ticket ends resolved with its checks waiting.
- `GET /api/run-board` — progress of that run: state (idle / running / done / error), the Boss's order, which ticket he's on, which are finished.
- `GET /api/approvals?status=pending` — the payment and purchase-order cards waiting for a human.
- `POST /api/approvals/{id}/approve` `{"approved_by": "<human name>"}` — a human approves: the MCP `pay` tool runs and cash changes. Agent names get a 403. If the pay tool refuses (not enough cash, or the vendor is blocked by an unpaid invoice), nothing changes and the card shows why. Once every item on a resolved ticket is decided, the ticket shows **signed**.
- `POST /api/approvals/{id}/reject` `{"decided_by": "...", "reason": "..."}` — a human says no; nothing is paid.
- `GET /api/drafts` — customer messages from Customer Service (drafts only, never sent).
- `POST /api/drafts/{id}/approve` `{"approved_by", "body"?}` — a human approves a draft, optionally with edited text. It is never emailed; it stays on the board. Agent names get a 403.
- `PUT /api/drafts/{id}` `{"edited_by", "subject"?, "body"?}` — edit a draft's text before approval (the first version is kept as `original_body`). It stays a draft; 409 if already approved. Logged as `draft_edited`.
- `POST /api/drafts/{id}/unapprove` `{"by"}` — a human undoes a draft approval (safe because nothing was sent); the ticket goes back to "action needed". Logged as `draft_unapproved`. Payments have no undo.
- `GET /api/cash` — the current checking balance from `cash_accounts`.
- `POST /api/reset` — copies `data/campus_customs.db` over the working copy and clears the board. The audit trail is kept, and the reset is logged in it.

The board's approvals, decisions, and drafts are saved in `output/board.json`. A bill prepared on two tickets (like invoice #501) is one card, so it can only be paid once.

---

## 7. How to Run

```bash
# one-time setup
python -m venv .venv            # activate it, then:
pip install -r requirements.txt
cp .env.example .env            # add your PORTKEY_API_KEY

# backend API, from backend/
uvicorn main:app --reload --port 8000

# dashboard, from frontend/ (opens http://localhost:5173)
npm install
npm run dev

# or run the team without the server, from backend/
python reset_db.py               # restore the working DB from the original
python run_ticket.py 102         # run the team on one ticket (audit appended)
```

`PORTKEY_API_KEY` is read from `.env` at the project root (copy `.env.example`; `.env` is never committed). The backend loads the MCP server in-process; run `python mcp_server/server.py` only to use the tools from a vibe coder. Full steps are in the root `README.md`.

---

## 8. The Dashboard (`frontend/`)

React + Vite + TypeScript, started with `npm run dev` at `http://localhost:5173`. It calls only the routes above at `http://localhost:8000` (the backend's CORS allows the Vite origin). Full design notes are in `output/design.md`.

- **Top bar:** Handsome Dan logo, a wide **checking counter** (`cash_accounts`, ticks down and pops a "−$2,400" chip when a check clears), and the shop's date from `desk.date_today`.
- **▶ Let the Boss run the board:** the one primary button. The Boss triages, then works every ticket in that order. Running a single ticket is only a small “or run just this ticket” link. Before a run, the cards can be dragged into your own order (refused after the board has run).
- **Ticket rail:** the three tickets as cards in work order, left to right, each with a 📝 note saying why it's there, a picture of what the ticket is about, a tiny row of the agents who worked it, and a stamp (RESOLVED = the agents are done; ALL DONE = every check and draft has been decided by a human).
- **Numbered steps on the cards:** everything the human must do (sign or void a check or purchase order, review a customer draft) is a numbered step on the card it belongs to, ① ② ③ across the board, with **START HERE** on the next one, the checking balance after each check, and a red warning when cash can't cover it. Hovering over a step shows **“Why step N?”** in plain numbers.
- **Draft review:** a split pane with the editable draft on the left and only what the agents used on the right. Approve keeps it on the board (never emailed); **↶ Undo approval** puts it back in your steps. Signed checks have no undo.
- **Desk log:** a live, color-coded log of what each agent said and which tools it used, plus a **Summary** tab: the Boss's reason for the ticket's place, then a numbered timeline of the work in order (an agent called twice shows twice), with off-shift agents listed at the end.
- **Human approval:** each payment or purchase order needs a human name. Only then does the backend call the MCP `pay` tool; refusals show the reason and change nothing.
- **Deep links:** `?ticket=101&tab=summary` and `?review=<draft id>` (used for the resolved-board screenshots).

---

## 9. Results: the Official Problem 9 Run

Reset to the original database (audit #2439), then one click on **“Let the Boss run the board”** (audit entries #2440–#2638):

| Step | What happened | Checking |
|---|---|---|
| Start | `data/campus_customs_new.db` reset from the original | **$3,400.00** |
| Boss triage | Order #102 → #101 → #103 (rent first, then the overdue invoice) | $3,400.00 |
| Boss runs #102, #101, #103 | All three resolved with no manual hand-off; every handoff matched the Problem 6 plan. Shared checks (rent prepared on #102 and #101; invoice #501 on #101 and #103) appeared once each. Both customer drafts passed the new internal-text check on the first try. | $3,400.00 |
| Step 1 | Rent, lease #1, **−$2,400** (signed) | $1,000.00 |
| Step 2 | Invoice #501, **−$840** (signed) | $160.00 |
| Step 3 | Tee PO, 1 × CC-TEE-WHITE S, **−$8** (signed) | $152.00 |
| Step 4 | Draft to Tauhid approved (no edits, never sent) | $152.00 |
| Step 5 | Hoodie PO, 12 × $22 = $264: flagged in red, **refused** by the pay tool twice (no negative balances), then voided | $152.00 |
| Step 6 | Draft to the Yale AI Club approved (no edits, never sent) | **$152.00** |

All three tickets ended **resolved** and **all done**; the ending balance matches `cash_accounts.checking` = 152.00; total 128,925 tokens on gpt-6-luna (run IDs: triage `ebf0b016a7`, #102 `51f84357f8`, #101 `bf00827117`, #103 `6bd3e6a173`). Earlier passes stay in the append-only audit trail and are listed in the Cash tab. Details: `output/desk_tickets.html` (Actual and Cash tabs), `output/resolved_tickets.json`, `output/resolved_board.html`.
