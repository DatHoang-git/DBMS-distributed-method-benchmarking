#!/usr/bin/env python3
"""Build all 6 Synthea EHR MongoDB benchmark datasets per EXPERIMENT_SPEC.md.

Reads real Synthea CSV output (patients.csv, encounters.csv, conditions.csv,
observations.csv) from a seed cohort, converts encounters to the exact Section 4.2
JSON schema, and statistically expands them into:
  - D100K (100,000 encounters)
  - D500K (500,000 encounters, D100K ⊂ D500K by PATIENT)
  - D1M   (1,000,000 encounters, D500K ⊂ D1M by PATIENT)
  - D3M   (3,000,000 encounters, D1M ⊂ D3M by PATIENT)
  - D1M-nat (symlink to D1M)
  - D1M-heavy (1,000,000 encounters; exact 1% PATIENTs hold exact 30% = 300,000 docs)

Also generates patient_ids.txt, query_params.json (SEED=42), and DATASET_SUMMARY.json.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import random
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SEED = 42
MILESTONES = [
    ("D100K", 100_000),
    ("D500K", 500_000),
    ("D1M", 1_000_000),
    ("D3M", 3_000_000),
]
DIABETES_T2_CODE = "44054006"


def parse_float_or_str(val: str) -> float | str:
    s = val.strip()
    if not s:
        return ""
    try:
        f = float(s)
        if math.isfinite(f):
            return round(f, 4)
        return s
    except ValueError:
        return s


def parse_float_default(val: str, default: float = 0.0) -> float:
    s = val.strip()
    if not s:
        return default
    try:
        f = float(s)
        return round(f, 2) if math.isfinite(f) else default
    except ValueError:
        return default


def parse_iso_utc(ts: str) -> datetime:
    s = ts.strip()
    if not s:
        raise ValueError("Empty timestamp")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def format_iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_deterministic_uuid(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def estimate_bson_size(doc: dict[str, Any]) -> int:
    """Accurate BSON byte-size estimator for encounter docs (without needing pymongo)."""
    # BSON document: 4 bytes total length + elements + 1 byte null terminator
    size = 5
    for k, v in doc.items():
        # 1 byte type + key UTF-8 bytes + 1 byte null
        size += 1 + len(k.encode("utf-8")) + 1
        if k in ("START", "STOP"):
            size += 8  # BSON UTC datetime (int64)
        elif isinstance(v, str):
            size += 4 + len(v.encode("utf-8")) + 1
        elif isinstance(v, float):
            size += 8
        elif isinstance(v, int):
            size += 4
        elif isinstance(v, list):
            arr_size = 5
            for idx, item in enumerate(v):
                arr_size += 1 + len(str(idx)) + 1
                if isinstance(item, dict):
                    arr_size += estimate_bson_size(item)
                elif isinstance(item, str):
                    arr_size += 4 + len(item.encode("utf-8")) + 1
                else:
                    arr_size += 8
            size += arr_size
        elif v is None:
            pass
        else:
            size += 8
    return size


def load_synthea_seed(csv_dir: Path) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]], datetime, datetime]:
    """Load real Synthea CSVs into compact per-patient structures."""
    t0 = time.time()
    print(f"[1/5] Loading Synthea seed CSVs from {csv_dir} ...", flush=True)

    # 1. Conditions grouped by ENCOUNTER
    cond_by_enc: dict[str, list[dict[str, str]]] = defaultdict(list)
    cond_path = csv_dir / "conditions.csv"
    with cond_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if None in row or None in row.values():
                continue
            enc_id = row.get("ENCOUNTER", "").strip()
            code = row.get("CODE", "").strip()
            if not enc_id or not code:
                continue
            cond_by_enc[enc_id].append({
                "CODE": code,
                "DESCRIPTION": row.get("DESCRIPTION", "").strip(),
            })
    print(f"  Loaded conditions for {len(cond_by_enc):,} encounters ({time.time() - t0:.1f}s)", flush=True)

    # 2. Observations grouped by ENCOUNTER
    obs_by_enc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    obs_path = csv_dir / "observations.csv"
    with obs_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if None in row or None in row.values():
                continue
            enc_id = row.get("ENCOUNTER", "").strip()
            code = row.get("CODE", "").strip()
            if not enc_id or not code:
                continue
            obs_by_enc[enc_id].append({
                "CATEGORY": row.get("CATEGORY", "").strip(),
                "CODE": code,
                "VALUE": parse_float_or_str(row.get("VALUE", "")),
                "UNITS": row.get("UNITS", "").strip(),
            })
    print(f"  Loaded observations for {len(obs_by_enc):,} encounters ({time.time() - t0:.1f}s)", flush=True)

    # 3. Encounters grouped by PATIENT
    enc_by_pat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    enc_path = csv_dir / "encounters.csv"
    min_dt: datetime | None = None
    max_dt: datetime | None = None
    total_seed_encs = 0
    diabetes_encs = 0
    lab_encs = 0

    with enc_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if None in row or None in row.values():
                continue
            enc_id = row.get("Id", "").strip()
            pat_id = row.get("PATIENT", "").strip()
            start_raw = row.get("START", "").strip()
            if not enc_id or not pat_id or not start_raw:
                continue
            try:
                start_dt = parse_iso_utc(start_raw)
                stop_raw = row.get("STOP", "").strip()
                stop_dt = parse_iso_utc(stop_raw) if stop_raw else start_dt
            except ValueError:
                continue
            if stop_dt < start_dt:
                stop_dt = start_dt

            if min_dt is None or start_dt < min_dt:
                min_dt = start_dt
            if max_dt is None or start_dt > max_dt:
                max_dt = start_dt

            conds = cond_by_enc.get(enc_id, [])
            obs = obs_by_enc.get(enc_id, [])
            if any(c["CODE"] == DIABETES_T2_CODE for c in conds):
                diabetes_encs += 1
            if any(o["CATEGORY"] == "laboratory" for o in obs):
                lab_encs += 1

            enc_by_pat[pat_id].append({
                "_id": enc_id,
                "PATIENT": pat_id,
                "ORGANIZATION": row.get("ORGANIZATION", "").strip(),
                "ENCOUNTERCLASS": row.get("ENCOUNTERCLASS", "").strip(),
                "start_dt": start_dt,
                "dur_sec": int((stop_dt - start_dt).total_seconds()),
                "TOTAL_CLAIM_COST": parse_float_default(row.get("TOTAL_CLAIM_COST", ""), 0.0),
                "conditions": conds,
                "observations": obs,
            })
            total_seed_encs += 1

    # Free lookup dicts early
    cond_by_enc.clear()
    obs_by_enc.clear()

    # 4. Patients
    seed_patients: list[dict[str, Any]] = []
    seed_enc_lists: list[list[dict[str, Any]]] = []
    pat_path = csv_dir / "patients.csv"
    with pat_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if None in row or None in row.values():
                continue
            pat_id = row.get("Id", "").strip()
            encs = enc_by_pat.get(pat_id)
            if not pat_id or not encs:
                continue
            seed_patients.append({
                "_id": pat_id,
                "BIRTHDATE": row.get("BIRTHDATE", "").strip(),
                "DEATHDATE": row.get("DEATHDATE", "").strip() or None,
                "GENDER": row.get("GENDER", "").strip(),
                "RACE": row.get("RACE", "").strip(),
                "ETHNICITY": row.get("ETHNICITY", "").strip(),
                "CITY": row.get("CITY", "").strip(),
                "STATE": row.get("STATE", "").strip(),
                "ZIP": row.get("ZIP", "").strip(),
                "HEALTHCARE_EXPENSES": parse_float_default(row.get("HEALTHCARE_EXPENSES", ""), 0.0),
                "HEALTHCARE_COVERAGE": parse_float_default(row.get("HEALTHCARE_COVERAGE", ""), 0.0),
            })
            seed_enc_lists.append(encs)

    # Drop last 25 patients to guarantee no partially-flushed concurrent patient records
    if len(seed_patients) > 100:
        seed_patients = seed_patients[:-25]
        seed_enc_lists = seed_enc_lists[:-25]

    assert min_dt is not None and max_dt is not None
    print(
        f"  Loaded {len(seed_patients):,} seed patients, {total_seed_encs:,} encounters "
        f"(avg {total_seed_encs / len(seed_patients):.1f}/patient; "
        f"diabetes 44054006: {diabetes_encs:,}; lab obs: {lab_encs:,}; "
        f"dates: {format_iso_utc(min_dt)} .. {format_iso_utc(max_dt)})",
        flush=True,
    )
    return seed_patients, seed_enc_lists, min_dt, max_dt


def build_exact_patient_plan(
    seed_enc_counts: list[int],
    milestones: list[tuple[str, int]],
    rng: random.Random,
) -> tuple[list[tuple[int, int]], dict[str, int]]:
    """Plan a sequence of (seed_idx, clone_epoch) hitting every milestone count EXACTLY."""
    n_seed = len(seed_enc_counts)
    by_count: dict[int, list[int]] = defaultdict(list)
    for idx, c in enumerate(seed_enc_counts):
        by_count[c].append(idx)
    available_counts_desc = sorted(by_count.keys(), reverse=True)

    plan: list[tuple[int, int]] = []
    milestone_pat_idx: dict[str, int] = {}
    total_docs = 0
    epoch = 0
    order: list[int] = []
    pos = 0

    def next_candidate() -> tuple[int, int]:
        nonlocal epoch, order, pos
        if pos >= len(order):
            order = list(range(n_seed))
            rng.shuffle(order)
            pos = 0
            epoch += 1
        idx = order[pos]
        pos += 1
        return idx, epoch

    for name, target in milestones:
        while total_docs < target:
            rem = target - total_docs
            # If we're far from target, draw normally from shuffled seed epochs
            if rem > max(available_counts_desc):
                s_idx, ep = next_candidate()
                plan.append((s_idx, ep))
                total_docs += seed_enc_counts[s_idx]
            else:
                # Exact fit if available
                if rem in by_count:
                    s_idx = rng.choice(by_count[rem])
                    plan.append((s_idx, epoch + 1000))
                    total_docs += rem
                else:
                    # Pick largest available count <= rem
                    picked = False
                    for c in available_counts_desc:
                        if c <= rem:
                            s_idx = rng.choice(by_count[c])
                            plan.append((s_idx, epoch + 1000))
                            total_docs += c
                            picked = True
                            break
                    if not picked:
                        raise RuntimeError(f"Cannot hit exact target {target} (rem={rem})")
        assert total_docs == target, f"Mismatch for {name}: {total_docs} != {target}"
        milestone_pat_idx[name] = len(plan)

    return plan, milestone_pat_idx


def materialize_patient_and_encounters(
    seed_pat: dict[str, Any],
    seed_encs: list[dict[str, Any]],
    clone_epoch: int,
    rng: random.Random,
    max_dt: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Create a patient doc and its encounter docs (original for epoch 1, perturbed clone for epoch > 1)."""
    is_orig = (clone_epoch == 1)
    if is_orig:
        pat_doc = dict(seed_pat)
        pat_id = pat_doc["_id"]
        enc_docs = []
        for e in seed_encs:
            start_dt = e["start_dt"]
            stop_dt = start_dt + timedelta(seconds=e["dur_sec"])
            enc_docs.append({
                "_id": e["_id"],
                "PATIENT": pat_id,
                "ORGANIZATION": e["ORGANIZATION"],
                "ENCOUNTERCLASS": e["ENCOUNTERCLASS"],
                "START": format_iso_utc(start_dt),
                "STOP": format_iso_utc(stop_dt),
                "TOTAL_CLAIM_COST": e["TOTAL_CLAIM_COST"],
                "conditions": e["conditions"],
                "observations": e["observations"],
            })
        return pat_doc, enc_docs

    # Perturbed clone: fresh UUIDs, slight date jitter (-14..+14 days, clamped <= max_dt), +/-5% numeric jitter
    pat_id = make_deterministic_uuid(rng)
    pat_doc = dict(seed_pat)
    pat_doc["_id"] = pat_id
    shift_sec = rng.randint(-14 * 86400, 14 * 86400)
    cost_factor = rng.uniform(0.95, 1.05)

    enc_docs = []
    for e in seed_encs:
        start_dt = e["start_dt"] + timedelta(seconds=shift_sec)
        if start_dt > max_dt:
            start_dt = max_dt - timedelta(seconds=rng.randint(0, 86400 * 7))
        stop_dt = start_dt + timedelta(seconds=e["dur_sec"])

        new_obs = []
        for o in e["observations"]:
            val = o["VALUE"]
            if isinstance(val, float):
                val = round(val * rng.uniform(0.97, 1.03), 4)
            new_obs.append({
                "CATEGORY": o["CATEGORY"],
                "CODE": o["CODE"],
                "VALUE": val,
                "UNITS": o["UNITS"],
            })

        enc_docs.append({
            "_id": make_deterministic_uuid(rng),
            "PATIENT": pat_id,
            "ORGANIZATION": e["ORGANIZATION"],
            "ENCOUNTERCLASS": e["ENCOUNTERCLASS"],
            "START": format_iso_utc(start_dt),
            "STOP": format_iso_utc(stop_dt),
            "TOTAL_CLAIM_COST": round(e["TOTAL_CLAIM_COST"] * cost_factor, 2),
            "conditions": e["conditions"],
            "observations": new_obs,
        })
    return pat_doc, enc_docs


