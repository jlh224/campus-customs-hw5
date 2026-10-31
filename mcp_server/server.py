"""Campus Customs MCP server: shop-data tools shared by every HW5 agent.

All tools read data/campus_customs_new.db (the working copy). The original
data/campus_customs.db is never opened here; it is only the reset point.
Tools return what is in the database and nothing else. A missing row comes
back as found=False with a message, never a guess.

Only two tools write: update_ticket (ticket status/notes) and pay (money).
pay needs a human approver's name and refuses if cash would go negative.
The backend never gives pay to an agent; only the human approval route
(POST /api/approvals/{id}/approve in backend/main.py) calls it.

Run from this folder (stdio):  python server.py
Run (HTTP):                    python server.py --http
HTTP URL:                      http://127.0.0.1:8001/mcp
"""

from __future__ import annotations

import argparse
import calendar
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")


def _connect(write: bool = False) -> sqlite3.Connection:
    """Open the working copy. Read-only unless a tool explicitly needs to write."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    mode = "rw" if write else "ro"
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _db(write: bool = False) -> Iterator[sqlite3.Connection]:
    """Connection that commits on success (write mode), rolls back on error, and always closes."""
    conn = _connect(write)
    try:
        yield conn
        if write:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _today(conn: sqlite3.Connection) -> date:
    """The shop's 'today' comes from desk.date_today, not the computer clock."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


@mcp.tool
def check_stock(sku: str, size: str | None = None) -> dict:
    """Check how many units of a SKU are on hand, by size.

    Reads the inventory table. Pass a size (e.g. "S", "M", "OS") for one
    size, or leave it out to get every size of that SKU. Use this to spot
    shortfalls: compare qty to what a ticket asks for.
    """
    sku = sku.strip().upper()
    size = size.strip().upper() if size else None
    with _db() as conn:
        rows = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory "
            "WHERE sku = ? ORDER BY rowid",
            (sku,),
        ).fetchall()
    if not rows:
        return {"found": False, "sku": sku, "message": f"No inventory rows for SKU {sku}."}

    sizes = [
        {"size": r["size"], "qty": r["qty"], "location": r["location"], "in_stock": r["qty"] > 0}
        for r in rows
    ]
    if size:
        match = [s for s in sizes if s["size"] == size]
        if not match:
            return {
                "found": False,
                "sku": sku,
                "name": rows[0]["name"],
                "message": f"SKU {sku} has no size {size}.",
                "sizes_carried": [s["size"] for s in sizes],
            }
        sizes = match
    return {
        "found": True,
        "sku": sku,
        "name": rows[0]["name"],
        "sizes": sizes,
        "total_qty": sum(s["qty"] for s in sizes),
    }


