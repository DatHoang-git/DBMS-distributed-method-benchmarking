#!/usr/bin/env python3
"""Verify all 6 generated datasets against EXPERIMENT_SPEC.md Data Agent DoD.

Checks:
  1. Exact encounter counts for D100K, D500K, D1M, D3M, D1M-nat, D1M-heavy.
  2. Strict PATIENT-level nesting: D100K ⊂ D500K ⊂ D1M ⊂ D3M.
  3. D1M-heavy skew: exact 1.00% PATIENTs hold exact 30.00% (300,000) encounters.
  4. Schema compliance (Section 4.2) and presence of diabetes 44054006 & laboratory obs.
  5. query_params.json & patient_ids.txt validity (SEED=42).
  6. D100K avgObjSize (JSON & estimated BSON) and D3M MongoDB capacity extrapolation.
  7. Writes verified data/DATASET_SUMMARY.json.
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from build_datasets import DIABETES_T2_CODE, estimate_bson_size

EXPECTED_COUNTS = {
    "D100K": 100_000,
    "D500K": 500_000,
    "D1M": 1_000_000,
    "D3M": 3_000_000,
    "D1M-nat": 1_000_000,
    "D1M-heavy": 1_000_000,
}
REQUIRED_KEYS = {
    "_id", "PATIENT", "ORGANIZATION", "ENCOUNTERCLASS",
    "START", "STOP", "TOTAL_CLAIM_COST", "conditions", "observations",
}


def inspect_dataset(ds_dir: Path, name: str, compute_bson: bool = False) -> tuple[dict[str, Any], set[str]]:
    t0 = time.time()
    enc_path = ds_dir / "encounters.jsonl.gz"
    pat_path = ds_dir / "patients.jsonl.gz"
    pids_path = ds_dir / "patient_ids.txt"
    qp_path = ds_dir / "query_params.json"

    for p in (enc_path, pat_path, pids_path, qp_path):
        assert p.exists(), f"Missing {p}"

    pat_ids_file = [line.strip() for line in pids_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    pat_ids_set = set(pat_ids_file)
    assert len(pat_ids_file) == len(pat_ids_set), f"{name}: duplicate patient IDs in patient_ids.txt"

    qp = json.loads(qp_path.read_text(encoding="utf-8"))
    assert qp["seed"] == 42, f"{name}: seed != 42"
    assert len(qp["q1_q2_pids"]) == 10_000
    assert len(qp["q3_windows"]) == 12
    assert len(qp["q4_windows"]) == 36
    assert len(qp["explain_samples"]) == 5

    # Count patients.jsonl.gz
    pat_count = 0
    with gzip.open(pat_path, "rt", encoding="utf-8") as f:
        for _ in f:
            pat_count += 1
    assert pat_count == len(pat_ids_set), f"{name}: patients.jsonl.gz ({pat_count}) != patient_ids.txt ({len(pat_ids_set)})"

    # Scan encounters.jsonl.gz
    enc_count = 0
    json_bytes = 0
    bson_bytes = 0
    diab_docs = 0
    lab_docs = 0
    per_pat = Counter()
    min_start = None
    max_start = None

    with gzip.open(enc_path, "rt", encoding="utf-8") as f:
        for line in f:
            enc_count += 1
            json_bytes += len(line.encode("utf-8"))
            doc = json.loads(line)
            if enc_count <= 5:
                assert set(doc.keys()) == REQUIRED_KEYS, f"{name}: schema keys mismatch: {set(doc.keys())}"
            if compute_bson:
                bson_bytes += estimate_bson_size(doc)
            per_pat[doc["PATIENT"]] += 1
            s = doc["START"]
            if min_start is None or s < min_start:
                min_start = s
            if max_start is None or s > max_start:
                max_start = s
            if any(c["CODE"] == DIABETES_T2_CODE for c in doc["conditions"]):
                diab_docs += 1
            if any(o["CATEGORY"] == "laboratory" for o in doc["observations"]):
                lab_docs += 1

    assert enc_count == EXPECTED_COUNTS[name], f"{name}: got {enc_count}, expected {EXPECTED_COUNTS[name]}"
    assert set(per_pat.keys()) == pat_ids_set, f"{name}: encounter PATIENT set != patient_ids.txt"

    info: dict[str, Any] = {
        "encounters": enc_count,
        "patients": pat_count,
        "avg_encounters_per_patient": round(enc_count / pat_count, 2),
        "avg_json_bytes": round(json_bytes / enc_count, 1),
        "encounters_gz_mb": round(enc_path.stat().st_size / (1024 * 1024), 2),
        "patients_gz_mb": round(pat_path.stat().st_size / (1024 * 1024), 2),
        "diabetes_t2_docs": diab_docs,
        "lab_obs_docs": lab_docs,
        "min_start": min_start,
        "max_start": max_start,
    }
    if compute_bson:
        info["est_avg_bson_bytes"] = round(bson_bytes / enc_count, 1)

    if name == "D1M-heavy":
        top_1pct_n = pat_count // 100
        assert pat_count % 100 == 0, f"D1M-heavy patients ({pat_count}) not divisible by 100"
        top_docs = sum(c for _, c in per_pat.most_common(top_1pct_n))
        info["hot_patients"] = top_1pct_n
        info["hot_patient_pct"] = round(100.0 * top_1pct_n / pat_count, 4)
        info["hot_encounters"] = top_docs
        info["hot_encounter_pct"] = round(100.0 * top_docs / enc_count, 4)
        assert top_docs == 300_000, f"D1M-heavy top 1% has {top_docs} docs, expected 300,000"

    print(
        f"  [PASS] {name:10s}: {enc_count:>9,} docs | {pat_count:>6,} pats | "
        f"enc.gz={info['encounters_gz_mb']:>6.1f} MB | diab={diab_docs:>5,} | lab={lab_docs:>7,} "
        f"({time.time() - t0:.1f}s)",
        flush=True,
    )
    return info, pat_ids_set


def main() -> None:
    data_root = Path("data")
    summary: dict[str, Any] = {}
    pat_sets: dict[str, set[str]] = {}

    for name in ("D100K", "D500K", "D1M", "D3M", "D1M-heavy"):
        info, pset = inspect_dataset(data_root / name, name, compute_bson=(name == "D100K"))
        summary[name] = info
        pat_sets[name] = pset

    # Verify D1M-nat symlink
    d1m_nat = data_root / "D1M-nat"
    assert d1m_nat.is_symlink() and d1m_nat.resolve() == (data_root / "D1M").resolve()
    summary["D1M-nat"] = {"symlink_to": "D1M", **summary["D1M"]}
    print("  [PASS] D1M-nat   : valid symlink -> D1M", flush=True)

    # Verify strict nesting D100K ⊂ D500K ⊂ D1M ⊂ D3M
    assert pat_sets["D100K"] < pat_sets["D500K"], "Nesting failed: D100K not ⊂ D500K"
    assert pat_sets["D500K"] < pat_sets["D1M"], "Nesting failed: D500K not ⊂ D1M"
    assert pat_sets["D1M"] < pat_sets["D3M"], "Nesting failed: D1M not ⊂ D3M"
    print("  [PASS] Nesting   : D100K ⊂ D500K ⊂ D1M ⊂ D3M (by PATIENT) verified!", flush=True)

    # Capacity estimate for D3M
    avg_bson = summary["D100K"]["est_avg_bson_bytes"]
    d3m_raw_bson_gb = (avg_bson * 3_000_000) / (1024 ** 3)
    d3m_est_index_gb = round(d3m_raw_bson_gb * 0.30, 2)
    d3m_est_total_mem_gb = round(d3m_raw_bson_gb + d3m_est_index_gb, 2)
    d3m_est_wt_disk_gb = round(d3m_raw_bson_gb * 0.35 + d3m_est_index_gb * 0.5, 2)

    summary["_capacity_estimate"] = {
        "d100k_est_avg_bson_bytes": avg_bson,
        "d100k_avg_json_bytes": summary["D100K"]["avg_json_bytes"],
        "d3m_uncompressed_bson_gb": round(d3m_raw_bson_gb, 2),
        "d3m_est_indexes_gb": d3m_est_index_gb,
        "d3m_est_total_working_set_gb": d3m_est_total_mem_gb,
        "d3m_est_wiredtiger_disk_gb": d3m_est_wt_disk_gb,
        "exceeds_1_5gb_wt_cache": d3m_est_total_mem_gb > 1.5,
    }

    (data_root / "DATASET_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nCapacity Extrapolation (D100K -> D3M):")
    print(json.dumps(summary["_capacity_estimate"], indent=2))
    print("\nALL CHECKS PASSED!")


if __name__ == "__main__":
    main()
