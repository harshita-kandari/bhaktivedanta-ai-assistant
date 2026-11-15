#!/usr/bin/env python
"""Write the hospital data to an .xlsx file.

Usage:
    .venv/bin/python scripts/export_call_data.py
    .venv/bin/python scripts/export_call_data.py --out ~/Desktop/calls.xlsx
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.export import build_workbook, database_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(BASE_DIR / "data" / f"hospital_call_data_{datetime.now():%Y%m%d_%H%M}.xlsx"),
        help="Destination .xlsx path",
    )
    args = parser.parse_args()

    destination = Path(args.out).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)

    workbook = build_workbook()
    workbook.save(destination)

    print(f"database: {database_path()}")
    print(f"workbook: {destination}")
    print(f"sheets:   {', '.join(workbook.sheetnames)}")
    print(f"size:     {destination.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
