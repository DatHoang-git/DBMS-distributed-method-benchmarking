import csv
import json
import math
import shlex
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ServerSelectionTimeoutError

uri = "mongodb://localhost:27017/?directConnection=true"
root = Path("results")
client = MongoClient(uri, serverSelectionTimeoutMS=1500)
db = client.ehr
expected_indexes = {
    (("_id", 1),),
    (("PATIENT", 1), ("START", -1)),
    (("START", 1),),
    (("conditions.CODE", 1), ("START", 1)),
}
groups = defaultdict(list)


def log(message):
    print(f"{datetime.now(timezone.utc).isoformat()} {message}", flush=True)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(*args):
    cmd = [sys.executable, *args]
    log(shlex.join(cmd))
    subprocess.run(cmd, check=True)


def wait_for(predicate, description):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except (AutoReconnect, ServerSelectionTimeoutError):
            pass
        time.sleep(1)
    raise RuntimeError(f"Timeout: {description}")


def check_indexes(label):
    index_list = list(db.encounters.list_indexes())
    keys = {tuple(index["key"].items()) for index in index_list}
    log(f"{label} indexes: {[(index['name'], list(index['key'].items())) for index in index_list]}")
    require(keys == expected_indexes, f"Unexpected indexes: {keys}")


def check_counts(label, expected_encounters, expected_patients):
    encounters = db.command("collStats", "encounters")["count"]
    patients = db.command("collStats", "patients")["count"] if "patients" in db.list_collection_names() else 0
    log(f"{label}: collStats count encounters={encounters}, patients={patients}")
    require((encounters, patients) == (expected_encounters, expected_patients), f"Count mismatch at {label}")


def load(step, expected_increment, expected_encounters, expected_patients):
    meta = root / "load" / f"SA_{step}.json"
    run("source/scripts/load_dataset.py", "--uri", uri, "--dataset", f"data/load_v2/{step}",
        "--env", "SA", "--meta-out", str(meta))
    info = json.loads(meta.read_text())
    require(info["encounters"]["docs"] == expected_increment, f"Unexpected {step} increment")
    check_counts(f"after {step}", expected_encounters, expected_patients)
    check_indexes(f"after {step}")