@mcp.tool
def get_vendor_status(vendor_id: int | None = None) -> dict:
    """Show a vendor's lead time, open invoices, and whether it can ship.

    Reads the vendors and invoices tables, plus desk.date_today for overdue
    days. A vendor will not ship new product while it has an open (unpaid)
    invoice, so can_ship is False until every open invoice is paid. Leave
    vendor_id out to list every vendor (use specialty to pick the right one).
    """
    with _db() as conn:
        today = _today(conn)
        if vendor_id is None:
            vendors = conn.execute(
                "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"
            ).fetchall()
        else:
            vendors = conn.execute(
                "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?",
                (vendor_id,),
            ).fetchall()
        if not vendors:
            return {"found": False, "vendor_id": vendor_id, "message": f"No vendor with id {vendor_id}."}

        result = []
        for v in vendors:
            invoices = conn.execute(
                "SELECT id, amount, due_date, status, description FROM invoices "
                "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
                (v["id"],),
            ).fetchall()
            open_invoices = []
            for inv in invoices:
                days_late = (today - date.fromisoformat(inv["due_date"])).days
                open_invoices.append({
                    "invoice_id": inv["id"],
                    "amount": inv["amount"],
                    "due_date": inv["due_date"],
                    "status": inv["status"],
                    "description": inv["description"],
                    "days_overdue": max(days_late, 0),
                    "overdue": days_late > 0,
                })
            result.append({
                "vendor_id": v["id"],
                "name": v["name"],
                "specialty": v["specialty"],
                "lead_days": v["lead_days"],
                "open_invoices": open_invoices,
                "open_balance": round(sum(i["amount"] for i in open_invoices), 2),
                "can_ship": not open_invoices,
            })
    return {"found": True, "date_today": today.isoformat(), "vendors": result}


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Look up a shop lease: landlord, monthly rent, and when rent is next due.

    Reads the leases table, plus desk.date_today to count days until rent is
    due (negative means overdue).
    """
    with _db() as conn:
        today = _today(conn)
        row = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
            "FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
    if row is None:
        return {"found": False, "lease_id": lease_id, "message": f"No lease with id {lease_id}."}

    days_until_due = (date.fromisoformat(row["next_due"]) - today).days
    return {
        "found": True,
        "lease_id": row["id"],
        "space_name": row["space_name"],
        "landlord": row["landlord"],
        "monthly_rent": row["monthly_rent"],
        "next_due": row["next_due"],
        "date_today": today.isoformat(),
        "days_until_due": days_until_due,
        "overdue": days_until_due < 0,
        "notes": row["notes"],
    }


TICKET_COLUMNS = (
    "id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at"
)
TICKET_STATUSES = ("open", "in_progress", "resolved")
PAY_KINDS = ("invoice", "rent", "purchase_order")
CASH_BUFFER = 100.0  # shop rule: checking should never drop below this (pay itself only blocks < $0)
# Names that may never approve a payment: the agents themselves.
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service", "agent"}


@mcp.tool
def list_tickets() -> dict:
    """List every ticket (open and resolved), oldest first, with its status and the shop's date.

    Reads the tickets table and desk.date_today. The board uses this.
    """
    with _db() as conn:
        today = _today(conn)
        rows = conn.execute(f"SELECT {TICKET_COLUMNS} FROM tickets ORDER BY id").fetchall()
    return {"date_today": today.isoformat(), "count": len(rows), "tickets": [dict(r) for r in rows]}


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that is not resolved yet, oldest first, with the shop's date.

    Reads the tickets table and desk.date_today. Use this to see the board.
    """
    with _db() as conn:
        today = _today(conn)
        rows = conn.execute(
            f"SELECT {TICKET_COLUMNS} FROM tickets WHERE status != 'resolved' ORDER BY created_at"
        ).fetchall()
    return {"date_today": today.isoformat(), "count": len(rows), "tickets": [dict(r) for r in rows]}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Read one ticket: type, requester, request text, and its links.

    Reads the tickets table and desk.date_today. The link fields point to
    other tables: sku/size -> inventory and pricing, lease_id -> leases,
    invoice_id -> invoices. A null link means the ticket has none.
    """
    with _db() as conn:
        today = _today(conn)
        row = conn.execute(f"SELECT {TICKET_COLUMNS} FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return {"found": False, "ticket_id": ticket_id, "message": f"No ticket with id {ticket_id}."}
    return {"found": True, "date_today": today.isoformat(), "ticket": dict(row)}


@mcp.tool
def get_pricing(sku: str, offered_unit_price: float | None = None, qty: int | None = None) -> dict:
    """Get a SKU's unit cost, list price, and margin; optionally test a discount.

    Reads the pricing table. Pass offered_unit_price (and qty) to see the
    discount percent, margin per unit, total margin, and whether the offer
    would sell below cost.
    """
    sku = sku.strip().upper()
    with _db() as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
    if row is None:
        return {"found": False, "sku": sku, "message": f"No pricing for SKU {sku}."}

    cost, price = row["unit_cost"], row["list_price"]
    result = {
        "found": True,
        "sku": sku,
        "unit_cost": cost,
        "list_price": price,
        "list_margin_per_unit": round(price - cost, 2),
        "list_margin_pct": round((price - cost) / price * 100, 1),
    }
    if offered_unit_price is not None:
        units = qty or 1
        result["offer"] = {
            "unit_price": offered_unit_price,
            "qty": units,
            "discount_pct": round((price - offered_unit_price) / price * 100, 1),
            "margin_per_unit": round(offered_unit_price - cost, 2),
            "margin_pct": round((offered_unit_price - cost) / offered_unit_price * 100, 1)
            if offered_unit_price > 0 else None,
            "order_total": round(offered_unit_price * units, 2),
            "total_margin": round((offered_unit_price - cost) * units, 2),
            "below_cost": offered_unit_price < cost,
        }
    return result


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Read one vendor invoice: vendor, amount, due date, status, days overdue.

    Reads the invoices and vendors tables, plus desk.date_today.
    """
    with _db() as conn:
        today = _today(conn)
        row = conn.execute(
            "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, i.status, i.description "
            "FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (invoice_id,),
        ).fetchone()
    if row is None:
        return {"found": False, "invoice_id": invoice_id, "message": f"No invoice with id {invoice_id}."}
    days_late = (today - date.fromisoformat(row["due_date"])).days
    return {
        "found": True,
        "invoice_id": row["id"],
        "vendor_id": row["vendor_id"],
        "vendor_name": row["vendor_name"],
        "amount": row["amount"],
        "due_date": row["due_date"],
        "status": row["status"],
        "description": row["description"],
        "date_today": today.isoformat(),
        "days_overdue": max(days_late, 0) if row["status"] == "open" else 0,
        "overdue": days_late > 0 and row["status"] == "open",
    }


