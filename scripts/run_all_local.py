#!/usr/bin/env python3
"""Automated single-host orchestrator for clean MongoDB 7.0 sharding benchmarks.

Runs SA, SH-hash, and SH-range sequentially on one physical machine with:
  - Warm-up strictly excluded from elapsed time and telemetry (via patched bench_v2.py)
  - Synthetic TN2-write documents purged between reps and compacted before S4
  - SH-range shard1RS compacted after Balancer migration before TN3/TN2-write
  - Complete Q1, Q3, Q4 measurements on SH-range and 3 reps on all RQ3 slope points
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPO = Path("/mnt/lamviec/keepskyclear.Obsidian/9_Projects/DBMS/DBMS-distributed-method-benchmarking")
DEFAULT_DATA = Path("/mnt/lamviec/keepskyclear.Obsidian/9_Projects/DBMS/data")

ALL_CONTAINERS = ["mdb-sa", "mdb-mongos", "mdb-shard1", "mdb-shard2", "mdb-cfgsvr"]


def ts_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Runner:
    def __init__(self, repo_root: Path, data_root: Path, py_exe: Path, log_path: Path) -> None:
        self.repo_root = repo_root
        self.data_root = data_root
        self.py_exe = py_exe
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str) -> None:
        line = f"[{ts_now()}] {msg}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def run_cmd(self, cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
        self.log("CMD: " + " ".join(cmd))
        res = subprocess.run(
            cmd,
            cwd=str(self.repo_root),
            text=True,
            capture_output=capture,
            check=False,
        )
        if capture:
            if res.stdout:
                for ln in res.stdout.strip().splitlines():
                    self.log("  | " + ln)
            if res.stderr:
                for ln in res.stderr.strip().splitlines():
                    self.log("  ! " + ln)
        if check and res.returncode != 0:
            raise RuntimeError(f"Command failed (rc={res.returncode}): {' '.join(cmd)}")
        return res

    def docker_cleanup(self) -> None:
        self.run_cmd(["docker", "rm", "-f", *ALL_CONTAINERS], check=False, capture=True)
        self.run_cmd(["docker", "network", "rm", "mdb-net"], check=False, capture=True)

    def check_containers_healthy(self, names: list[str]) -> None:
        for name in names:
            res = self.run_cmd(
                ["docker", "inspect", "-f", "{{.State.Running}}|{{.State.OOMKilled}}|{{.RestartCount}}", name],
                capture=True,
            )
            state = res.stdout.strip()
            parts = state.split("|")
            if len(parts) != 3 or parts[0] != "true" or parts[1] != "false" or parts[2] != "0":
                raise RuntimeError(f"Container {name} unhealthy: {state}")
        self.log(f"Container health OK: {', '.join(names)}")

    def mongo_client(self, uri: str, timeout_ms: int = 600_000):
        # Import using venv python? We run this orchestrator WITH .venv/bin/python,
        # or if invoked via system python, fall back gracefully.
        from pymongo import MongoClient

        return MongoClient(uri, serverSelectionTimeoutMS=10_000, socketTimeoutMS=timeout_ms)

    def wait_for_writable_primary(self, uri: str, label: str, timeout_s: int = 60) -> None:
        deadline = time.monotonic() + timeout_s
        last_err = ""
        while time.monotonic() < deadline:
            try:
                c = self.mongo_client(uri, timeout_ms=5_000)
                hello = c.admin.command("hello")
                c.close()
                if hello.get("isWritablePrimary") or hello.get("ismaster"):
                    self.log(f"Primary ready on {label}")
                    return
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
            time.sleep(1.5)
        raise RuntimeError(f"Timeout waiting for writable primary on {label}: {last_err}")

    def wait_for_mongos(self, uri: str, timeout_s: int = 60) -> None:
        deadline = time.monotonic() + timeout_s
        last_err = ""
        while time.monotonic() < deadline:
            try:
                c = self.mongo_client(uri, timeout_ms=5_000)
                c.admin.command("ping")
                c.close()
                self.log("mongos ready")
                return
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
            time.sleep(1.5)
        raise RuntimeError(f"Timeout waiting for mongos: {last_err}")

    def assert_collection_state(self, uri: str, expected_count: int, expected_indexes: int = 4) -> None:
        c = self.mongo_client(uri)
        try:
            col = c["ehr"]["encounters"]
            cnt = col.count_documents({})
            idxs = list(col.list_indexes())
            self.log(f"Verify state: encounters.count={cnt:,} (expected {expected_count:,}), indexes={len(idxs)}")
            if cnt != expected_count:
                raise RuntimeError(f"Count mismatch: got {cnt}, expected {expected_count}")
            if len(idxs) < expected_indexes:
                raise RuntimeError(f"Missing indexes: got {len(idxs)}, expected >= {expected_indexes}: {idxs}")
        finally:
            c.close()

    def cleanup_bench_docs(self, uri: str, expected_after: int, shard_uris: list[str] | None = None, compact: bool = False) -> None:
        c = self.mongo_client(uri)
        try:
            res = c["ehr"]["encounters"].delete_many({"_id": {"$regex": "^bench-"}})
            self.log(f"Purged synthetic TN2-write docs: deleted={res.deleted_count:,}")
            cnt = c["ehr"]["encounters"].count_documents({})
            if cnt != expected_after:
                raise RuntimeError(f"Post-purge count mismatch: got {cnt}, expected {expected_after}")
        finally:
            c.close()

        if compact:
            targets = shard_uris or [uri]
            for u in targets:
                sc = self.mongo_client(u)
                try:
                    t0 = time.monotonic()
                    out = sc["ehr"].command({"compact": "encounters", "force": True})
                    self.log(f"Compacted {u} in {time.monotonic() - t0:.1f}s: {out}")
                finally:
                    sc.close()

    def load_step(self, uri: str, step_path: Path, env: str, meta_out: Path) -> None:
        cmd = [
            str(self.py_exe),
            "scripts/load_dataset.py",
            "--uri", uri,
            "--dataset", str(step_path),
            "--env", env,
            "--meta-out", str(meta_out),
        ]
        self.run_cmd(cmd, capture=True)

    def run_bench(
        self,
        uri: str,
        node_uris: list[str],
        env: str,
        dataset: str,
        scenario: str,
        output_dir: Path,
        query: str = "Q1",
        threads: int = 1,
        rep: int = 1,
        warmup_s: int = 20,
        min_seconds: int = 30,
        duration: int = 60,
        idle_net_s: int = 0,
    ) -> None:
        cmd = [
            str(self.py_exe),
            "scripts/bench_v2.py",
            "--uri", uri,
            "--env", env,
            "--dataset", dataset,
            "--data-root", str(self.data_root),
            "--scenario", scenario,
            "--output-dir", str(output_dir),
        ]
        for nu in node_uris:
            cmd.extend(["--node-uri", nu])
        if scenario in ("TN1", "TN3-read"):
            cmd.extend([
                "--query", query,
                "--threads", str(threads),
                "--rep", str(rep),
                "--warmup-s", str(warmup_s),
                "--min-seconds", str(min_seconds),
            ])
            if idle_net_s > 0:
                cmd.extend(["--idle-net-s", str(idle_net_s)])
        elif scenario == "TN2-write":
            cmd.extend([
                "--threads", str(threads),
                "--duration", str(duration),
                "--rep", str(rep),
            ])
        self.run_cmd(cmd, capture=True)

        if scenario in ("TN1", "TN2-write", "TN3-read"):
            if scenario == "TN2-write":
                tag = f"{env}_{dataset}_TN2-write_t{threads}_r{rep}"
            else:
                tag = f"{env}_{dataset}_{scenario}_{query}_t{threads}_r{rep}"
            meta_p = self.repo_root / output_dir / "meta" / f"{tag}.json"
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            if meta.get("client_bound"):
                raise RuntimeError(f"CLIENT BOUND HIT on {tag}: client_cpu_max={meta.get('client_cpu_max')}%")
            if meta.get("n_success", 0) < meta.get("n_requests", 0) or meta.get("n_success", 0) == 0:
                raise RuntimeError(f"Failed requests in {tag}: {meta.get('n_success')}/{meta.get('n_requests')}")

    def create_secondary_indexes(self, uri: str) -> None:
        c = self.mongo_client(uri)
        try:
            col = c["ehr"]["encounters"]
            col.create_index([("PATIENT", 1), ("START", -1)])
            col.create_index([("START", 1)])
            col.create_index([("conditions.CODE", 1), ("START", 1)])
            self.log(f"Created 3 secondary indexes: {[i['name'] for i in col.list_indexes()]}")
        finally:
            c.close()

    def init_sharded_cluster(self, shard_key: dict[str, Any], num_initial_chunks: int | None, start_balancer: bool) -> None:
        self.docker_cleanup()
        self.run_cmd(["docker", "network", "create", "mdb-net"], capture=True)
        self.run_cmd([
            "docker", "run", "-d", "--name", "mdb-cfgsvr", "--network", "mdb-net",
            "--memory=512m", "--cpus=1", "-p", "27019:27019",
            "mongo:7.0", "mongod", "--configsvr", "--replSet", "cfgRS",
            "--port", "27019", "--bind_ip_all", "--wiredTigerCacheSizeGB", "0.25",
        ], capture=True)
        self.run_cmd([
            "docker", "run", "-d", "--name", "mdb-shard1", "--network", "mdb-net",
            "--memory=1g", "--cpus=2", "-p", "27118:27018",
            "mongo:7.0", "mongod", "--shardsvr", "--replSet", "shard1RS",
            "--port", "27018", "--bind_ip_all", "--wiredTigerCacheSizeGB", "0.50",
        ], capture=True)
        self.run_cmd([
            "docker", "run", "-d", "--name", "mdb-shard2", "--network", "mdb-net",
            "--memory=1g", "--cpus=2", "-p", "27218:27018",
            "mongo:7.0", "mongod", "--shardsvr", "--replSet", "shard2RS",
            "--port", "27018", "--bind_ip_all", "--wiredTigerCacheSizeGB", "0.50",
        ], capture=True)
        self.run_cmd([
            "docker", "run", "-d", "--name", "mdb-mongos", "--network", "mdb-net",
            "--memory=512m", "--cpus=2", "-p", "27017:27017",
            "mongo:7.0", "mongos", "--configdb", "cfgRS/mdb-cfgsvr:27019",
            "--port", "27017", "--bind_ip_all",
        ], capture=True)

        time.sleep(3)
        self.run_cmd(["docker", "exec", "mdb-cfgsvr", "mongosh", "--port", "27019", "--eval",
                      'rs.initiate({_id:"cfgRS", configsvr:true, members:[{_id:0, host:"mdb-cfgsvr:27019"}]})'], capture=True)
        self.run_cmd(["docker", "exec", "mdb-shard1", "mongosh", "--port", "27018", "--eval",
                      'rs.initiate({_id:"shard1RS", members:[{_id:0, host:"mdb-shard1:27018"}]})'], capture=True)
        self.run_cmd(["docker", "exec", "mdb-shard2", "mongosh", "--port", "27018", "--eval",
                      'rs.initiate({_id:"shard2RS", members:[{_id:0, host:"mdb-shard2:27018"}]})'], capture=True)

        self.wait_for_writable_primary("mongodb://localhost:27019/?directConnection=true", "cfgRS")
        self.wait_for_writable_primary("mongodb://localhost:27118/?directConnection=true", "shard1RS")
        self.wait_for_writable_primary("mongodb://localhost:27218/?directConnection=true", "shard2RS")
        self.wait_for_mongos("mongodb://localhost:27017")

        c = self.mongo_client("mongodb://localhost:27017")
        try:
            c.admin.command("addShard", "shard1RS/mdb-shard1:27018")
            c.admin.command("addShard", "shard2RS/mdb-shard2:27018")
            c["config"]["settings"].update_one({"_id": "chunksize"}, {"$set": {"value": 32}}, upsert=True)
            c.admin.command("enableSharding", "ehr")
            c.admin.command("shardCollection", "ehr.patients", key={"_id": "hashed"})
            sc_cmd: dict[str, Any] = {"shardCollection": "ehr.encounters", "key": shard_key}
            if num_initial_chunks is not None:
                sc_cmd["numInitialChunks"] = num_initial_chunks
            c.admin.command(sc_cmd)
            self.create_secondary_indexes("mongodb://localhost:27017")
            if start_balancer:
                c.admin.command("balancerStart")
            else:
                c.admin.command("balancerStop")
                # Wait until any initial round settles
                for _ in range(20):
                    bs = c.admin.command("balancerStatus")
                    if bs.get("mode") == "off" and not bs.get("inBalancerRound", False):
                        break
                    time.sleep(1)
            self.log(f"Cluster initialized (shard_key={shard_key}, balancer={c.admin.command('balancerStatus')})")
        finally:
            c.close()

    # ------------------------------------------------------------------ PHASES
    def _run_sa_up_to_d1m(self, compact_after_write: bool) -> str:
        self.docker_cleanup()
        self.run_cmd([
            "docker", "run", "-d", "--name", "mdb-sa",
            "--memory=1g", "--cpus=2", "-p", "27017:27017",
            "mongo:7.0", "mongod", "--replSet", "rs0", "--port", "27017",
            "--bind_ip_all", "--wiredTigerCacheSizeGB", "0.50",
        ], capture=True)
        time.sleep(3)
        self.run_cmd(["docker", "exec", "mdb-sa", "mongosh", "--port", "27017", "--eval",
                      'rs.initiate({_id:"rs0", members:[{_id:0, host:"localhost:27017"}]})'], capture=True)
        uri = "mongodb://localhost:27017/?directConnection=true"
        self.wait_for_writable_primary(uri, "mdb-sa")
        self.create_secondary_indexes(uri)
        nodes = [f"entry={uri}"]

        steps = [
            ("S1", "D100K", 100_000),
            ("S2", "D500K", 500_000),
            ("S3", "D1M", 1_000_000),
        ]
        for step, ds, exp_cnt in steps:
            self.load_step(uri, self.data_root / "load_v2" / step, "SA", Path("results/load") / f"SA_{step}.json")
            self.assert_collection_state(uri, exp_cnt)
            if ds == "D1M":
                self.run_bench(uri, nodes, "SA", "D1M", "TN2-dist", Path("results/RQ2"))
            for t in (1, 4, 8):
                for r in (1, 2, 3):
                    self.run_bench(uri, nodes, "SA", ds, "TN1", Path("results/RQ1"), query="Q1", threads=t, rep=r)

        # TN2-write at D1M with purge after EVERY rep (+ optional compact after rep 3)
        for r in (1, 2, 3):
            self.run_bench(uri, nodes, "SA", "D1M", "TN2-write", Path("results/RQ2"), threads=4, rep=r, duration=60)
            self.cleanup_bench_docs(uri, 1_000_000, compact=(compact_after_write and r == 3))
        return uri

    def run_sa_d100k_d1m(self) -> None:
        self.log("=== START PHASE SA-d100k-d1m ===")
        self._run_sa_up_to_d1m(compact_after_write=False)
        self.check_containers_healthy(["mdb-sa"])
        self.docker_cleanup()
        self.log("=== COMPLETE PHASE SA-d100k-d1m ===")

    def run_sa(self) -> None:
        self.log("=== START PHASE SA ===")
        uri = self._run_sa_up_to_d1m(compact_after_write=True)
        nodes = [f"entry={uri}"]

        # S4 + S5 -> D3M clean
        self.load_step(uri, self.data_root / "load_v2" / "S4", "SA", Path("results/load") / "SA_S4.json")
        self.assert_collection_state(uri, 2_000_007)
        self.load_step(uri, self.data_root / "load_v2" / "S5", "SA", Path("results/load") / "SA_S5.json")
        self.assert_collection_state(uri, 3_000_000)
        for t in (1, 4, 8):
            for r in (1, 2, 3):
                self.run_bench(uri, nodes, "SA", "D3M", "TN1", Path("results/RQ1"), query="Q1", threads=t, rep=r)

        self.check_containers_healthy(["mdb-sa"])
        self.docker_cleanup()
        self.log("=== COMPLETE PHASE SA ===")

    def run_sa_resume_d3m(self) -> None:
        self.log("=== RESUME PHASE SA FROM S5 (D3M) ===")
        uri = "mongodb://localhost:27017/?directConnection=true"
        nodes = [f"entry={uri}"]
        self.assert_collection_state(uri, 2_000_007)
        self.load_step(uri, self.data_root / "load_v2" / "S5", "SA", Path("results/load") / "SA_S5.json")
        self.assert_collection_state(uri, 3_000_000)
        for t in (1, 4, 8):
            for r in (1, 2, 3):
                self.run_bench(uri, nodes, "SA", "D3M", "TN1", Path("results/RQ1"), query="Q1", threads=t, rep=r)

        self.check_containers_healthy(["mdb-sa"])
        self.docker_cleanup()
        self.log("=== COMPLETE PHASE SA ===")

    def run_sh_hash(self) -> None:
        self.log("=== START PHASE SH-hash ===")
        self.init_sharded_cluster({"PATIENT": "hashed"}, num_initial_chunks=16, start_balancer=False)
        uri = "mongodb://localhost:27017"
        s1_uri = "mongodb://localhost:27118/?directConnection=true"
        s2_uri = "mongodb://localhost:27218/?directConnection=true"
        nodes = [f"mongos={uri}", f"s1={s1_uri}", f"s2={s2_uri}"]

        steps = [
            ("S1", "D100K", 100_000),
            ("S2", "D500K", 500_000),
            ("S3", "D1M", 1_000_000),
        ]
        for step, ds, exp_cnt in steps:
            self.load_step(uri, self.data_root / "load_v2" / step, "SH-hash", Path("results/load") / f"SH-hash_{step}.json")
            self.assert_collection_state(uri, exp_cnt)
            if ds == "D1M":
                self.run_bench(uri, nodes, "SH-hash", "D1M", "TN2-dist", Path("results/RQ2"))
            for t in (1, 4, 8):
                for r in (1, 2, 3):
                    idle = 15 if t == 1 else 0
                    self.run_bench(uri, nodes, "SH-hash", ds, "TN1", Path("results/RQ1"),
                                   query="Q1", threads=t, rep=r, idle_net_s=idle)
            if ds == "D1M":
                self.run_bench(uri, nodes, "SH-hash", "D1M", "TN3-explain", Path("results/RQ3"))
            for q in ("Q3", "Q4"):
                for r in (1, 2, 3):
                    self.run_bench(uri, nodes, "SH-hash", ds, "TN3-read", Path("results/RQ3"),
                                   query=q, threads=1, rep=r, idle_net_s=15)

        # TN2-write at D1M with purge after EVERY rep + compact on s1 & s2 after rep 3
        for r in (1, 2, 3):
            self.run_bench(uri, nodes, "SH-hash", "D1M", "TN2-write", Path("results/RQ2"), threads=4, rep=r, duration=60)
            self.cleanup_bench_docs(uri, 1_000_000, shard_uris=[s1_uri, s2_uri], compact=(r == 3))

        # S4 + S5 -> D3M clean
        self.load_step(uri, self.data_root / "load_v2" / "S4", "SH-hash", Path("results/load") / "SH-hash_S4.json")
        self.assert_collection_state(uri, 2_000_007)
        self.load_step(uri, self.data_root / "load_v2" / "S5", "SH-hash", Path("results/load") / "SH-hash_S5.json")
        self.assert_collection_state(uri, 3_000_000)
        for t in (1, 4, 8):
            for r in (1, 2, 3):
                idle = 15 if t == 1 else 0
                self.run_bench(uri, nodes, "SH-hash", "D3M", "TN1", Path("results/RQ1"),
                               query="Q1", threads=t, rep=r, idle_net_s=idle)
        for q in ("Q3", "Q4"):
            for r in (1, 2, 3):
                self.run_bench(uri, nodes, "SH-hash", "D3M", "TN3-read", Path("results/RQ3"),
                               query=q, threads=1, rep=r, idle_net_s=15)

        self.check_containers_healthy(["mdb-cfgsvr", "mdb-shard1", "mdb-shard2", "mdb-mongos"])
        self.docker_cleanup()
        self.log("=== COMPLETE PHASE SH-hash ===")

    def wait_for_sh_range_balance(self, uri: str, timeout_s: int = 900) -> None:
        c = self.mongo_client(uri)
        try:
            deadline = time.monotonic() + timeout_s
            stable_polls = 0
            while time.monotonic() < deadline:
                stats = c["ehr"].command({"collStats": "encounters"})
                shards = stats.get("shards", {})
                s1 = shards.get("shard1RS", {})
                s2 = shards.get("shard2RS", {})
                c1, c2 = s1.get("count", 0), s2.get("count", 0)
                mb1 = s1.get("size", 0) / 2**20
                mb2 = s2.get("size", 0) / 2**20
                diff_mb = abs(mb1 - mb2)
                bs = c.admin.command("balancerStatus")
                in_round = bs.get("inBalancerRound", False)
                migs = c["config"]["migrations"].count_documents({})
                self.log(f"Balance poll: s1=({c1:,}, {mb1:.1f}MB) s2=({c2:,}, {mb2:.1f}MB) diff={diff_mb:.1f}MB inRound={in_round} migs={migs}")
                if c2 > 0 and diff_mb < 96.0 and not in_round and migs == 0:
                    stable_polls += 1
                    if stable_polls >= 2:
                        self.log("Balancer settled within <96 MB threshold")
                        return
                else:
                    stable_polls = 0
                time.sleep(10)
            raise RuntimeError("Timeout waiting for SH-range Balancer to settle")
        finally:
            c.close()

    def cleanup_orphans(self, shard_uris: list[str], nss: str = "ehr.encounters") -> None:
        for u in shard_uris:
            sc = self.mongo_client(u, timeout_ms=1_200_000)
            try:
                stats = sc["ehr"].command({"collStats": "encounters"})
                if stats.get("numOrphanDocs", 0) == 0:
                    self.log(f"No orphan docs on {u}")
                    continue
                next_key: Any = None
                while True:
                    cmd: dict[str, Any] = {"cleanupOrphaned": nss}
                    if next_key is not None:
                        cmd["startingFromKey"] = next_key
                    res = sc.admin.command(cmd)
                    next_key = res.get("stoppedAtKey")
                    if not next_key:
                        break
                self.log(f"cleanupOrphaned complete on {u}")
            finally:
                sc.close()

    def run_sh_range(self) -> None:
        self.log("=== START PHASE SH-range ===")
        self.init_sharded_cluster({"START": 1, "PATIENT": 1}, num_initial_chunks=None, start_balancer=True)
        uri = "mongodb://localhost:27017"
        self.load_step(uri, self.data_root / "load_v2" / "D1M_sorted", "SH-range", Path("results/load/SH-range_D1M.json"))
        self.assert_collection_state(uri, 1_000_000)
        self._finish_sh_range()

    def run_sh_range_resume(self) -> None:
        self.log("=== RESUME PHASE SH-range ===")
        self._finish_sh_range()

    def _finish_sh_range(self) -> None:
        uri = "mongodb://localhost:27017"
        s1_uri = "mongodb://localhost:27118/?directConnection=true"
        s2_uri = "mongodb://localhost:27218/?directConnection=true"
        nodes = [f"mongos={uri}", f"s1={s1_uri}", f"s2={s2_uri}"]

        self.wait_for_sh_range_balance(uri, timeout_s=1200)

        # Stop balancer and wait for any active round to clear
        c = self.mongo_client(uri)
        try:
            c.admin.command("balancerStop")
            for _ in range(30):
                bs = c.admin.command("balancerStatus")
                migs = c["config"]["migrations"].count_documents({})
                if bs.get("mode") == "off" and not bs.get("inBalancerRound", False) and migs == 0:
                    break
                time.sleep(2)
        finally:
            c.close()

        # Drain delayed orphan deletions so shard counts sum cleanly to 1,000,000
        self.cleanup_orphans([s1_uri, s2_uri])

        # Snapshot pre-compact distribution (documents 96 MB threshold + migration bloat)
        self.run_bench(uri, nodes, "SH-range", "D1M", "TN2-dist", Path("results/RQ2"))

        # Compact both shards to reclaim deleted pages from Balancer chunk moves
        for u in (s1_uri, s2_uri):
            sc = self.mongo_client(u)
            try:
                t0 = time.monotonic()
                out = sc["ehr"].command({"compact": "encounters", "force": True})
                self.log(f"Compacted {u} in {time.monotonic() - t0:.1f}s: {out}")
            finally:
                sc.close()

        # Snapshot post-compact distribution
        sys.path.insert(0, str(self.repo_root / "scripts"))
        import bench_v2  # noqa: PLC0415
        c = self.mongo_client(uri)
        try:
            post_snap = bench_v2.snapshot_distribution(c, "ehr", "encounters", "SH-range")
            post_p = self.repo_root / "results/RQ2/dist/SH-range_D1M_dist_post_compact.json"
            post_p.write_text(json.dumps(post_snap, indent=2, default=str), encoding="utf-8")
            self.log(f"Wrote {post_p}: {post_snap['shards']}")
        finally:
            c.close()

        # TN3-explain + TN3-read for Q1, Q3, Q4 (1 thread, 3 reps, idle 15s)
        self.run_bench(uri, nodes, "SH-range", "D1M", "TN3-explain", Path("results/RQ3"))
        for q in ("Q1", "Q3", "Q4"):
            for r in (1, 2, 3):
                self.run_bench(uri, nodes, "SH-range", "D1M", "TN3-read", Path("results/RQ3"),
                               query=q, threads=1, rep=r, idle_net_s=15)

        # TN2-write (4 threads, 60s, 3 reps, purge between reps)
        for r in (1, 2, 3):
            self.run_bench(uri, nodes, "SH-range", "D1M", "TN2-write", Path("results/RQ2"), threads=4, rep=r, duration=60)
            self.cleanup_bench_docs(uri, 1_000_000, compact=False)

        self.check_containers_healthy(["mdb-cfgsvr", "mdb-shard1", "mdb-shard2", "mdb-mongos"])
        self.docker_cleanup()
        self.log("=== COMPLETE PHASE SH-range ===")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase", required=True, choices=["SA", "SA-d100k-d1m", "SA-resume-d3m", "SH-hash", "SH-range", "SH-range-resume", "all"])
    ap.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--python", type=Path, default=None)
    args = ap.parse_args()

    py_exe = args.python or (args.repo_root / ".venv/bin/python")
    log_path = args.repo_root / "results/sys" / f"{args.phase}_run.log"
    runner = Runner(args.repo_root, args.data_root, py_exe, log_path)

    if args.phase in ("SA", "all"):
        runner.run_sa()
    if args.phase == "SA-d100k-d1m":
        runner.run_sa_d100k_d1m()
    if args.phase == "SA-resume-d3m":
        runner.run_sa_resume_d3m()
    if args.phase in ("SH-hash", "all"):
        runner.run_sh_hash()
    if args.phase in ("SH-range", "all"):
        runner.run_sh_range()
    if args.phase == "SH-range-resume":
        runner.run_sh_range_resume()


if __name__ == "__main__":
    main()