def bench(dataset, scenario, threads, rep):
    out = root / ("RQ1" if scenario == "TN1" else "RQ2")
    query = "Q1" if scenario == "TN1" else "INSERT"
    extra = ["--query", query] if scenario == "TN1" else ["--duration", "60"]
    tag = f"SA_{dataset}_{scenario}" + ("_Q1" if scenario == "TN1" else "") + f"_t{threads}_r{rep}"
    run("source/scripts/bench_v2.py", "--uri", uri, "--env", "SA", "--dataset", dataset,
        "--scenario", scenario, "--threads", str(threads), "--rep", str(rep),
        "--output-dir", str(out), *extra)
    info = json.loads((out / "meta" / f"{tag}.json").read_text())
    if info["client_bound"] or info["client_cpu_max"] >= 75:
        log(f"STOP_CPU {tag} client_cpu_max={info['client_cpu_max']} client_bound={info['client_bound']}")
        raise SystemExit(75)
    require((info["dataset"], info["scenario"], info["threads"], info["rep"]) ==
            (dataset, scenario, threads, rep), f"Metadata mismatch: {tag}")
    status = json.loads((out / "status" / f"{tag}_entry.json").read_text())
    latencies = []
    with (out / f"{tag}.csv").open(newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            require(row["success"] == "1" and not row["error_msg"] and row["query_id"] == query
                    and int(row["docs_returned"]) > 0, f"Invalid operation: {tag}: {row}")
            latency = float(row["latency_ms"])
            require(math.isfinite(latency) and latency >= 0, f"Invalid latency: {tag}")
            latencies.append(latency)
    count = len(latencies)
    require(count == info["n_success"] == info["n_requests"] and count > 0, f"CSV/metadata mismatch: {tag}")
    latencies.sort()
    position = (count - 1) * 0.95
    lower, upper = math.floor(position), math.ceil(position)
    p95 = latencies[lower] + (latencies[upper] - latencies[lower]) * (position - lower)
    require(round(p95, 3) == info["p95_ms"], f"p95 mismatch: {tag}")
    require(info["qps_or_inserts_s"] == round(count / info["elapsed_s"], 2), f"Rate mismatch: {tag}")
    if scenario == "TN1":
        require(count >= 2000 and info["elapsed_s"] >= 50, f"TN1 minimum duration or request count: {tag}")
        require(status["opcounters_delta"]["query"] >= count, f"Server query count mismatch: {tag}")
    else:
        require(info["elapsed_s"] >= 60, f"TN2-write duration: {tag}")
        require(status["opcounters_delta"]["insert"] == count, f"Server insert count mismatch: {tag}")
    log(f"Validated {tag}: {count} successful operations, elapsed={info['elapsed_s']}s")
    groups[scenario, dataset, threads].append(info)
    return count


def tn1(dataset):
    for threads in (1, 4, 8):
        for rep in (1, 2, 3):
            bench(dataset, "TN1", threads, rep)


def measure():
    wait_for(lambda: client.admin.command("ping")["ok"] == 1, "MongoDB ping")
    rs = client.admin.command("replSetInitiate", {"_id": "rs0", "members": [{"_id": 0, "host": "localhost:27017"}]})
    log(f"Replica set init: {rs}")
    wait_for(lambda: client.admin.command("hello")["isWritablePrimary"], "rs0 primary")
    initial_databases = client.list_database_names()
    log(f"Initial databases: {initial_databases}")
    require(set(initial_databases) <= {"admin", "config", "local"}, "Expected a fresh MongoDB instance")
    require("ehr" not in initial_databases, "ehr already exists")
    server = client.server_info()
    cache = client.admin.command("serverStatus")["wiredTiger"]["cache"]["maximum bytes configured"]
    log(f"MongoDB {server['version']} WiredTiger configured max bytes={cache}")
    require(server["version"].startswith("7.0.") and cache == 536870912, "Unexpected MongoDB or cache configuration")
    require(not db.list_collection_names(), "ehr was not empty before creating indexes")
    db.encounters.create_index([("PATIENT", 1), ("START", -1)])
    db.encounters.create_index([("START", 1)])
    db.encounters.create_index([("conditions.CODE", 1), ("START", 1)])
    check_indexes("before S1")
    check_counts("before S1", 0, 0)
    load("S1", 100000, 100000, 1822)
    log("Starting 100K pilot: 9 planned TN1 runs")
    tn1("D100K")
    log("PILOT_VALID: all 9 runs validated and CPU below stop threshold; using pilot as D100K TN1")
    load("S2", 400000, 500000, 9202)
    tn1("D500K")
    load("S3", 500000, 1000000, 18443)
    tn1("D1M")
    encounters = 1000000
    for rep in (1, 2, 3):
        check_counts(f"before TN2-write r{rep}", encounters, 18443)
        encounters += bench("D1M", "TN2-write", 4, rep)
        check_counts(f"after TN2-write r{rep}", encounters, 18443)
    check_counts("before S4", encounters, 18443)
    log(f"TN2-write added {encounters - 1000000} docs retained at D3M according to the guide's cumulative sequence")
    load("S4", 2000000, encounters + 2000000, 55448)
    tn1("D3M")


def summarize():
    require(len(groups) == 13 and all(len(v) == 3 for v in groups.values()), "Incomplete run matrix")
    with (root / "SA_summary.csv").open("x", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["scenario", "dataset", "threads", "repetitions", "mean_p95_ms",
                         "mean_qps_or_inserts_s", "max_client_cpu_pct", "successful_operations"])
        for (scenario, dataset, threads), runs in groups.items():
            writer.writerow([scenario, dataset, threads, len(runs),
                             f"{statistics.mean(r['p95_ms'] for r in runs):.3f}",
                             f"{statistics.mean(r['qps_or_inserts_s'] for r in runs):.2f}",
                             max(r["client_cpu_max"] for r in runs), sum(r["n_success"] for r in runs)])
    log("COMPLETE: 36 TN1 and 3 TN2-write runs validated and summarized. TN1 rate uses benchmark metadata denominator including warm-up.")


with (root / "sys" / "SA_sar.log").open("x") as sar_log:
    sar = subprocess.Popen(["sar", "-u", "-r", "-d", "1"], stdout=sar_log, stderr=subprocess.STDOUT)
    try:
        measure()
        summarize()
    finally:
        sar.terminate()
        sar.wait()
        client.close()
