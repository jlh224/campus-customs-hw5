"""The board: runs, items waiting for human approval, and customer drafts.

Saved to output/board.json so it survives a server reload. Shop facts (cash,
stock, invoices) are NOT stored here; they live in the database and come
through MCP. The board only remembers what the agents prepared and what the
human decided.

Approval ids are stable, so the same bill prepared on two tickets (e.g.
invoice #501 on 101 and 103) is one card, and can only be paid once:
    pay-invoice-501, pay-rent-1, po-1-CC-HOOD-NAVY-M
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from config import OUTPUT_DIR
from models import TicketRunResult

BOARD_PATH = OUTPUT_DIR / "board.json"
OPEN_STATUSES = {"pending", "refused"}  # refused = pay tool said no; still needs a human decision
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty() -> dict:
    return {"runs": {}, "approvals": [], "drafts": [], "triage": None, "manual_order": None}


def load() -> dict:
    if not BOARD_PATH.exists():
        return _empty()
    try:
        return json.loads(BOARD_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _empty()


def _save(board: dict) -> None:
    BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = BOARD_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(board, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, BOARD_PATH)


def clear() -> None:
    with _lock:
        _save(_empty())


def record_run_start(ticket_id: int, run_id: str) -> None:
    with _lock:
        board = load()
        board["runs"][str(ticket_id)] = {"run_id": run_id, "status": "running", "started_at": _now(), "result": None}
        _save(board)


def _approval_from_payment(p: dict, ticket_id: int, run_id: str) -> dict:
    return {
        "id": f"pay-{p['kind']}-{p['ref_id']}",
        "type": "payment",
        "ticket_ids": [ticket_id],
        "run_id": run_id,
        "status": "pending",
        "title": f"Pay {p['kind']} #{p['ref_id']} — ${p['amount']:,.2f} to {p['payee']}",
        "amount": p["amount"],
        "pay_args": {"kind": p["kind"], "ref_id": p["ref_id"], "account": p["account"]},
        "item": p,
        "created_at": _now(),
    }


def _approval_from_po(po: dict, ticket_id: int, run_id: str) -> dict:
    return {
        "id": f"po-{po['vendor_id']}-{po['sku']}-{po['size']}",
        "type": "purchase_order",
        "ticket_ids": [ticket_id],
        "run_id": run_id,
        "status": "pending",
        "title": f"Purchase order — {po['qty']} × {po['sku']} {po['size']} from {po['vendor_name']} (${po['total_cost']:,.2f})",
        "amount": po["total_cost"],
        "pay_args": {
            "kind": "purchase_order", "ref_id": po["vendor_id"],
            "sku": po["sku"], "size": po["size"], "qty": po["qty"],
        },
        "item": po,
        "created_at": _now(),
    }


def record_run_result(result: TicketRunResult) -> None:
    """Store a finished run and put its payment requests, POs, and drafts on the board."""
    data = result.model_dump(mode="json")
    tid = result.ticket_id
    with _lock:
        board = load()
        board["runs"][str(tid)] = {
            "run_id": result.run_id,
            "status": "done" if result.ok else "error",
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "result": data,
        }
        # A re-run replaces this ticket's undecided items; decided ones stay as history.
        kept = []
        for a in board["approvals"]:
            if a["status"] in OPEN_STATUSES and tid in a["ticket_ids"]:
                a["ticket_ids"] = [t for t in a["ticket_ids"] if t != tid]
                if not a["ticket_ids"]:
                    continue
            kept.append(a)
        board["approvals"] = kept

        new_items = [_approval_from_payment(p, tid, result.run_id) for p in data["payment_requests"]]
        new_items += [_approval_from_po(po, tid, result.run_id) for po in data["purchase_orders"]]
        by_id = {a["id"]: a for a in board["approvals"]}
        for item in new_items:
            existing = by_id.get(item["id"])
            if existing is None:
                board["approvals"].append(item)
                by_id[item["id"]] = item
            elif existing["status"] in OPEN_STATUSES:
                if tid not in existing["ticket_ids"]:
                    existing["ticket_ids"].append(tid)
            # already approved/paid: don't put the same bill back on the board

        board["drafts"] = [d for d in board["drafts"] if d.get("ticket_id") != tid]
        board["drafts"] += [
            {**d, "id": f"draft-{tid}-{i + 1}", "run_id": result.run_id, "status": "draft"}
            for i, d in enumerate(data["customer_drafts"])
        ]
        _save(board)


def get_approval(approval_id: str) -> dict | None:
    return next((a for a in load()["approvals"] if a["id"] == approval_id), None)


def decide(approval_id: str, status: str, decided_by: str, outcome: Any = None, note: str | None = None) -> dict:
    with _lock:
        board = load()
        for a in board["approvals"]:
            if a["id"] == approval_id:
                a.update(status=status, decided_by=decided_by, decided_at=_now(), outcome=outcome, note=note)
                _save(board)
                return a
    raise KeyError(approval_id)


def mark_signed_if_done(ticket_id: int, signed_by: str) -> bool:
    """Mark a finished run 'signed' once every approval on its ticket is decided. True if it just got signed."""
    with _lock:
        state = load()
        run = state["runs"].get(str(ticket_id))
        if not run or run.get("status") != "done" or run.get("signed_at"):
            return False
        mine = [a for a in state["approvals"] if ticket_id in a["ticket_ids"]]
        drafts = [d for d in _with_draft_ids(state)["drafts"] if d.get("ticket_id") == ticket_id]
        if not mine and not drafts:
            return False
        if any(a["status"] in OPEN_STATUSES for a in mine) or any(d.get("status") != "approved" for d in drafts):
            return False
        run.update(signed_by=signed_by, signed_at=_now())
        _save(state)
        return True


def open_items_for(ticket_id: int) -> list[dict]:
    return [a for a in load()["approvals"] if ticket_id in a["ticket_ids"] and a["status"] in OPEN_STATUSES]


def save_triage(triage: dict) -> None:
    with _lock:
        state = load()
        state["triage"] = triage
        _save(state)


def _with_draft_ids(state: dict) -> dict:
    """Older boards stored drafts without ids/status; give them stable ones."""
    counts: dict[int, int] = {}
    for d in state.get("drafts", []):
        tid = d.get("ticket_id")
        counts[tid] = counts.get(tid, 0) + 1
        d.setdefault("id", f"draft-{tid}-{counts[tid]}")
        d.setdefault("status", "draft")
    return state


def drafts() -> list[dict]:
    return _with_draft_ids(load())["drafts"]


def pending_drafts_for(ticket_id: int) -> list[dict]:
    return [d for d in drafts() if d.get("ticket_id") == ticket_id and d.get("status") != "approved"]


def approve_draft(draft_id: str, approved_by: str, body: str | None) -> dict:
    """A human reviewed the draft (optionally edited it) and approved it. It is NOT sent; it stays on the board."""
    with _lock:
        state = _with_draft_ids(load())
        for d in state["drafts"]:
            if d["id"] == draft_id:
                if body is not None and body.strip() and body.strip() != d["body"].strip():
                    d.setdefault("original_body", d["body"])
                    d["body"] = body.strip()
                    d["edited"] = True
                d.update(status="approved", approved_by=approved_by, approved_at=_now(), sent=False)
                _save(state)
                return d
    raise KeyError(draft_id)


def get_manual_order() -> list[int] | None:
    return load().get("manual_order")


def set_manual_order(order: list[int] | None) -> None:
    with _lock:
        state = load()
        state["manual_order"] = order
        _save(state)


def unapprove_draft(draft_id: str) -> dict:
    """Undo a draft approval (it was never sent, so this is safe). Any edits to the text are kept."""
    with _lock:
        state = _with_draft_ids(load())
        for d in state["drafts"]:
            if d["id"] == draft_id:
                for k in ("approved_by", "approved_at"):
                    d.pop(k, None)
                d["status"] = "draft"
                run = state["runs"].get(str(d["ticket_id"]))
                if run:  # the ticket is no longer all done
                    run.pop("signed_at", None)
                    run.pop("signed_by", None)
                _save(state)
                return d
    raise KeyError(draft_id)


def edit_draft(draft_id: str, subject: str | None, body: str | None) -> dict:
    """Change an unapproved draft's text (the first version is kept as original_body). Approval is still a human's job."""
    with _lock:
        state = _with_draft_ids(load())
        for d in state["drafts"]:
            if d["id"] == draft_id:
                if d.get("status") == "approved":
                    raise ValueError("approved")
                if body is not None and body.strip() and body.strip() != d["body"].strip():
                    d.setdefault("original_body", d["body"])
                    d["body"] = body.strip()
                    d["edited"] = True
                if subject is not None and subject.strip() and subject.strip() != d["subject"].strip():
                    d.setdefault("original_subject", d["subject"])
                    d["subject"] = subject.strip()
                    d["edited"] = True
                _save(state)
                return d
    raise KeyError(draft_id)
