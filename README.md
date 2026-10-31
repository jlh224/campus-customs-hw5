# Campus Customs: Multi-Agent Back Office (MGT 409E, Homework 5)

A five-agent team (Boss, Inventory, Accounting, Facilities, Customer Service) that works the Campus Customs desk tickets through an MCP server, with a FastAPI backend and a React dashboard where a human signs every payment.

- **Model:** every agent uses **`gpt-6-luna`** through Portkey (`PORTKEY_API_KEY`). No other model is used.
- **Money:** agents only *prepare* payments. Cash changes only when a human approves on the board, and the `pay` tool refuses anything that would make checking go negative.
- **Customers and vendors:** nothing is ever emailed or sent. Customer messages are drafts that stay on the board.

## What's in the repo

| Path | What it is |
|---|---|
| `data/campus_customs.db` | The original database. Never written to; it's the reset point. |
| `data/campus_customs_new.db` | The working copy the app reads and writes. Committed **after** the official run (checking $152.00), so the board opens showing the results. |
| `mcp_server/server.py` | FastMCP server with the 14 shop tools ([its README](mcp_server/README.md)). |
| `backend/` | FastAPI app (`main.py`), PydanticAI agents (`agents.py`), data types (`models.py`), one prompt per agent in `prompts/`, and `reset_db.py`. |
| `frontend/` | React + Vite + TypeScript dashboard. |
| `output/` | `harness.md`, `mcp_smoke.json`, `desk_tickets.html` (Expected, Actual, Cash, Reflection), `design.md`, `resolved_tickets.json`, `resolved_board.html` (+ `resolved_board_images/`), `audit_trail.json`, `board.json` (dashboard state), `github_url.txt`. |
| `AI_prompts.md` | The prompts I gave my vibe coder, one section per problem. |
| `.mcp.json` | Connects the MCP server to a vibe coder (Claude Code). |

## Setup (once)

You need Python 3.11+ and Node 18+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then put your Portkey key in .env
cd frontend && npm install && cd ..
```

`.env` is in `.gitignore`. Never commit it.

## Run it

### 1. Copy the original database to the working copy (when you need a clean run)

The repo ships the working copy *after* the official run, so the board shows the resolved tickets and checking at $152.00. To start clean, copy the original over the working copy:

```bash
python backend/reset_db.py
# same thing by hand:  cp data/campus_customs.db data/campus_customs_new.db
```

### 2. Start the MCP server

The backend loads `mcp_server/server.py` itself (in-process), so for the dashboard **you don't need a separate terminal**. To use the tools from a vibe coder or another client:

```bash
python mcp_server/server.py          # stdio (what .mcp.json uses; Claude Code starts it for you)
python mcp_server/server.py --http   # HTTP at http://127.0.0.1:8001/mcp
```

### 3. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API is at `http://localhost:8000` (routes are listed in `output/harness.md`, section 6). CORS allows the Vite page at `http://localhost:5173`.

### 4. Start the React board

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The board calls the backend at `http://localhost:8000` (override with `VITE_API_URL`).

### 5. Reset the database before a full three-ticket run

Before running all three tickets, reset so the run starts from the original data (checking $3,400.00, invoice #501 open, rent due 2026-09-02):

- On the board: click **Reset desk** (top right). This copies the original database over the working copy, clears the board, and logs a `db_reset` entry in the audit trail. Or:
- `curl -X POST http://localhost:8000/api/reset`, or `python backend/reset_db.py` (database only).

Then click **▶ Let the Boss run the board**. The Boss ranks the tickets (rent first, then the overdue invoice, then the discount) and runs #102, #101 and #103 in that order. When he's done, do the numbered steps on the cards left to right. Type your name in **Signing as**, then:

- **Sign** or **Void** each check and purchase order (hover over a step to see why it comes next).
- **Review and approve** each customer draft.

Expected result: checking $3,400 → $1,000 → $160 → $152. The $264 hoodie restock is refused by the pay tool (not enough cash), so void it.

To run a single ticket from the command line instead: `cd backend && python run_ticket.py 102`.

## Where to look

- **Plan vs. what happened, cash, and reflection:** double-click `output/desk_tickets.html`.
- **Screenshots of the resolved board:** double-click `output/resolved_board.html`.
- **Every agent step, tool call and human approval:** `output/audit_trail.json` (append-only; earlier test runs are kept).
- **Tables, tools, agents, routes, dashboard, safety rules:** `output/harness.md`.
