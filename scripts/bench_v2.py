#!/usr/bin/env python3
"""MongoDB 7.0 Sharding Benchmark Harness (Khung Thực nghiệm Tinh gọn — v3).

Hỗ trợ trực tiếp 3 môi trường (SA, SH-hash, SH-range), 3 truy vấn đọc (Q1, Q3, Q4)
và 3 thực nghiệm chính (TN1, TN2, TN3) đúng theo docs/EXPERIMENT_SPEC.md (v3):
  - TN1       : Đọc Q1 trên SA vs SH-hash (100K/500K/1M/3M × 1/4/8 luồng) -> p95, QPS.
  - TN2-dist  : Ảnh chụp getShardDistribution/collStats sau nạp/cân bằng (1M).
  - TN2-write : Ghi trực tuyến OLTP (START=now(), 4 luồng, 60s) -> % insert/shard, inserts/s, p95.
  - TN3-explain: Chụp explain('executionStats') cho Q1, Q3 (12 quý), Q4 (36 tháng) — hỗ trợ cả find & aggregate.
  - TN3-read  : Đo Q1, Q3, Q4 (1 luồng) kèm đo nền 15s idle network trên mongos -> p95, KB/req.

Ví dụ chạy nhanh:
  python3 scripts/bench_v2.py --uri mongodb://vm-w1:27017 --env SA --dataset D100K --scenario TN1 --query Q1 --threads 4 --rep 1 --output-dir results/RQ1
  python3 scripts/bench_v2.py --uri mongodb://vm-coord:27017 --node-uri mongos=mongodb://vm-coord:27017 --node-uri s1=mongodb://vm-w1:27018 --node-uri s2=mongodb://vm-w2:27018 --env SH-hash --dataset D1M --scenario TN2-write --threads 4 --rep 1 --output-dir results/RQ2
  python3 scripts/bench_v2.py --uri mongodb://vm-coord:27017 --env SH-hash --dataset D1M --scenario TN3-read --query Q4 --idle-net-s 15 --rep 1 --output-dir results/RQ3
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

Q4_CODE = "314529007"  # Medication review due (~834 docs/month at D1M)


# --------------------------------------------------------------------------- helpers
def parse_iso_utc(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    return s[int(k)] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def read_proc_cpu_ticks() -> tuple[int, int]:
    try:
        with open("/proc/stat", encoding="utf-8") as f:
            parts = [int(x) for x in f.readline().split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        total = sum(parts)
        return total - idle, total
    except OSError:
        return 0, 0


class CpuSampler(threading.Thread):
    def __init__(self, interval: float = 1.0) -> None:
        super().__init__(daemon=True)
        self.interval = interval
        self.stop_evt = threading.Event()
        self.samples: list[float] = []

    def run(self) -> None:
        b0, t0 = read_proc_cpu_ticks()
        while not self.stop_evt.wait(self.interval):
            b1, t1 = read_proc_cpu_ticks()
            dt = max(1, t1 - t0)
            self.samples.append(round(100.0 * (b1 - b0) / dt, 2))
            b0, t0 = b1, t1

    def stop_and_stats(self) -> tuple[float, float]:
        self.stop_evt.set()
        self.join(timeout=2.0)
        if not self.samples:
            return 0.0, 0.0
        return max(self.samples), round(sum(self.samples) / len(self.samples), 2)


# --------------------------------------------------------------------------- Queries (v3: Q1, Q3, Q4)
def run_query(col: Any, qid: str, params: dict[str, Any]) -> int:
    if qid == "Q1":
        cur = col.find(
            {"PATIENT": params["pid"]},
            {"START": 1, "ENCOUNTERCLASS": 1, "ORGANIZATION": 1, "conditions": 1},
        ).sort("START", -1)
        return sum(1 for _ in cur)
    if qid == "Q3":
        pipe = [
            {"$match": {"START": {"$gte": params["qStart"], "$lt": params["qEnd"]}}},
            {"$unwind": "$conditions"},
            {"$group": {"_id": "$conditions.CODE", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
            {"$limit": 10},
        ]
        return sum(1 for _ in col.aggregate(pipe))
    if qid == "Q4":
        cur = col.find(
            {"conditions.CODE": Q4_CODE, "START": {"$gte": params["mStart"], "$lt": params["mEnd"]}},
            {"PATIENT": 1, "START": 1, "ORGANIZATION": 1},
        )
        return sum(1 for _ in cur)
    raise ValueError(f"Unknown query: {qid}")


def explain_query(db: Any, col_name: str, qid: str, params: dict[str, Any]) -> dict[str, Any]:
    if qid in ("Q1", "Q4"):
        cmd: dict[str, Any] = {"find": col_name}
        if qid == "Q1":
            cmd["filter"] = {"PATIENT": params["pid"]}
            cmd["projection"] = {"START": 1, "ENCOUNTERCLASS": 1, "ORGANIZATION": 1, "conditions": 1}
            cmd["sort"] = {"START": -1}
        else:
            cmd["filter"] = {"conditions.CODE": Q4_CODE, "START": {"$gte": params["mStart"], "$lt": params["mEnd"]}}
            cmd["projection"] = {"PATIENT": 1, "START": 1, "ORGANIZATION": 1}
        raw = db.command({"explain": cmd, "verbosity": "executionStats"})
        wp = raw.get("queryPlanner", {}).get("winningPlan", {})
        es = raw.get("executionStats", {})
        stages = es.get("executionStages", {})
        shards_list = stages.get("shards", [])
        return {
            "query": qid,
            "type": "find",
            "winning_stage": wp.get("stage", stages.get("stage")),
            "shards_targeted": len(shards_list) if shards_list else 1,
            "merge_type": "mongos" if len(shards_list) > 1 else "none",
            "total_exec_ms": es.get("executionTimeMillis"),
            "nReturned": es.get("nReturned"),
            "totalKeysExamined": es.get("totalKeysExamined"),
            "totalDocsExamined": es.get("totalDocsExamined"),
            "raw": raw,
        }
    if qid == "Q3":
        pipe = [
            {"$match": {"START": {"$gte": params["qStart"], "$lt": params["qEnd"]}}},
            {"$unwind": "$conditions"},
            {"$group": {"_id": "$conditions.CODE", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
            {"$limit": 10},
        ]
        raw = db.command({"explain": {"aggregate": col_name, "pipeline": pipe, "cursor": {}}, "verbosity": "executionStats"})
        shards_map = raw.get("shards", {})
        split_pipe = raw.get("splitPipeline") or {}
        merge_type = raw.get("mergeType", "none" if len(shards_map) <= 1 else "unknown")
        tot_keys = tot_docs = 0
        for sbody in shards_map.values():
            st_list = sbody.get("stages", [])
            cur_es = st_list[0]["$cursor"].get("executionStats", {}) if (st_list and "$cursor" in st_list[0]) else {}
            tot_keys += cur_es.get("totalKeysExamined", 0) or 0
            tot_docs += cur_es.get("totalDocsExamined", 0) or 0
        return {
            "query": qid,
            "type": "aggregate",
            "winning_stage": "SPLIT_PIPELINE" if split_pipe else ("SINGLE_SHARD_AGG" if len(shards_map) == 1 else "LOCAL_AGG"),
            "shards_targeted": max(1, len(shards_map)),
            "merge_type": merge_type,
            "totalKeysExamined": tot_keys,
            "totalDocsExamined": tot_docs,
            "raw": raw,
        }
    raise ValueError(f"Unknown query: {qid}")


# --------------------------------------------------------------------------- MongoDB telemetry & pre-flight
def snapshot_server_status(uri: str) -> dict[str, Any]:
    from pymongo import MongoClient

    c = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        st = c.admin.command("serverStatus")
        wt = st.get("wiredTiger", {}).get("cache", {})
        net = st.get("network", {})
        ops = st.get("opcounters", {})
        return {
            "timestamp_utc": utc_now_iso(),
            "host": st.get("host"),
            "process": st.get("process"),
            "version": st.get("version"),
            "opcounters": {k: ops.get(k, 0) for k in ("insert", "query", "update", "delete", "getmore", "command")},
            "network": {k: net.get(k, 0) for k in ("bytesIn", "bytesOut", "numRequests")},
            "wt_cache": {
                "max_bytes": wt.get("maximum bytes configured", 0),
                "current_bytes": wt.get("bytes currently in the cache", 0),
                "pages_requested": wt.get("pages requested from the cache", 0),
                "pages_read_into_cache": wt.get("pages read into cache", 0),
                "bytes_read_into_cache": wt.get("bytes read into cache", 0),
            },
        }
    finally:
        c.close()


def diff_status(s0: dict[str, Any], s1: dict[str, Any]) -> dict[str, Any]:
    def d(sec: str) -> dict[str, Any]:
        return {k: s1[sec].get(k, 0) - s0[sec].get(k, 0) for k in s1[sec]}

    wt_d = d("wt_cache")
    req = max(1, wt_d.get("pages_requested", 0))
    reads = wt_d.get("pages_read_into_cache", 0)
    hit = round(1.0 - min(1.0, reads / req), 6) if wt_d.get("pages_requested", 0) > 0 else None
    return {
        "host": s1.get("host"),
        "process": s1.get("process"),
        "opcounters_delta": d("opcounters"),
        "network_delta": d("network"),
        "wt_cache_delta": wt_d,
        "wt_cache_hit_ratio": hit,
    }


def preflight_balancer_stopped(client: Any, env: str) -> dict[str, Any]:
    if env == "SA":
        return {"checked": False, "env": env}
    bs = client.admin.command("balancerStatus")
    active_migs = client["config"]["migrations"].count_documents({})
    mode = bs.get("mode")
    in_round = bs.get("inBalancerRound", False)
    if mode != "off" or in_round or active_migs > 0:
        raise RuntimeError(
            f"Pre-flight FAILED on {env}: balancerStatus mode={mode}, inBalancerRound={in_round}, "
            f"active_migrations={active_migs}. Run sh.stopBalancer() first."
        )
    return {"checked": True, "mode": mode, "inBalancerRound": in_round, "active_migrations": active_migs}


def measure_idle_network_bps(uri: str, seconds: int = 15) -> dict[str, float]:
    s0 = snapshot_server_status(uri)
    t0 = time.monotonic()
    time.sleep(seconds)
    s1 = snapshot_server_status(uri)
    dt = max(1e-3, time.monotonic() - t0)
    return {
        "idle_seconds": round(dt, 2),
        "idle_bytes_in_per_s": round((s1["network"]["bytesIn"] - s0["network"]["bytesIn"]) / dt, 2),
        "idle_bytes_out_per_s": round((s1["network"]["bytesOut"] - s0["network"]["bytesOut"]) / dt, 2),
    }


def snapshot_distribution(client: Any, db_name: str, col_name: str, env: str) -> dict[str, Any]:
    stats = client[db_name].command({"collStats": col_name})
    out: dict[str, Any] = {
        "timestamp_utc": utc_now_iso(),
        "env": env,
        "total_count": stats.get("count"),
        "total_size_mb": round(stats.get("size", 0) / 2**20, 2),
        "total_storage_mb": round(stats.get("storageSize", 0) / 2**20, 2),
        "total_index_mb": round(stats.get("totalIndexSize", 0) / 2**20, 2),
        "shards": {},
    }
    if "shards" in stats:
        tot = sum(s.get("size", 0) for s in stats["shards"].values())
        for sname, s in stats["shards"].items():
            out["shards"][sname] = {
                "count": s.get("count", 0),
                "size_mb": round(s.get("size", 0) / 2**20, 2),
                "size_pct": round(100.0 * s.get("size", 0) / max(1, tot), 2),
                "storage_mb": round(s.get("storageSize", 0) / 2**20, 2),
                "index_mb": round(s.get("totalIndexSize", 0) / 2**20, 2),
            }
    else:
        out["shards"]["single_node"] = {
            "count": stats.get("count", 0),
            "size_mb": round(stats.get("size", 0) / 2**20, 2),
            "size_pct": 100.0,
            "storage_mb": round(stats.get("storageSize", 0) / 2**20, 2),
            "index_mb": round(stats.get("totalIndexSize", 0) / 2**20, 2),
        }
    return out


# --------------------------------------------------------------------------- Workload runners
def make_param_generator(wl: dict[str, Any], patient_ids: list[str], seed: int):
    rng = random.Random(seed)
    q3_wins = [(parse_iso_utc(w["qStart"]), parse_iso_utc(w["qEnd"])) for w in wl["q3_windows"]]
    q4_wins = [(parse_iso_utc(w["mStart"]), parse_iso_utc(w["mEnd"])) for w in wl["q4_windows"]]
    n_pat = len(patient_ids)
    idx_q3 = 0
    idx_q4 = 0
    lock = threading.Lock()

    def next_params(qid: str) -> dict[str, Any]:
        nonlocal idx_q3, idx_q4
        with lock:
            if qid == "Q1":
                return {"pid": patient_ids[rng.randrange(n_pat)]}
            if qid == "Q3":
                qs, qe = q3_wins[idx_q3 % len(q3_wins)]
                idx_q3 += 1
                return {"qStart": qs, "qEnd": qe}
            ms, me = q4_wins[idx_q4 % len(q4_wins)]
            idx_q4 += 1
            return {"mStart": ms, "mEnd": me}

    return next_params


def run_read_benchmark(
    col: Any,
    qid: str,
    next_params: Any,
    threads: int,
    warmup_s: int,
    min_reqs: int,
    min_seconds: int,
    max_seconds: int,
    seed: int,
) -> list[dict[str, Any]]:
    # Warm-up
    if warmup_s > 0:
        w_end = time.monotonic() + warmup_s
        while time.monotonic() < w_end:
            run_query(col, qid, next_params(qid))

    rows: list[dict[str, Any]] = []
    lock = threading.Lock()
    counter = {"n": 0}
    t0 = time.monotonic()

    def worker(tid: int) -> None:
        local: list[dict[str, Any]] = []
        while True:
            elapsed = time.monotonic() - t0
            if elapsed >= max_seconds:
                break
            with lock:
                if elapsed >= min_seconds and counter["n"] >= min_reqs:
                    break
                counter["n"] += 1
            params = next_params(qid)
            ts = utc_now_iso()
            q0 = time.perf_counter()
            ok, docs, err = 1, 0, ""
            try:
                docs = run_query(col, qid, params)
            except Exception as exc:  # noqa: BLE001
                ok, err = 0, str(exc)[:180]
            local.append({
                "timestamp_iso": ts,
                "thread_id": tid,
                "query_id": qid,
                "latency_ms": round((time.perf_counter() - q0) * 1000.0, 4),
                "docs_returned": docs,
                "success": ok,
                "error_msg": err,
            })
        with lock:
            rows.extend(local)

    with ThreadPoolExecutor(max_workers=threads) as ex:
        for f in [ex.submit(worker, i) for i in range(threads)]:
            f.result()
    return rows


def run_write_benchmark(
    col: Any,
    patient_ids: list[str],
    threads: int,
    duration_s: int,
    seed: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lock = threading.Lock()
    stop_evt = threading.Event()

    def worker(tid: int) -> None:
        rng = random.Random(seed + tid * 1009)
        local: list[dict[str, Any]] = []
        seq = 0
        while not stop_evt.is_set():
            seq += 1
            now = datetime.now(timezone.utc)
            doc = {
                "_id": f"bench-{seed}-{tid}-{seq}-{rng.getrandbits(32):08x}",
                "PATIENT": patient_ids[rng.randrange(len(patient_ids))],
                "ORGANIZATION": "bench-org-001",
                "ENCOUNTERCLASS": "ambulatory",
                "START": now,
                "STOP": now,
                "TOTAL_CLAIM_COST": 125.0,
                "conditions": [{"CODE": Q4_CODE, "DESCRIPTION": "Medication review due (situation)"}],
                "observations": [{"CATEGORY": "laboratory", "CODE": "4548-4", "VALUE": 6.5, "UNITS": "%"}],
            }
            q0 = time.perf_counter()
            ok, err = 1, ""
            try:
                col.insert_one(doc)
            except Exception as exc:  # noqa: BLE001
                ok, err = 0, str(exc)[:180]
            local.append({
                "timestamp_iso": now.isoformat(),
                "thread_id": tid,
                "query_id": "INSERT",
                "latency_ms": round((time.perf_counter() - q0) * 1000.0, 4),
                "docs_returned": 1 if ok else 0,
                "success": ok,
                "error_msg": err,
            })
        with lock:
            rows.extend(local)

    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(worker, i) for i in range(threads)]
        time.sleep(duration_s)
        stop_evt.set()
        for f in futs:
            f.result()
    return rows


# --------------------------------------------------------------------------- CLI
def parse_node_uris(raw: list[str]) -> dict[str, str]:
    return dict(item.split("=", 1) for item in raw)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["timestamp_iso", "thread_id", "query_id", "latency_ms", "docs_returned", "success", "error_msg"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uri", required=True, help="MongoDB entry URI (mongos or SA 1-node RS)")
    ap.add_argument("--node-uri", action="append", default=[],
                    help="Per-node URIs for serverStatus telemetry, e.g. mongos=mongodb://... s1=mongodb://... s2=mongodb://...")
    ap.add_argument("--db", default="ehr")
    ap.add_argument("--collection", default="encounters")
    ap.add_argument("--env", required=True, choices=["SA", "SH-hash", "SH-range"])
    ap.add_argument("--dataset", required=True, choices=["D100K", "D500K", "D1M", "D3M"])
    ap.add_argument("--data-root", type=Path, default=Path("data"))
    ap.add_argument("--scenario", required=True, choices=["TN1", "TN2-dist", "TN2-write", "TN3-explain", "TN3-read"])
    ap.add_argument("--query", default="Q1", choices=["Q1", "Q3", "Q4"])
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--warmup-s", type=int, default=20)
    ap.add_argument("--min-reqs", type=int, default=0, help="0 = auto (2000 for Q1, 300 for Q3/Q4)")
    ap.add_argument("--min-seconds", type=int, default=30)
    ap.add_argument("--max-seconds", type=int, default=180)
    ap.add_argument("--duration", type=int, default=60, help="Seconds for TN2-write")
    ap.add_argument("--idle-net-s", type=int, default=0, help="Seconds to measure idle mongos network baseline (e.g. 15)")
    ap.add_argument("--client-cpu-limit", type=float, default=75.0)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()

    from pymongo import MongoClient

    client = MongoClient(args.uri, w="majority", readConcernLevel="local")
    db = client[args.db]
    col = db[args.collection]
    node_uris = parse_node_uris(args.node_uri) or {"entry": args.uri}

    ds_dir = args.data_root / args.dataset
    wl = json.loads((ds_dir / "workload_v2.json").read_text(encoding="utf-8"))
    patient_ids = sorted(l.strip() for l in (ds_dir / "patient_ids.txt").read_text(encoding="utf-8").splitlines() if l.strip())

    # ---- TN2-dist ----
    if args.scenario == "TN2-dist":
        snap = snapshot_distribution(client, args.db, args.collection, args.env)
        out_p = args.output_dir / "dist" / f"{args.env}_{args.dataset}_dist.json"
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {out_p}: {snap['shards']}")
        return

    # ---- TN3-explain ----
    if args.scenario == "TN3-explain":
        preflight_balancer_stopped(client, args.env)
        out_dir = args.output_dir / "explain"
        out_dir.mkdir(parents=True, exist_ok=True)
        for s in wl["explain_samples"]:
            res = explain_query(db, args.collection, "Q1", {"pid": s["pid"]})
            (out_dir / f"{args.env}_{args.dataset}_Q1_s{s['sample']}.json").write_text(
                json.dumps(res, indent=2, default=str), encoding="utf-8"
            )
        for i, w in enumerate(wl["q3_windows"], start=1):
            res = explain_query(db, args.collection, "Q3", {"qStart": parse_iso_utc(w["qStart"]), "qEnd": parse_iso_utc(w["qEnd"])})
            (out_dir / f"{args.env}_{args.dataset}_Q3_w{i:02d}.json").write_text(
                json.dumps(res, indent=2, default=str), encoding="utf-8"
            )
        for i, w in enumerate(wl["q4_windows"], start=1):
            res = explain_query(db, args.collection, "Q4", {"mStart": parse_iso_utc(w["mStart"]), "mEnd": parse_iso_utc(w["mEnd"])})
            (out_dir / f"{args.env}_{args.dataset}_Q4_w{i:02d}.json").write_text(
                json.dumps(res, indent=2, default=str), encoding="utf-8"
            )
        print(f"Wrote explain JSONs for {args.env}/{args.dataset} to {out_dir}")
        return

    # ---- Active measurement (TN1, TN2-write, TN3-read) ----
    bal_info = preflight_balancer_stopped(client, args.env)
    stream_seed = args.seed * 1000 + args.rep
    next_params = make_param_generator(wl, patient_ids, stream_seed)
    idle_net = measure_idle_network_bps(args.uri, args.idle_net_s) if args.idle_net_s > 0 else None

    start_utc = utc_now_iso()
    st0 = {k: snapshot_server_status(u) for k, u in node_uris.items()}
    cpu_sampler = CpuSampler(1.0)
    cpu_sampler.start()
    t0 = time.monotonic()

    if args.scenario in ("TN1", "TN3-read"):
        min_reqs = args.min_reqs or (2000 if args.query == "Q1" else 300)
        tag = f"{args.env}_{args.dataset}_{args.scenario}_{args.query}_t{args.threads}_r{args.rep}"
        rows = run_read_benchmark(col, args.query, next_params, args.threads, args.warmup_s,
                                  min_reqs, args.min_seconds, args.max_seconds, stream_seed)
    else:  # TN2-write
        tag = f"{args.env}_{args.dataset}_TN2-write_t{args.threads}_r{args.rep}"
        rows = run_write_benchmark(col, patient_ids, args.threads, args.duration, stream_seed)

    elapsed_s = round(time.monotonic() - t0, 3)
    client_cpu_max, client_cpu_avg = cpu_sampler.stop_and_stats()
    st1 = {k: snapshot_server_status(u) for k, u in node_uris.items()}
    end_utc = utc_now_iso()

    write_csv(args.output_dir / f"{tag}.csv", rows)
    status_dir = args.output_dir / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    deltas = {}
    for k in node_uris:
        deltas[k] = diff_status(st0[k], st1[k])
        (status_dir / f"{tag}_{k}.json").write_text(json.dumps(deltas[k], indent=2), encoding="utf-8")

    ok_lats = [r["latency_ms"] for r in rows if r["success"] == 1]
    # Compute net network KB/req on entry/mongos if available
    net_kb_per_req = None
    entry_key = "mongos" if "mongos" in deltas else "entry"
    if entry_key in deltas and ok_lats:
        nd = deltas[entry_key]["network_delta"]
        tot_b = nd.get("bytesIn", 0) + nd.get("bytesOut", 0)
        if idle_net:
            idle_b = (idle_net["idle_bytes_in_per_s"] + idle_net["idle_bytes_out_per_s"]) * elapsed_s
            tot_b = max(0.0, tot_b - idle_b)
        net_kb_per_req = round(tot_b / (1024.0 * len(ok_lats)), 3)

    meta = {
        "spec_version": 3,
        "env": args.env,
        "dataset": args.dataset,
        "scenario": args.scenario,
        "query": "INSERT" if args.scenario == "TN2-write" else args.query,
        "threads": args.threads,
        "rep": args.rep,
        "seed": args.seed,
        "client_host": socket.gethostname(),
        "mongo_version": client.server_info().get("version"),
        "balancer_preflight": bal_info,
        "idle_network_baseline": idle_net,
        "elapsed_s": elapsed_s,
        "n_requests": len(rows),
        "n_success": len(ok_lats),
        "qps_or_inserts_s": round(len(ok_lats) / max(1e-6, elapsed_s), 2),
        "p50_ms": round(percentile(ok_lats, 50), 3),
        "p95_ms": round(percentile(ok_lats, 95), 3),
        "net_kb_per_req": net_kb_per_req,
        "client_cpu_max": client_cpu_max,
        "client_cpu_avg": client_cpu_avg,
        "client_bound": client_cpu_max >= args.client_cpu_limit,
        "start_utc": start_utc,
        "end_utc": end_utc,
    }
    meta_path = args.output_dir / "meta" / f"{tag}.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"DONE {tag}: n={len(ok_lats)}, rate={meta['qps_or_inserts_s']}/s, p95={meta['p95_ms']}ms, "
          f"net={net_kb_per_req}KB/req, client_cpu_max={client_cpu_max}% (bound={meta['client_bound']})")


if __name__ == "__main__":
    main()