def generate_query_params(
    dataset_name: str,
    patient_ids: list[str],
    min_start_iso: str,
    max_start_iso: str,
    seed: int = SEED,
) -> dict[str, Any]:
    """Generate deterministic query_params.json for Q1-Q4 and R3-1 explain samples."""
    rng = random.Random(seed)
    max_dt = parse_iso_utc(max_start_iso)
    # Use end of the last complete month before max_dt as anchor for clean quarterly/monthly windows
    anchor = datetime(max_dt.year, max_dt.month, 1, tzinfo=timezone.utc)
    recent_3y_start = datetime(anchor.year - 3, anchor.month, 1, tzinfo=timezone.utc)
    d12m_ago = datetime(anchor.year - 1, anchor.month, 1, tzinfo=timezone.utc)

    # Q1/Q2: 10,000 uniformly sampled patient IDs
    n_sample = 10_000
    if len(patient_ids) >= n_sample:
        q1_q2_pids = rng.sample(patient_ids, n_sample)
    else:
        q1_q2_pids = [rng.choice(patient_ids) for _ in range(n_sample)]

    # Q3: 12 quarterly windows in the last 3 years
    q3_windows = []
    y, m = recent_3y_start.year, recent_3y_start.month
    for _ in range(12):
        q_start = datetime(y, m, 1, tzinfo=timezone.utc)
        m2 = m + 3
        y2 = y + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1
        q_end = datetime(y2, m2, 1, tzinfo=timezone.utc)
        q3_windows.append({
            "qStart": format_iso_utc(q_start),
            "qEnd": format_iso_utc(q_end),
        })
        y, m = y2, m2

    # Q4: 36 monthly windows in the last 3 years
    q4_windows = []
    y, m = recent_3y_start.year, recent_3y_start.month
    for _ in range(36):
        m_start = datetime(y, m, 1, tzinfo=timezone.utc)
        m2 = m + 1
        y2 = y + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1
        m_end = datetime(y2, m2, 1, tzinfo=timezone.utc)
        q4_windows.append({
            "mStart": format_iso_utc(m_start),
            "mEnd": format_iso_utc(m_end),
        })
        y, m = y2, m2

    # R3-1 explain samples: 5 fixed parameter sets
    explain_samples = []
    for s in range(5):
        qw = q3_windows[min(s * 2 + 1, len(q3_windows) - 1)]
        mw = q4_windows[min(s * 6 + 3, len(q4_windows) - 1)]
        explain_samples.append({
            "sample": s + 1,
            "pid": q1_q2_pids[s],
            "d12mAgo": format_iso_utc(d12m_ago),
            "qStart": qw["qStart"],
            "qEnd": qw["qEnd"],
            "mStart": mw["mStart"],
            "mEnd": mw["mEnd"],
        })

    return {
        "seed": seed,
        "dataset": dataset_name,
        "num_patients": len(patient_ids),
        "date_range": {
            "min_start": min_start_iso,
            "max_start": max_start_iso,
            "recent_3y_start": format_iso_utc(recent_3y_start),
        },
        "d12mAgo": format_iso_utc(d12m_ago),
        "q1_q2_pids": q1_q2_pids,
        "q3_windows": q3_windows,
        "q4_windows": q4_windows,
        "explain_samples": explain_samples,
    }


