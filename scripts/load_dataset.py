#!/usr/bin/env python3
"""Load a generated dataset (.jsonl.gz) into MongoDB with proper BSON ISODate types.

Usage:
  python3 scripts/load_dataset.py --uri mongodb://localhost:27017 --db ehr --dataset data/D100K
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_iso_utc(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_collection(col: Any, path: Path, parse_dates: bool, batch_size: int) -> tuple[int, float]:
    t0 = time.time()
    batch: list[dict[str, Any]] = []
    total = 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            if parse_dates:
                if doc.get("START"):
                    doc["START"] = parse_iso_utc(doc["START"])
                if doc.get("STOP"):
                    doc["STOP"] = parse_iso_utc(doc["STOP"])
            batch.append(doc)
            if len(batch) >= batch_size:
                col.insert_many(batch, ordered=False)
                total += len(batch)
                batch.clear()
        if batch:
            col.insert_many(batch, ordered=False)
            total += len(batch)
    return total, time.time() - t0


def main() -> None:
    parser = argparse.ArgumentParser(description="Load .jsonl.gz EHR dataset into MongoDB.")
    parser.add_argument("--uri", required=True, help="MongoDB connection URI")
    parser.add_argument("--db", default="ehr", help="Target database name")
    parser.add_argument("--dataset", type=Path, required=True, help="Dataset directory (e.g. data/D100K)")
    parser.add_argument("--batch-size", type=int, default=1000, help="insert_many batch size")
    parser.add_argument("--drop", action="store_true", help="Drop collections before loading")
    args = parser.parse_args()

    from pymongo import MongoClient  # Lazy import so script can be inspected without pymongo

    client = MongoClient(args.uri, w="majority")
    db = client[args.db]

    if args.drop:
        db.patients.drop()
        db.encounters.drop()

    p_count, p_sec = load_collection(db.patients, args.dataset / "patients.jsonl.gz", False, args.batch_size)
    print(f"Loaded patients: {p_count:,} docs in {p_sec:.1f}s ({p_count / max(p_sec, 1e-6):,.0f} docs/s)")

    e_count, e_sec = load_collection(db.encounters, args.dataset / "encounters.jsonl.gz", True, args.batch_size)
    print(f"Loaded encounters: {e_count:,} docs in {e_sec:.1f}s ({e_count / max(e_sec, 1e-6):,.0f} docs/s)")


if __name__ == "__main__":
    main()