@mcp.tool
def get_cash_balance() -> dict:
    """Show the shop's cash: each account's balance and as-of date, plus the total.

    Reads the cash_accounts table. Cash only goes out in this shop (no revenue
    is modeled), so every payment must fit inside these balances.
    """
    with _db() as conn:
        rows = conn.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name").fetchall()
    accounts = [dict(r) for r in rows]
    return {"accounts": accounts, "total": round(sum(a["balance"] for a in accounts), 2)}


def _payment_target(conn: sqlite3.Connection, kind: str, ref_id: int) -> dict:
    """Look up what a payment would pay for; amount and payee come from the database only."""
    if kind == "invoice":
        row = conn.execute(
            "SELECT i.id, i.amount, i.due_date, i.status, i.description, v.name AS payee "
            "FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (ref_id,),
        ).fetchone()
        if row is None:
            return {"ok": False, "message": f"No invoice with id {ref_id}."}
        if row["status"] != "open":
            return {"ok": False, "message": f"Invoice {ref_id} is '{row['status']}', not open; nothing to pay."}
        return {"ok": True, "payee": row["payee"], "amount": row["amount"], "due_date": row["due_date"],
                "description": row["description"]}
    if kind == "rent":
        row = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due FROM leases WHERE id = ?", (ref_id,)
        ).fetchone()
        if row is None:
            return {"ok": False, "message": f"No lease with id {ref_id}."}
        if date.fromisoformat(row["next_due"]) > _today(conn) + timedelta(days=31):
            return {"ok": False, "message": f"Rent for lease {ref_id} is already paid ahead (next due {row['next_due']})."}
        return {"ok": True, "payee": row["landlord"], "amount": row["monthly_rent"], "due_date": row["next_due"],
                "description": f"Rent for {row['space_name']}"}
    return {"ok": False, "message": f"kind must be 'invoice' or 'rent', got '{kind}' (purchase orders: use draft_purchase_order)."}