def write_nested_datasets(
    out_root: Path,
    seed_patients: list[dict[str, Any]],
    seed_enc_lists: list[list[dict[str, Any]]],
    max_dt: datetime,
    compresslevel: int = 3,
) -> dict[str, Any]:
    """Stream-generate D100K ⊂ D500K ⊂ D1M ⊂ D3M in a single pass."""
    t0 = time.time()
    print("[2/5] Planning exact nested patient schedule (D100K ⊂ D500K ⊂ D1M ⊂ D3M) ...", flush=True)
    seed_counts = [len(encs) for encs in seed_enc_lists]
    rng_plan = random.Random(SEED)
    plan, milestone_pat_idx = build_exact_patient_plan(seed_counts, MILESTONES, rng_plan)
    for name, target in MILESTONES:
        print(f"  {name}: {target:,} encounters across {milestone_pat_idx[name]:,} patients", flush=True)

    print("[3/5] Streaming D100K, D500K, D1M, D3M (.jsonl.gz) in single pass ...", flush=True)
    writers: dict[str, tuple[Any, Any]] = {}
    stats: dict[str, dict[str, Any]] = {}
    for name, _ in MILESTONES:
        ds_dir = out_root / name
        ds_dir.mkdir(parents=True, exist_ok=True)
        enc_f = gzip.open(ds_dir / "encounters.jsonl.gz", "wt", encoding="utf-8", compresslevel=compresslevel)
        pat_f = gzip.open(ds_dir / "patients.jsonl.gz", "wt", encoding="utf-8", compresslevel=compresslevel)
        writers[name] = (enc_f, pat_f)
        stats[name] = {
            "encounters": 0,
            "patients": 0,
            "patient_ids": [],
            "min_start": None,
            "max_start": None,
            "json_bytes": 0,
            "est_bson_bytes": 0,
            "diabetes_t2_docs": 0,
            "lab_obs_docs": 0,
            "total_conditions": 0,
            "total_observations": 0,
        }

    rng_mat = random.Random(SEED + 1)
    active = [name for name, _ in MILESTONES]
    total_pats = len(plan)

    for p_idx, (s_idx, ep) in enumerate(plan, start=1):
        pat_doc, enc_docs = materialize_patient_and_encounters(
            seed_patients[s_idx], seed_enc_lists[s_idx], ep, rng_mat, max_dt
        )
        pat_line = json.dumps(pat_doc, separators=(",", ":")) + "\n"
        enc_lines: list[str] = []
        p_json_bytes = 0
        p_bson_bytes = 0
        p_diab = 0
        p_lab = 0
        p_conds = 0
        p_obs = 0
        p_min_s: str | None = None
        p_max_s: str | None = None

        for ed in enc_docs:
            line = json.dumps(ed, separators=(",", ":")) + "\n"
            enc_lines.append(line)
            p_json_bytes += len(line.encode("utf-8"))
            if "D100K" in active:
                p_bson_bytes += estimate_bson_size(ed)
            s_val = ed["START"]
            if p_min_s is None or s_val < p_min_s:
                p_min_s = s_val
            if p_max_s is None or s_val > p_max_s:
                p_max_s = s_val
            c_list = ed["conditions"]
            o_list = ed["observations"]
            p_conds += len(c_list)
            p_obs += len(o_list)
            if any(c["CODE"] == DIABETES_T2_CODE for c in c_list):
                p_diab += 1
            if any(o["CATEGORY"] == "laboratory" for o in o_list):
                p_lab += 1

        enc_chunk = "".join(enc_lines)
        n_encs = len(enc_docs)
        pat_id = pat_doc["_id"]

        for name in active:
            enc_f, pat_f = writers[name]
            pat_f.write(pat_line)
            enc_f.write(enc_chunk)
            st = stats[name]
            st["encounters"] += n_encs
            st["patients"] += 1
            st["patient_ids"].append(pat_id)
            st["json_bytes"] += p_json_bytes
            st["est_bson_bytes"] += p_bson_bytes
            st["diabetes_t2_docs"] += p_diab
            st["lab_obs_docs"] += p_lab
            st["total_conditions"] += p_conds
            st["total_observations"] += p_obs
            if p_min_s and (st["min_start"] is None or p_min_s < st["min_start"]):
                st["min_start"] = p_min_s
            if p_max_s and (st["max_start"] is None or p_max_s > st["max_start"]):
                st["max_start"] = p_max_s

        # Close any milestone reached at this patient index
        newly_done = [name for name in active if p_idx == milestone_pat_idx[name]]
        for name in newly_done:
            enc_f, pat_f = writers[name]
            enc_f.close()
            pat_f.close()
            active.remove(name)
            ds_dir = out_root / name
            st = stats[name]
            (ds_dir / "patient_ids.txt").write_text("\n".join(st["patient_ids"]) + "\n", encoding="utf-8")
            qp = generate_query_params(name, st["patient_ids"], st["min_start"], st["max_start"], SEED)
            (ds_dir / "query_params.json").write_text(json.dumps(qp, indent=2), encoding="utf-8")
            print(
                f"  Finished {name}: {st['encounters']:,} encounters, {st['patients']:,} patients "
                f"({time.time() - t0:.1f}s)",
                flush=True,
            )

        if p_idx % 10_000 == 0 or p_idx == total_pats:
            print(f"  Progress: {p_idx:,}/{total_pats:,} patients ({time.time() - t0:.1f}s)", flush=True)

    # Create D1M-nat symlink -> D1M
    d1m_nat = out_root / "D1M-nat"
    if d1m_nat.is_symlink() or d1m_nat.exists():
        d1m_nat.unlink()
    os.symlink("D1M", d1m_nat)
    print("  Created symlink data/D1M-nat -> D1M", flush=True)

    summary = {}
    for name, _ in MILESTONES:
        st = stats[name]
        ds_dir = out_root / name
        enc_gz_mb = (ds_dir / "encounters.jsonl.gz").stat().st_size / (1024 * 1024)
        pat_gz_mb = (ds_dir / "patients.jsonl.gz").stat().st_size / (1024 * 1024)
        summary[name] = {
            "encounters": st["encounters"],
            "patients": st["patients"],
            "avg_encounters_per_patient": round(st["encounters"] / st["patients"], 2),
            "avg_json_bytes": round(st["json_bytes"] / st["encounters"], 1),
            "est_avg_bson_bytes": round(st["est_bson_bytes"] / st["encounters"], 1) if st["est_bson_bytes"] else None,
            "encounters_gz_mb": round(enc_gz_mb, 2),
            "patients_gz_mb": round(pat_gz_mb, 2),
            "diabetes_t2_docs": st["diabetes_t2_docs"],
            "lab_obs_docs": st["lab_obs_docs"],
            "avg_conditions_per_doc": round(st["total_conditions"] / st["encounters"], 2),
            "avg_observations_per_doc": round(st["total_observations"] / st["encounters"], 2),
            "min_start": st["min_start"],
            "max_start": st["max_start"],
        }
    return summary


