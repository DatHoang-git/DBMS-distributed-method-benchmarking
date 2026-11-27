#!/usr/bin/env python3
"""Load a generated dataset (.jsonl.gz) into MongoDB with proper BSON ISODate types.

v2: hỗ trợ nạp tăng dần theo bước (data/load_v2/S1..S4, HEAVY) đã sắp xếp theo START,
ghi metadata thời gian nạp ra JSON và cho phép chọn writeConcern.

Usage:
  # v1 (nạp nguyên một dataset, thứ tự theo bệnh nhân như file gốc)
  python3 scripts/load_dataset.py --uri mongodb://localhost:27017 --db ehr --dataset data/D100K --drop

  # v2 (nạp tăng dần, thứ tự thời gian): S1 -> đo D100K, S2 -> đo D500K, ...
  python3 scripts/load_dataset.py --uri mongodb://mongos:27017 --dataset data/load_v2/S1 --drop \
      --meta-out results/load/SH-hash_S1.json --env SH-hash
  python3 scripts/load_dataset.py --uri mongodb://mongos:27017 --dataset data/load_v2/S2 \
      --meta-out results/load/SH-hash_S2.json --env SH-hash
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


def load_collection(col: Any, path: Path, parse_dates: bool, batch_size: int,
                    progress_every: int = 0) -> tuple[int, float, list[dict[str, float]]]:
    t0 = time.time()
    batch: list[dict[str, Any]] = []
    total = 0
    timeline: list[dict[str, float]] = []
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
                if progress_every and total % progress_every == 0:
                    timeline.append({"elapsed_s": round(time.time() - t0, 2), "docs": total})
        if batch:
            col.insert_many(batch, ordered=False)
            total += len(batch)
    timeline.append({"elapsed_s": round(time.time() - t0, 2), "docs": total})
    return total, time.time() - t0, timeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Load .jsonl.gz EHR dataset into MongoDB.")
    parser.add_argument("--uri", required=True, help="MongoDB connection URI")
    parser.add_argument("--db", default="ehr", help="Target database name")
    parser.add_argument("--dataset", type=Path, required=True,
                        help="Dataset or load step directory (data/D100K, data/load_v2/S2, ...)")
    parser.add_argument("--batch-size", type=int, default=1000, help="insert_many batch size")
    parser.add_argument("--w", default="majority", help='writeConcern w (default "majority")')
    parser.add_argument("--drop", action="store_true", help="Drop collections before loading")
    parser.add_argument("--skip-patients", action="store_true", help="Do not load patients.jsonl.gz")
    parser.add_argument("--env", default="", help="Env label stored in metadata (SA, B1, SH-hash, ...)")
    parser.add_argument("--meta-out", type=Path, default=None, help="Write load metadata JSON here")
    parser.add_argument("--progress-every", type=int, default=50_000,
                        help="Record (elapsed, docs) every N docs for the load timeline")
    args = parser.parse_args()

    from pymongo import MongoClient  # Lazy import so script can be inspected without pymongo

    w: Any = int(args.w) if args.w.isdigit() else args.w
    client = MongoClient(args.uri, w=w)
    db = client[args.db]

    if args.drop:
        db.patients.drop()
        db.encounters.drop()

    started = datetime.now(timezone.utc).isoformat()
    meta: dict[str, Any] = {"env": args.env, "dataset_dir": str(args.dataset), "batch_size": args.batch_size,
                            "write_concern_w": args.w, "start_utc": started,
                            "server_version": client.server_info().get("version")}

    if not args.skip_patients and (args.dataset / "patients.jsonl.gz").exists():
        p_count, p_sec, _ = load_collection(db.patients, args.dataset / "patients.jsonl.gz", False, args.batch_size)
        print(f"Loaded patients: {p_count:,} docs in {p_sec:.1f}s ({p_count / max(p_sec, 1e-6):,.0f} docs/s)")
        meta["patients"] = {"docs": p_count, "seconds": round(p_sec, 2)}

    e_count, e_sec, timeline = load_collection(db.encounters, args.dataset / "encounters.jsonl.gz", True,
                                               args.batch_size, args.progress_every)
    print(f"Loaded encounters: {e_count:,} docs in {e_sec:.1f}s ({e_count / max(e_sec, 1e-6):,.0f} docs/s)")
    meta["encounters"] = {"docs": e_count, "seconds": round(e_sec, 2),
                          "docs_per_s": round(e_count / max(e_sec, 1e-6), 1), "timeline": timeline}
    meta["end_utc"] = datetime.now(timezone.utc).isoformat()

    if args.meta_out:
        args.meta_out.parent.mkdir(parents=True, exist_ok=True)
        args.meta_out.write_text(json.dumps(meta, indent=2))
        print(f"Wrote {args.meta_out}")


if __name__ == "__main__":
    main()
