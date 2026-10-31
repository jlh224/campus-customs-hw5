"""Run the agent team on tickets from the command line (no web server needed).

From the backend/ folder:
    python run_ticket.py 101            # one ticket
    python run_ticket.py 101 102 103    # several, one after another
    python run_ticket.py 101 --reset    # restore the original database first

Every step is appended to output/audit_trail.json. No payment is ever made
here: agents can only prepare payments for a human to approve.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from agents import run_ticket
from reset_db import reset_database


async def _print_event(type_: str, data: dict) -> None:
    if type_ == "handoff":
        print(f"  -> {data['from']} delegates to {data['to']}: {data['task'][:120]}")
    elif type_ == "tool_call":
        print(f"     [{data['agent']}] {data['tool']}({json.dumps(data['args'])})")
    elif type_ == "customer_draft":
        print(f"     [customer_service] draft saved for {data['to']}: {data['subject']}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tickets", nargs="+", type=int)
    parser.add_argument("--reset", action="store_true", help="copy the original DB over the working copy first")
    args = parser.parse_args()

    if args.reset:
        print(reset_database())
    for ticket_id in args.tickets:
        print(f"\n=== Ticket {ticket_id} ===")
        result = await run_ticket(ticket_id, emit=_print_event)
        print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
