#!/usr/bin/env python3
"""
Admin helper: list demo run requests (no-login workflow).

Usage:
  python scripts/admin_list_demo_requests.py
  python scripts/admin_list_demo_requests.py --status pending --limit 25
  python scripts/admin_list_demo_requests.py --status completed
  python scripts/admin_list_demo_requests.py --json
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Optional


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.db.operations import list_demo_run_requests  # noqa: E402


def _fmt_dt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return str(v)


def _fmt_num(v: Any, decimals: int = 0) -> str:
    if v is None:
        return "-"
    try:
        if decimals == 0:
            return f"{int(float(v))}"
        return f"{float(v):.{decimals}f}"
    except Exception:
        return str(v)


def _short(v: Any, width: int) -> str:
    s = "-" if v is None else str(v)
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: width - 1] + "…"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="List demo_run_requests (admin helper).")
    parser.add_argument("--status", type=str, default="pending", help="Filter by status (default: pending). Use '' for all.")
    parser.add_argument("--limit", type=int, default=50, help="Max rows to show (default 50)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of a table")
    args = parser.parse_args()

    status: Optional[str] = args.status if args.status != "" else None
    rows = list_demo_run_requests(status=status, limit=args.limit)

    if args.json:
        print(json.dumps(rows, default=str, indent=2))
        return 0

    if not rows:
        if status:
            print(f"No demo requests found (status={status}).")
        else:
            print("No demo requests found.")
        return 0

    # Column layout
    cols = [
        ("request_id", 10),
        ("status", 10),
        ("run_id", 6),
        ("variant", 9),
        ("dur_s", 6),
        ("speed", 6),
        ("aoa", 5),
        ("yaw", 5),
        ("email", 26),
        ("created_at", 19),
        ("notes", 40),
    ]

    def cell(r: dict, key: str, width: int) -> str:
        if key == "variant":
            return _short(r.get("requested_variant"), width)
        if key == "dur_s":
            return _short(_fmt_num(r.get("requested_duration_sec"), decimals=1), width)
        if key == "speed":
            return _short(_fmt_num(r.get("requested_speed_ms"), decimals=1), width)
        if key == "aoa":
            return _short(_fmt_num(r.get("requested_aoa_deg"), decimals=1), width)
        if key == "yaw":
            return _short(_fmt_num(r.get("requested_yaw_deg"), decimals=1), width)
        if key == "email":
            return _short(r.get("requester_email"), width)
        if key == "created_at":
            return _short(_fmt_dt(r.get("created_at")), width)
        if key == "notes":
            return _short(r.get("requested_notes"), width)
        return _short(r.get(key), width)

    header = " ".join([name.ljust(width) for name, width in cols])
    sep = " ".join(["-" * width for _, width in cols])
    print(header)
    print(sep)

    for r in rows:
        line = " ".join([cell(r, name, width).ljust(width) for name, width in cols])
        print(line)

    print("")
    print("Fulfill a request:")
    print("  python scripts/admin_fulfill_demo_request.py <REQUEST_ID> --start-consumer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


