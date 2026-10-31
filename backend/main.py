"""Campus Customs backend: FastAPI routes for the React dashboard.

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000
Then the dashboard calls http://localhost:8000/api/...

Shop facts (tickets, cash) come from the campus-customs MCP server, the same
one the agents use. Agents only PREPARE payments; the approve route below is
the only place money moves, and only after a human clicks Approve (it calls
the MCP pay tool with the human's name).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import audit
import board
from agents import run_ticket, run_triage
from config import MODEL_NAME
from mcp_client import call_tool
from models import AGENT_NAMES
from reset_db import reset_database

app = FastAPI(title="Campus Customs Agent Desk", version="1.0")
app.add_middleware(
    CORSMiddleware,
    # The Vite dev server. CORS_ORIGINS (comma-separated) can replace this list, e.g. for a second desk on 5174.
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# One ticket run at a time: runs share one cash balance, so they shouldn't race.
_active: dict[str, Any] = {"task": None, "ticket_id": None, "run_id": None}
# "Let the Boss run the board": triage, then every open ticket in the Boss's order.
_board_run: dict[str, Any] = {"state": "idle", "order": [], "current": None, "finished": [], "error": None,
                              "started_at": None, "finished_at": None}


class ApproveBody(BaseModel):
    approved_by: str = Field(description="Name of the human approving. Agents cannot approve.", min_length=1)


class RejectBody(BaseModel):
    decided_by: str = Field(min_length=1)
    reason: str | None = None


def _running() -> bool:
    task = _active["task"]
    return task is not None and not task.done()


# ---------- Health ----------

@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": MODEL_NAME, "running_ticket": _active["ticket_id"] if _running() else None}


# ---------- Tickets ----------

@app.get("/api/tickets")
async def list_tickets() -> dict:
    """The tickets with their status and desk state.

    status:     the database status (open / in_progress / resolved)
    desk_state: open -> running -> resolved (the run finished) -> signed (a human
                signed or voided every check on it)
    """
    state = board.load()
    data = await call_tool("list_tickets")
    out = []
    for t in data["tickets"]:
        run = state["runs"].get(str(t["id"])) or {}
        running = _running() and _active["ticket_id"] == t["id"]
        open_items = len(board.open_items_for(t["id"]))
        drafts_pending = len(board.pending_drafts_for(t["id"]))
        if running:
            desk_state = "running"
        elif t["status"] == "resolved" and run.get("signed_at") and drafts_pending == 0:
            desk_state = "signed"
        else:
            desk_state = t["status"]
        out.append({
            **t,
            "is_resolved": t["status"] == "resolved",
            "is_running": running,
            "desk_state": desk_state,
            "awaiting_signature": t["status"] == "resolved" and open_items > 0,
            "drafts_pending": drafts_pending,
            "action_needed": t["status"] == "resolved" and (open_items > 0 or drafts_pending > 0),
            "signed_by": run.get("signed_by"),
            "last_run": {k: run[k] for k in ("run_id", "status", "started_at", "finished_at") if k in run} or None,
            "open_approvals": open_items,
        })
    return {"date_today": data["date_today"], "tickets": out, "manual_order": board.get_manual_order()}


@app.get("/api/tickets/{ticket_id}")
async def ticket_detail(ticket_id: int) -> dict:
    """One ticket, its last run (decision, handoffs, per-agent reports), approvals, and drafts."""
    data = await call_tool("get_ticket", {"ticket_id": ticket_id})
    if not data.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}")
    state = board.load()
    return {
        "ticket": data["ticket"],
        "run": state["runs"].get(str(ticket_id)),
        "approvals": [a for a in state["approvals"] if ticket_id in a["ticket_ids"]],
        "drafts": [d for d in state["drafts"] if d.get("ticket_id") == ticket_id],
    }


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket_route(ticket_id: int) -> dict:
    """Start the agent team on one ticket. Returns at once; watch /api/events for progress."""
    if _running():
        raise HTTPException(409, f"Ticket {_active['ticket_id']} is still running. Wait for it to finish.")
    data = await call_tool("get_ticket", {"ticket_id": ticket_id})
    if not data.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}")

    _active.update(task=asyncio.create_task(_run_one(ticket_id)), ticket_id=ticket_id, run_id=None)
    return {"started": True, "ticket_id": ticket_id}


async def _run_one(ticket_id: int) -> None:
    """Run one ticket and put its results on the board (shared by the single and whole-board routes)."""
    run_id = uuid.uuid4().hex[:10]
    board.record_run_start(ticket_id, run_id)
    _active.update(ticket_id=ticket_id, run_id=run_id)
    result = await run_ticket(ticket_id, run_id=run_id)
    board.record_run_result(result)


@app.get("/api/run-board")
async def board_run_status() -> dict:
    """Progress of the Boss's whole-board run: state, his order, which ticket he's on, which are finished."""
    return {"board_run": _board_run, "running_ticket": _active["ticket_id"] if _running() else None}


@app.post("/api/run-board", status_code=202)
async def run_board() -> dict:
    """The Boss triages the board, then works every open ticket in his order, one after another.

    Nothing is paid: each ticket ends resolved with its checks waiting. When the whole board is done,
    the dashboard tells the human it's time to sign, in order.
    """
    if _running():
        raise HTTPException(409, "The team is already working. Wait for it to finish.")

    async def worker() -> None:
        _board_run.update(state="running", order=[], current=None, finished=[], error=None, order_source=None,
                          started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), finished_at=None)
        audit.append("board_run_start")
        try:
            _board_run["current"] = "triage"
            triage_result = await run_triage()
            board.save_triage(triage_result)
            order = [i["ticket_id"] for i in sorted(triage_result["order"], key=lambda i: i["rank"])]
            manual = board.get_manual_order()
            if manual:  # the human overrode the Boss: work in their order, Boss's reasons stay as notes
                order = [t for t in manual if t in order] + [t for t in order if t not in manual]
                _board_run["order_source"] = "human"
            else:
                _board_run["order_source"] = "boss"
            open_ids = {t["id"] for t in (await call_tool("list_tickets"))["tickets"] if t["status"] != "resolved"}
            _board_run["order"] = order
            for ticket_id in order:
                if ticket_id not in open_ids:
                    continue
                _board_run["current"] = ticket_id
                await _run_one(ticket_id)
                _board_run["finished"].append(ticket_id)
            _board_run.update(state="done", current=None)
        except Exception as exc:  # keep what finished; report the failure on the board
            _board_run.update(state="error", current=None, error=f"{type(exc).__name__}: {exc}")
        finally:
            _board_run["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            audit.append("board_run_end", state=_board_run["state"], order=_board_run["order"],
                         finished=_board_run["finished"], error=_board_run["error"])

    _active.update(task=asyncio.create_task(worker()), ticket_id=None, run_id=None)
    return {"started": True}


@app.get("/api/runs/{run_id}")
async def run_status(run_id: str) -> dict:
    for tid, run in board.load()["runs"].items():
        if run["run_id"] == run_id:
            return {"ticket_id": int(tid), **run}
    raise HTTPException(404, f"No run {run_id}")


# ---------- Boss triage ----------

@app.get("/api/triage")
async def get_triage() -> dict:
    """The Boss's latest suggested ticket order (or null if he hasn't been asked since the last reset)."""
    return {"triage": board.load().get("triage")}


@app.post("/api/triage")
async def triage() -> dict:
    """Ask the Boss which ticket to work first. Read-only: he looks at tickets, cash, lease, and invoices; nothing changes."""
    if _running():
        raise HTTPException(409, f"Ticket {_active['ticket_id']} is running. Ask for an order when it finishes.")
    result = await run_triage()
    board.save_triage(result)
    return {"triage": result}


# ---------- Agent events ----------

def _summary(e: dict) -> str:
    who = e.get("agent") or "desk"
    ev = e["event"]
    if ev == "model_step":
        calls = ", ".join(c["tool"] for c in e.get("tool_calls") or [])
        return f"{who} thinks: {e.get('text') or ''}".strip() + (f" → calls {calls}" if calls else "")
    if ev == "tool_call":
        return f"{who} calls {e['tool']}({e.get('args')})"
    if ev == "tool_result":
        return f"{who} got {e['tool']} result"
    if ev == "delegation_start":
        return f"{who} → {e['to_agent']}: {e.get('task')}"
    if ev == "delegation_end":
        return f"{e['to_agent']} reported back to {who}: {(e.get('report') or {}).get('summary', '')}"
    if ev == "agent_end":
        out = e.get("output") or {}
        return f"{who} finished: {out.get('summary') or out.get('decision') or ''}"
    if ev == "customer_draft_saved":
        return f"{who} saved a draft for {(e.get('draft') or {}).get('to')}"
    if ev in ("agent_error", "delegation_failed", "tool_error"):
        return f"{who} error: {e.get('error')}"
    if ev == "delegation_refused":
        return f"{who} → {e.get('to_agent')} refused: {e.get('reason')}"
    if ev == "triage_end":
        return "boss suggested an order: " + " → ".join(f"#{i['ticket_id']}" for i in e.get("order") or [])
    if ev == "draft_edited":
        return f"{e.get('edited_by')} edited draft {e.get('draft_id')} (still needs approval)"
    if ev == "draft_unapproved":
        return f"{e.get('by')} undid the approval of draft {e.get('draft_id')}"
    if ev == "draft_approved":
        return f"{e.get('approved_by')} approved the customer draft {e.get('draft_id')} (not sent)"
    if ev == "order_override":
        return "human reordered the board: " + " \u2192 ".join(f"#{t}" for t in e.get("order") or [])
    if ev == "approval_decided":
        return f"{e.get('decided_by')} {e.get('status')} {e.get('approval_id')}"
    return ev.replace("_", " ")


@app.get("/api/events")
async def events(
    since: int = Query(0, description="Only events with seq greater than this"),
    ticket_id: int | None = None,
    run_id: str | None = None,
    limit: int = Query(200, le=1000),
) -> dict:
    """Recent agent events from the audit trail: what each agent said and which tools it used.

    Poll with ?since=<last seq you saw> to get only new events.
    """
    items = audit.read(since)
    if ticket_id is not None:
        items = [e for e in items if e.get("ticket_id") == ticket_id]
    if run_id:
        items = [e for e in items if e.get("run_id") == run_id]
    items = items[-limit:]
    return {
        "events": [{**e, "summary": _summary(e)} for e in items],
        "last_seq": items[-1]["seq"] if items else since,
        "running": _running(),
        "running_ticket": _active["ticket_id"] if _running() else None,
    }


# ---------- Human approvals (the only place money moves) ----------

@app.get("/api/approvals")
async def list_approvals(status: str | None = None) -> dict:
    items = board.load()["approvals"]
    if status:
        items = [a for a in items if a["status"] == status]
    return {"approvals": items}


async def _maybe_sign(ticket_ids: list[int], decided_by: str) -> list[int]:
    """A resolved ticket is SIGNED once the human has signed or voided every item on it."""
    signed = []
    for tid in ticket_ids:
        if board.mark_signed_if_done(tid, decided_by):
            await call_tool("update_ticket", {
                "ticket_id": tid, "status": "resolved",
                "note": f"Signed by {decided_by}: every payment and purchase order on this ticket is decided.",
            })
            signed.append(tid)
    return signed


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: str, body: ApproveBody) -> dict:
    """A human clicked Approve: pay through the MCP pay tool. Refusals (no cash, vendor blocked) change nothing."""
    if body.approved_by.strip().lower().replace(" ", "_") in AGENT_NAMES + ("agent",):
        raise HTTPException(403, "Only a human can approve a payment, not an agent.")
    item = board.get_approval(approval_id)
    if item is None:
        raise HTTPException(404, f"No approval {approval_id}")
    if item["status"] not in board.OPEN_STATUSES:
        raise HTTPException(409, f"{approval_id} is already {item['status']}.")

    outcome = await call_tool("pay", {**item["pay_args"], "approved_by": body.approved_by.strip()})
    status = "paid" if outcome.get("paid") else "refused"
    item = board.decide(approval_id, status, body.approved_by.strip(), outcome)
    audit.append("approval_decided", approval_id=approval_id, status=status, decided_by=body.approved_by.strip(),
                 ticket_ids=item["ticket_ids"], outcome=outcome)
    signed = await _maybe_sign(item["ticket_ids"], body.approved_by.strip()) if status == "paid" else []
    cash = await call_tool("get_cash_balance")
    return {"approval": item, "paid": status == "paid", "message": outcome.get("message"),
            "tickets_signed": signed, "cash": cash}


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: str, body: RejectBody) -> dict:
    """A human said no: nothing is paid, and the item leaves the queue."""
    item = board.get_approval(approval_id)
    if item is None:
        raise HTTPException(404, f"No approval {approval_id}")
    if item["status"] not in board.OPEN_STATUSES:
        raise HTTPException(409, f"{approval_id} is already {item['status']}.")
    item = board.decide(approval_id, "rejected", body.decided_by.strip(), note=body.reason)
    audit.append("approval_decided", approval_id=approval_id, status="rejected", decided_by=body.decided_by.strip(),
                 ticket_ids=item["ticket_ids"], reason=body.reason)
    signed = await _maybe_sign(item["ticket_ids"], body.decided_by.strip())
    return {"approval": item, "tickets_signed": signed}


# ---------- Drafts, cash, reset ----------

@app.get("/api/drafts")
async def drafts() -> dict:
    """Customer messages written by Customer Service. Never sent; they stay on the board."""
    return {"drafts": board.drafts()}


class DraftApproveBody(BaseModel):
    approved_by: str = Field(min_length=1)
    body: str | None = None  # edited text, if the human changed it


@app.post("/api/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str, body: DraftApproveBody) -> dict:
    """A human reviewed (and maybe edited) a customer draft and approved it. Nothing is emailed: it stays on the board."""
    who = body.approved_by.strip()
    if who.lower().replace(" ", "_") in AGENT_NAMES + ("agent",):
        raise HTTPException(403, "Only a human can approve a customer message, not an agent.")
    try:
        draft = board.approve_draft(draft_id, who, body.body)
    except KeyError:
        raise HTTPException(404, f"No draft {draft_id}")
    audit.append("draft_approved", draft_id=draft_id, ticket_id=draft.get("ticket_id"), approved_by=who,
                 edited=bool(draft.get("edited")), sent=False)
    signed = await _maybe_sign([draft["ticket_id"]], who)
    return {"draft": draft, "tickets_signed": signed}


class DraftUndoBody(BaseModel):
    by: str = Field(min_length=1)


@app.post("/api/drafts/{draft_id}/unapprove")
async def unapprove_draft(draft_id: str, body: DraftUndoBody) -> dict:
    """Undo a draft approval. Safe because drafts are never sent; the ticket goes back to 'action needed'.
    (Payments have no undo: once a human signs, the money has moved.)"""
    if body.by.strip().lower().replace(" ", "_") in AGENT_NAMES + ("agent",):
        raise HTTPException(403, "Only a human can undo an approval, not an agent.")
    try:
        draft = board.unapprove_draft(draft_id)
    except KeyError:
        raise HTTPException(404, f"No draft {draft_id}")
    audit.append("draft_unapproved", draft_id=draft_id, ticket_id=draft.get("ticket_id"), by=body.by.strip())
    return {"draft": draft}


class DraftEditBody(BaseModel):
    edited_by: str = Field(min_length=1)
    subject: str | None = None
    body: str | None = None


@app.put("/api/drafts/{draft_id}")
async def edit_draft(draft_id: str, body: DraftEditBody) -> dict:
    """Edit a draft's text before approval. It stays a draft: a human still has to approve it."""
    try:
        draft = board.edit_draft(draft_id, body.subject, body.body)
    except KeyError:
        raise HTTPException(404, f"No draft {draft_id}")
    except ValueError:
        raise HTTPException(409, "Undo the approval before editing an approved draft.")
    audit.append("draft_edited", draft_id=draft_id, ticket_id=draft.get("ticket_id"), edited_by=body.edited_by.strip())
    return {"draft": draft}