def _purchase_order_target(conn: sqlite3.Connection, vendor_id: int, sku: str | None, size: str | None,
                           qty: int | None) -> dict:
    """Price a restock order from the database; refuse if the vendor won't ship."""
    if not sku or not size or not qty or qty <= 0:
        return {"ok": False, "message": "A purchase order needs sku, size, and qty (at least 1)."}
    sku, size = sku.strip().upper(), size.strip().upper()
    vendor = conn.execute("SELECT id, name, lead_days FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
    price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
    carried = conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
    if vendor is None:
        return {"ok": False, "message": f"No vendor with id {vendor_id}."}
    if price is None or carried is None:
        return {"ok": False, "message": f"The shop does not carry {sku} in size {size}."}
    open_bills = conn.execute(
        "SELECT id FROM invoices WHERE vendor_id = ? AND status = 'open'", (vendor_id,)
    ).fetchall()
    if open_bills:
        ids = ", ".join(f"#{b['id']}" for b in open_bills)
        return {"ok": False, "message": f"{vendor['name']} will not ship while invoice {ids} is unpaid. Pay it first."}
    return {
        "ok": True,
        "payee": vendor["name"],
        "amount": round(price["unit_cost"] * qty, 2),
        "lead_days": vendor["lead_days"],
        "order": {"sku": sku, "size": size, "qty": qty, "unit_cost": price["unit_cost"]},
    }


@mcp.tool
def prepare_payment(kind: str, ref_id: int, account: str = "checking") -> dict:
    """Prepare (but do NOT make) a payment, for a human to approve.

    kind is "invoice" (ref_id = invoices.id) or "rent" (ref_id = leases.id).
    Reads invoices/vendors or leases, cash_accounts, and desk.date_today.
    Returns the amount and payee from the database, the cash before and
    after, and whether cash covers it. Nothing is paid and nothing is
    written: a human must approve it, and only then does the pay tool run.
    """
    with _db() as conn:
        today = _today(conn)
        target = _payment_target(conn, kind, ref_id)
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if not target["ok"]:
        return {"prepared": False, "kind": kind, "ref_id": ref_id, "message": target["message"]}
    if acct is None:
        return {"prepared": False, "kind": kind, "ref_id": ref_id, "message": f"No cash account '{account}'."}

    days_to_due = (date.fromisoformat(target["due_date"]) - today).days
    can_afford = acct["balance"] >= target["amount"]
    cash_after = round(acct["balance"] - target["amount"], 2)
    below_buffer = can_afford and cash_after < CASH_BUFFER
    if not can_afford:
        message = "Not enough cash: the pay tool will refuse this payment."
    elif below_buffer:
        message = f"Affordable, but checking would drop below the ${CASH_BUFFER:.0f} buffer. Flag it for a human."
    else:
        message = "Ready for human approval."
    return {
        "prepared": True,
        "status": "awaiting_human_approval",
        "kind": kind,
        "ref_id": ref_id,
        "payee": target["payee"],
        "description": target["description"],
        "amount": target["amount"],
        "due_date": target["due_date"],
        "date_today": today.isoformat(),
        "days_until_due": days_to_due,
        "overdue": days_to_due < 0,
        "account": account,
        "cash_before": acct["balance"],
        "cash_after_if_paid": cash_after,
        "can_afford": can_afford,
        "cash_buffer": CASH_BUFFER,
        "below_buffer": below_buffer,
        "message": message,
    }


@mcp.tool
def get_payments(kind: str | None = None, ref_id: int | None = None) -> dict:
    """List payments already made, newest first; use it to catch duplicate payments.

    Reads the payments table. Filter by kind ("invoice" or "rent") and/or
    ref_id (invoices.id or leases.id). An empty list means nothing has been
    paid for that item yet.
    """
    where, params = [], []
    if kind:
        where.append("kind = ?")
        params.append(kind.strip().lower())
    if ref_id is not None:
        where.append("ref_id = ?")
        params.append(ref_id)
    sql = "SELECT id, kind, ref_id, amount, account, paid_at, approved_by FROM payments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with _db() as conn:
        rows = conn.execute(sql + " ORDER BY id DESC", params).fetchall()
    payments = [dict(r) for r in rows]
    return {"count": len(payments), "total_paid": round(sum(p["amount"] for p in payments), 2), "payments": payments}


@mcp.tool
def draft_purchase_order(vendor_id: int, sku: str, size: str, qty: int) -> dict:
    """Draft (but do NOT send) a restock purchase order, for human review.

    Reads vendors, invoices (open bills block shipping), pricing (unit
    cost), and desk.date_today. Returns total cost, the vendor's lead time,
    whether it can ship now, and the earliest arrival date.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    if qty <= 0:
        return {"drafted": False, "message": "qty must be at least 1."}
    with _db() as conn:
        today = _today(conn)
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,)
        ).fetchone()
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        carried = conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        open_bills = conn.execute(
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'", (vendor_id,)
        ).fetchall()
    if vendor is None:
        return {"drafted": False, "message": f"No vendor with id {vendor_id}."}
    if price is None:
        return {"drafted": False, "message": f"No pricing for SKU {sku}."}
    if carried is None:
        return {"drafted": False, "message": f"The shop does not carry {sku} in size {size}."}

    can_ship = not open_bills
    return {
        "drafted": True,
        "status": "draft_needs_human_review",
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "vendor_specialty": vendor["specialty"],
        "sku": sku,
        "size": size,
        "qty": qty,
        "unit_cost": price["unit_cost"],
        "total_cost": round(price["unit_cost"] * qty, 2),
        "lead_days": vendor["lead_days"],
        "can_ship": can_ship,
        "blocking_invoices": [dict(b) for b in open_bills],
        "date_today": today.isoformat(),
        "earliest_arrival": (today + timedelta(days=vendor["lead_days"])).isoformat() if can_ship else None,
        "message": "Vendor can ship." if can_ship
        else "Vendor will not ship until its open invoice(s) are paid; arrival is lead_days after payment.",
    }


@mcp.tool
def update_ticket(ticket_id: int, status: str, note: str) -> dict:
    """Set a ticket's status and add a dated note (the original request text is kept).

    Writes the tickets table. status is one of: open, in_progress, resolved.
    Use resolved when the team's work is done, even if a payment or purchase
    order still waits for a human signature (the board tracks that as "signed").
    """
    status = status.strip().lower()
    if status not in TICKET_STATUSES:
        return {"updated": False, "message": f"status must be one of {TICKET_STATUSES}."}
    with _db(write=True) as conn:
        today = _today(conn)
        row = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"updated": False, "message": f"No ticket with id {ticket_id}."}
        notes = (row["notes"] or "") + f"\n[{today.isoformat()} {status}] {note.strip()}"
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes.strip(), ticket_id))
    return {"updated": True, "ticket_id": ticket_id, "old_status": row["status"], "status": status, "notes": notes.strip()}


def _add_month(d: date) -> date:
    month = d.month % 12 + 1
    year = d.year + (d.month == 12)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


@mcp.tool
def pay(
    kind: str,
    ref_id: int,
    approved_by: str,
    account: str = "checking",
    sku: str | None = None,
    size: str | None = None,
    qty: int | None = None,
) -> dict:
    """Make a payment. HUMAN APPROVAL REQUIRED: approved_by is the human who approved it.

    kind is "invoice" (ref_id = invoices.id), "rent" (ref_id = leases.id), or
    "purchase_order" (ref_id = vendors.id, plus sku, size, qty: pays the vendor
    up front for a restock at unit cost). Writes payments, cash_accounts, and
    invoices (status -> paid) or leases (next_due moves one month ahead), all in
    one transaction. Refuses if there is not enough cash (balances never go
    negative) and refuses a purchase order while the vendor has an unpaid invoice.
    """
    approver = (approved_by or "").strip()
    if not approver or approver.lower() in AGENT_NAMES:
        return {"paid": False, "message": "A human approver's name is required; agents cannot approve payments."}
    if kind not in PAY_KINDS:
        return {"paid": False, "message": f"kind must be one of {PAY_KINDS}, got '{kind}'."}
    with _db(write=True) as conn:
        today = _today(conn)
        if kind == "purchase_order":
            target = _purchase_order_target(conn, ref_id, sku, size, qty)
        else:
            target = _payment_target(conn, kind, ref_id)
        if not target["ok"]:
            return {"paid": False, "kind": kind, "ref_id": ref_id, "message": target["message"]}
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            return {"paid": False, "message": f"No cash account '{account}'."}
        amount = target["amount"]
        if acct["balance"] < amount:
            return {
                "paid": False,
                "kind": kind,
                "ref_id": ref_id,
                "amount": amount,
                "cash_balance": acct["balance"],
                "message": f"Refused: {account} has ${acct['balance']:.2f}, payment is ${amount:.2f}. No negative balances.",
            }
        new_balance = round(acct["balance"] - amount, 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_balance, today.isoformat(), account)
        )
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref_id, amount, account, today.isoformat(), approver),
        )
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            follow_up = {"invoice_status": "paid"}
        elif kind == "purchase_order":
            # Stock isn't added yet: it arrives lead_days after the order is paid.
            arrival = (today + timedelta(days=target["lead_days"])).isoformat()
            follow_up = {"purchase_order": {**target["order"], "expected_arrival": arrival}}
        else:
            next_due = _add_month(date.fromisoformat(target["due_date"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, ref_id))
            follow_up = {"lease_next_due": next_due}
    return {
        "paid": True,
        "payment_id": cur.lastrowid,
        "kind": kind,
        "ref_id": ref_id,
        "payee": target["payee"],
        "amount": amount,
        "account": account,
        "paid_at": today.isoformat(),
        "approved_by": approver,
        "cash_after": new_balance,
        **follow_up,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Customs MCP server")
    parser.add_argument("--http", action="store_true", help="serve over HTTP instead of stdio")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=args.port)
    else:
        mcp.run()