def write_d1m_heavy(
    out_root: Path,
    seed_patients: list[dict[str, Any]],
    seed_enc_lists: list[list[dict[str, Any]]],
    max_dt: datetime,
    compresslevel: int = 3,
) -> dict[str, Any]:
    """Build D1M-heavy: 1,000,000 encounters where exact 1% PATIENTs hold exact 30% (300,000) docs."""
    t0 = time.time()
    print("[4/5] Building D1M-heavy (exact 1% PATIENTs = exact 300,000 encounters) ...", flush=True)
    seed_counts = [len(encs) for encs in seed_enc_lists]
    rng = random.Random(SEED + 200)

    # First plan the 99% normal patients to sum to exact 700,000 encounters,
    # ensuring their count is a multiple of 99 (so total = 100 * k, hot = 1 * k = exact 1.00%!).
    normal_plan, _ = build_exact_patient_plan(seed_counts, [("normal_700k", 700_000)], rng)

    # Adjust len(normal_plan) to be divisible by 99 while keeping exact sum = 700,000
    by_count: dict[int, list[int]] = defaultdict(list)
    for idx, c in enumerate(seed_counts):
        by_count[c].append(idx)

    rem_mod = len(normal_plan) % 99
    if rem_mod != 0:
        # Remove `rem_mod` patients (or add `99 - rem_mod` patients) while adjusting encounters to keep 700,000.
        # Easiest: pop a few patients at the tail until we have a surplus of docs, then refill with exact count of patients!
        target_p_normal = (len(normal_plan) // 99) * 99
        # Pop down so remaining docs per patient is around ~55 (dense region of seed counts)
        pop_to = max(0, target_p_normal - 25)
        normal_plan = normal_plan[:pop_to]
        cur_docs = sum(seed_counts[s] for s, _ in normal_plan)
        need_pats = target_p_normal - len(normal_plan)
        need_docs = 700_000 - cur_docs

        # Build a dense set of counts (every count present in by_count)
        avail_counts = sorted(by_count.keys())
        avail_set = set(avail_counts)
        # Pick need_pats - 2 patients aiming right at the mean, then solve exact pair for the last 2
        for step in range(need_pats - 2):
            left_pats = need_pats - step - 1
            avg_c = need_docs / (left_pats + 1)
            chosen_c = min(avail_counts, key=lambda c: abs(c - avg_c))
            normal_plan.append((rng.choice(by_count[chosen_c]), 9000 + step))
            need_docs -= chosen_c

        # Find exact pair (c1, c2) in avail_counts summing to need_docs
        pair_found = None
        for c1 in avail_counts:
            c2 = need_docs - c1
            if c2 in avail_set:
                pair_found = (c1, c2)
                break
        if pair_found is None:
            raise RuntimeError(f"Could not find pair summing to {need_docs}")
        normal_plan.append((rng.choice(by_count[pair_found[0]]), 9901))
        normal_plan.append((rng.choice(by_count[pair_found[1]]), 9902))

    assert len(normal_plan) % 99 == 0
    assert sum(seed_counts[s] for s, _ in normal_plan) == 700_000
    k_hot = len(normal_plan) // 99
    total_pats = 100 * k_hot
    print(
        f"  D1M-heavy plan: {total_pats:,} total patients "
        f"({len(normal_plan):,} normal = 99% -> 700,000 docs; {k_hot:,} hot = 1% -> 300,000 docs)",
        flush=True,
    )

    # Pick k_hot seed patients for the 1% hot group
    hot_plan = [(rng.randrange(len(seed_patients)), 5000 + i) for i in range(k_hot)]

    # Materialize & write
    ds_dir = out_root / "D1M-heavy"
    ds_dir.mkdir(parents=True, exist_ok=True)
    enc_f = gzip.open(ds_dir / "encounters.jsonl.gz", "wt", encoding="utf-8", compresslevel=compresslevel)
    pat_f = gzip.open(ds_dir / "patients.jsonl.gz", "wt", encoding="utf-8", compresslevel=compresslevel)

    patient_ids: list[str] = []
    min_start: str | None = None
    max_start: str | None = None
    json_bytes = 0
    diabetes_t2_docs = 0
    lab_obs_docs = 0
    total_written = 0

    # 1. Write 99% normal patients (700,000 docs)
    for s_idx, ep in normal_plan:
        pat_doc, enc_docs = materialize_patient_and_encounters(
            seed_patients[s_idx], seed_enc_lists[s_idx], ep + 10, rng, max_dt
        )
        pat_f.write(json.dumps(pat_doc, separators=(",", ":")) + "\n")
        patient_ids.append(pat_doc["_id"])
        for ed in enc_docs:
            line = json.dumps(ed, separators=(",", ":")) + "\n"
            enc_f.write(line)
            json_bytes += len(line.encode("utf-8"))
            total_written += 1
            s_val = ed["START"]
            if min_start is None or s_val < min_start:
                min_start = s_val
            if max_start is None or s_val > max_start:
                max_start = s_val
            if any(c["CODE"] == DIABETES_T2_CODE for c in ed["conditions"]):
                diabetes_t2_docs += 1
            if any(o["CATEGORY"] == "laboratory" for o in ed["observations"]):
                lab_obs_docs += 1

    # 2. Write 1% hot patients (exact 300,000 docs via cloning within last 3 years)
    recent_3y_start = max_dt - timedelta(days=365 * 3)
    recent_span_sec = int((max_dt - recent_3y_start).total_seconds())

    base_per_hot = 300_000 // k_hot
    extra_hot = 300_000 % k_hot
    hot_total_docs = 0

    for h_i, (s_idx, ep) in enumerate(hot_plan):
        target_for_this_hot = base_per_hot + (1 if h_i < extra_hot else 0)
        pat_doc, base_encs = materialize_patient_and_encounters(
            seed_patients[s_idx], seed_enc_lists[s_idx], ep + 10, rng, max_dt
        )
        pat_f.write(json.dumps(pat_doc, separators=(",", ":")) + "\n")
        patient_ids.append(pat_doc["_id"])

        written_this = 0
        # First emit original encounters (up to target)
        for ed in base_encs:
            if written_this >= target_for_this_hot:
                break
            line = json.dumps(ed, separators=(",", ":")) + "\n"
            enc_f.write(line)
            json_bytes += len(line.encode("utf-8"))
            written_this += 1
            total_written += 1
            hot_total_docs += 1
            s_val = ed["START"]
            if min_start is None or s_val < min_start:
                min_start = s_val
            if max_start is None or s_val > max_start:
                max_start = s_val
            if any(c["CODE"] == DIABETES_T2_CODE for c in ed["conditions"]):
                diabetes_t2_docs += 1
            if any(o["CATEGORY"] == "laboratory" for o in ed["observations"]):
                lab_obs_docs += 1

        # Clone encounters with new _id and valid START within the last 3 years
        n_base = len(base_encs)
        clone_idx = 0
        while written_this < target_for_this_hot:
            src = base_encs[clone_idx % n_base]
            clone_idx += 1
            orig_start = parse_iso_utc(src["START"])
            orig_stop = parse_iso_utc(src["STOP"])
            dur = max(0, int((orig_stop - orig_start).total_seconds()))
            new_start = recent_3y_start + timedelta(seconds=rng.randint(0, recent_span_sec))
            new_stop = new_start + timedelta(seconds=dur)

            cloned = {
                "_id": make_deterministic_uuid(rng),
                "PATIENT": pat_doc["_id"],
                "ORGANIZATION": src["ORGANIZATION"],
                "ENCOUNTERCLASS": src["ENCOUNTERCLASS"],
                "START": format_iso_utc(new_start),
                "STOP": format_iso_utc(new_stop),
                "TOTAL_CLAIM_COST": src["TOTAL_CLAIM_COST"],
                "conditions": src["conditions"],
                "observations": src["observations"],
            }
            line = json.dumps(cloned, separators=(",", ":")) + "\n"
            enc_f.write(line)
            json_bytes += len(line.encode("utf-8"))
            written_this += 1
            total_written += 1
            hot_total_docs += 1
            s_val = cloned["START"]
            if min_start is None or s_val < min_start:
                min_start = s_val
            if max_start is None or s_val > max_start:
                max_start = s_val
            if any(c["CODE"] == DIABETES_T2_CODE for c in cloned["conditions"]):
                diabetes_t2_docs += 1
            if any(o["CATEGORY"] == "laboratory" for o in cloned["observations"]):
                lab_obs_docs += 1

    enc_f.close()
    pat_f.close()

    assert total_written == 1_000_000, f"Expected 1,000,000, got {total_written}"
    assert hot_total_docs == 300_000, f"Expected 300,000 hot docs, got {hot_total_docs}"
    assert len(patient_ids) == total_pats

    (ds_dir / "patient_ids.txt").write_text("\n".join(patient_ids) + "\n", encoding="utf-8")
    qp = generate_query_params("D1M-heavy", patient_ids, min_start or "", max_start or "", SEED)
    (ds_dir / "query_params.json").write_text(json.dumps(qp, indent=2), encoding="utf-8")

    enc_gz_mb = (ds_dir / "encounters.jsonl.gz").stat().st_size / (1024 * 1024)
    pat_gz_mb = (ds_dir / "patients.jsonl.gz").stat().st_size / (1024 * 1024)
    print(
        f"  Finished D1M-heavy: {total_written:,} encounters, {total_pats:,} patients "
        f"(hot {k_hot:,} = 1.00% -> {hot_total_docs:,} docs = 30.00%, {time.time() - t0:.1f}s)",
        flush=True,
    )
    return {
        "encounters": total_written,
        "patients": total_pats,
        "hot_patients": k_hot,
        "hot_patient_pct": round(100.0 * k_hot / total_pats, 4),
        "hot_encounters": hot_total_docs,
        "hot_encounter_pct": round(100.0 * hot_total_docs / total_written, 4),
        "avg_json_bytes": round(json_bytes / total_written, 1),
        "encounters_gz_mb": round(enc_gz_mb, 2),
        "patients_gz_mb": round(pat_gz_mb, 2),
        "diabetes_t2_docs": diabetes_t2_docs,
        "lab_obs_docs": lab_obs_docs,
        "min_start": min_start,
        "max_start": max_start,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Synthea MongoDB benchmark datasets.")
    parser.add_argument("--csv-dir", type=Path, required=True, help="Synthea CSV output directory")
    parser.add_argument("--out-dir", type=Path, default=Path("data"), help="Output data root directory")
    parser.add_argument("--compresslevel", type=int, default=3, help="Gzip compression level (1-9)")
    parser.add_argument("--only-heavy", action="store_true", help="Only build D1M-heavy (skip D100K..D3M)")
    args = parser.parse_args()

    t_start = time.time()
    seed_patients, seed_enc_lists, min_dt, max_dt = load_synthea_seed(args.csv_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.only_heavy:
        heavy_summary = write_d1m_heavy(args.out_dir, seed_patients, seed_enc_lists, max_dt, args.compresslevel)
        print(f"Built D1M-heavy in {time.time() - t_start:.1f}s: {json.dumps(heavy_summary, indent=2)}", flush=True)
        return

    summary = write_nested_datasets(args.out_dir, seed_patients, seed_enc_lists, max_dt, args.compresslevel)
    summary["D1M-nat"] = {"symlink_to": "D1M", **summary["D1M"]}
    summary["D1M-heavy"] = write_d1m_heavy(args.out_dir, seed_patients, seed_enc_lists, max_dt, args.compresslevel)

    # Extrapolate D3M MongoDB Data + Index size from D100K avgObjSize (BSON)
    d100k = summary["D100K"]
    avg_bson = d100k["est_avg_bson_bytes"]
    d3m_raw_bson_gb = (avg_bson * 3_000_000) / (1024 ** 3)
    # 5 indexes on encounters (incl. _id, PATIENT+START, START, conditions.CODE+START, ENCOUNTERCLASS+START + shard key):
    # ~25-35% of raw BSON size (or ~1.2-1.8 GB for 3M docs, especially multikey index on conditions.CODE)
    d3m_est_index_gb = round(d3m_raw_bson_gb * 0.30, 2)
    d3m_est_wt_disk_gb = round(d3m_raw_bson_gb * 0.35 + d3m_est_index_gb * 0.5, 2)  # WiredTiger snappy compression
    d3m_est_uncompressed_total_gb = round(d3m_raw_bson_gb + d3m_est_index_gb, 2)

    summary["_capacity_estimate"] = {
        "d100k_est_avg_bson_bytes": avg_bson,
        "d3m_uncompressed_bson_gb": round(d3m_raw_bson_gb, 2),
        "d3m_est_indexes_gb": d3m_est_index_gb,
        "d3m_est_total_in_memory_gb": d3m_est_uncompressed_total_gb,
        "d3m_est_wiredtiger_disk_gb": d3m_est_wt_disk_gb,
        "exceeds_1_5gb_wt_cache": d3m_est_uncompressed_total_gb > 1.5,
        "total_build_seconds": round(time.time() - t_start, 1),
    }

    summary_path = args.out_dir / "DATASET_SUMMARY.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[5/5] Wrote {summary_path} in {time.time() - t_start:.1f}s total.", flush=True)


if __name__ == "__main__":
    main()