# ---------- Human override of the Boss's order ----------

class OrderBody(BaseModel):
    order: list[int] | None = None  # null clears the override (the Boss decides again)


@app.put("/api/order")
async def set_order(body: OrderBody) -> dict:
    """The human dragged the cards into a different order; the Boss will work the board in that order."""
    if _running():
        raise HTTPException(409, "The team is working. Reorder before or after a run.")
    if body.order is not None:
        listed = (await call_tool("list_tickets"))["tickets"]
        known = {t["id"] for t in listed}
        if set(body.order) - known:
            raise HTTPException(400, f"Unknown ticket ids: {sorted(set(body.order) - known)}")
        if not any(t["status"] != "resolved" for t in listed):
            # Reordering after the Boss already worked the board would misreport the order the work happened in.
            raise HTTPException(409, "Every ticket is already resolved. Reset the desk to choose a new order.")
    board.set_manual_order(body.order)
    audit.append("order_override", order=body.order, by="human")
    return {"manual_order": body.order}


@app.get("/api/cash")
async def cash() -> dict:
    """Current checking balance from cash_accounts (via MCP)."""
    data = await call_tool("get_cash_balance")
    checking = next((a for a in data["accounts"] if a["name"] == "checking"), None)
    return {"checking": checking["balance"] if checking else None, "as_of": checking["date"] if checking else None,
            "accounts": data["accounts"]}


@app.post("/api/reset")
async def reset() -> dict:
    """Restore the working DB from the original and clear the board. The audit trail is kept (append-only)."""
    if _running():
        raise HTTPException(409, "A ticket is running. Wait for it to finish before resetting.")
    message = reset_database()
    board.clear()
    _board_run.update(state="idle", order=[], current=None, finished=[], error=None, started_at=None, finished_at=None)
    audit.append("db_reset", message=message)
    return {"reset": True, "message": message, "cash": await cash()}
