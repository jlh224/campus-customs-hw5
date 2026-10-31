"""Reset the working database: copy data/campus_customs.db over data/campus_customs_new.db.

The original is only ever read. Run this before a full run to resolve the tickets.
    python reset_db.py
"""

from __future__ import annotations

import shutil

from config import ROOT

ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"


def reset_database() -> str:
    if not ORIGINAL_DB.exists():
        raise FileNotFoundError(f"Original database missing: {ORIGINAL_DB}")
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    return f"Reset {WORKING_DB.name} from {ORIGINAL_DB.name}."


if __name__ == "__main__":
    print(reset_database())
