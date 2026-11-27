#!/usr/bin/env python3
"""Chuẩn bị dữ liệu & tải công việc cho khung thực nghiệm v2 (EXPERIMENT_SPEC_v2.md).

Không sinh lại Synthea. Mọi đầu ra được suy ra từ các tập đã có trong data/.

Bốn lệnh con (chạy theo thứ tự d2m -> analyze -> workload -> loadorder):

  d2m        Tạo mốc trung gian D2M (D1M ⊂ D2M ⊂ D3M) = tiền tố danh sách bệnh nhân D3M
             đạt >= 2M encounters -> data/D2M/patient_ids.txt. Tăng độ phân giải đúng vùng
             1M -> 3M nơi tỷ lệ dữ liệu/cache vượt 1.

  analyze    Phân tích offline, sinh data/V2_ANALYSIS.json:
             - dung lượng BSON ước lượng theo từng mốc quy mô (D100K..D3M, D1M-heavy)
             - "khối lượng khóa" (bytes/khóa) cho PATIENT, ORGANIZATION, ENCOUNTERCLASS so với
               chunk 32 MB, cận dưới Imbalance trên 2 shard
               -> dự đoán trước số khóa không thể chia (jumbo) cho R2 (dự đoán đăng ký trước)
             - số tài liệu/byte mỗi cửa sổ Q3 (quý) và Q4S/Q4L (tháng)
             - hot set của Q1/Q2 khi chọn bệnh nhân đều trên TOÀN BỘ quần thể

  workload   Sinh data/<ds>/workload_v2.json (tham số Q1..Q4L, seed luồng yêu cầu,
             cửa sổ thời gian dùng CHUNG cho mọi env, cấu hình Zipf cho R2).

  loadorder  Sinh data/load_v2/<step>/{encounters,patients}.jsonl.gz:
             S1 = D100K, S2 = D500K\\D100K, S3 = D1M\\D500K, S4 = D2M\\D1M, S5 = D3M\\D2M,
             HEAVY = D1M-heavy.
             Encounters trong mỗi bước được SẮP XẾP THEO START (mô phỏng thứ tự ghi
             thời gian thực của EHR, phá vỡ locality "theo bệnh nhân" của file gốc).
             Nạp lần lượt S1..S5 tái tạo D100K -> D500K -> D1M -> D2M -> D3M (nạp tăng dần).

Ví dụ:
  python3 scripts/prepare_v2.py --data-root data d2m
  python3 scripts/prepare_v2.py --data-root data analyze
  python3 scripts/prepare_v2.py --data-root data workload
  python3 scripts/prepare_v2.py --data-root data loadorder --tmp-dir data/.tmp
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

SEED = 42
CHUNK_MB = 32
CHUNK_BYTES = CHUNK_MB * 1024 * 1024
TIERS = ["D100K", "D500K", "D1M", "D2M", "D3M"]  # D2M = mốc trung gian suy ra từ D3M (lệnh d2m)
Q4S_CODE = "44054006"   # Tiểu đường type 2  -> fan-out chọn lọc, kết quả rất nhỏ
Q4L_CODE = "314529007"  # Medication review due -> fan-out, kết quả lớn (hàng trăm-nghìn docs/tháng)
ZIPF_THETAS = [0.99, 1.2]
ZIPF_PERM_SEEDS = [1, 2, 3, 4, 5]
STEPS = [("S1", "D100K", None), ("S2", "D500K", "D100K"), ("S3", "D1M", "D500K"),
         ("S4", "D2M", "D1M"), ("S5", "D3M", "D2M")]


# --------------------------------------------------------------------------- utils
def bson_size(doc: dict[str, Any]) -> int:
    """Ước lượng kích thước BSON (START/STOP là datetime 8 byte)."""
    size = 5
    for k, v in doc.items():
        size += 2 + len(k.encode("utf-8"))
        if k in ("START", "STOP"):
            size += 8
        elif isinstance(v, str):
            size += 5 + len(v.encode("utf-8"))
        elif isinstance(v, bool):
            size += 1
        elif isinstance(v, (int, float)):
            size += 8
        elif isinstance(v, dict):
            size += bson_size(v)
        elif isinstance(v, list):
            arr = 5
            for i, item in enumerate(v):
                arr += 2 + len(str(i))
                if isinstance(item, dict):
                    arr += bson_size(item)
                elif isinstance(item, str):
                    arr += 5 + len(item.encode("utf-8"))
                else:
                    arr += 8
            size += arr
    return size


def read_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def iter_jsonl(path: Path) -> Iterator[str]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield line


def month_add(y: int, m: int, k: int) -> tuple[int, int]:
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1


def windows(max_start_iso: str) -> dict[str, Any]:
    """Cửa sổ thời gian cố định, dùng CHUNG cho mọi env và mọi dataset."""
    y, m = int(max_start_iso[:4]), int(max_start_iso[5:7])
    ay, am = y, m  # neo = đầu tháng chứa max_start (tháng cuối chưa trọn vẹn bị loại)
    sy, sm = month_add(ay, am, -36)
    q3 = []
    for i in range(12):
        a = month_add(sy, sm, 3 * i)
        b = month_add(sy, sm, 3 * i + 3)
        q3.append({"qStart": f"{a[0]:04d}-{a[1]:02d}-01T00:00:00Z", "qEnd": f"{b[0]:04d}-{b[1]:02d}-01T00:00:00Z"})
    q4 = []
    for i in range(36):
        a = month_add(sy, sm, i)
        b = month_add(sy, sm, i + 1)
        q4.append({"mStart": f"{a[0]:04d}-{a[1]:02d}-01T00:00:00Z", "mEnd": f"{b[0]:04d}-{b[1]:02d}-01T00:00:00Z"})
    d12 = month_add(ay, am, -12)
    return {
        "anchor": f"{ay:04d}-{am:02d}-01T00:00:00Z",
        "d12mAgo": f"{d12[0]:04d}-{d12[1]:02d}-01T00:00:00Z",
        "q3_windows": q3,
        "q4_windows": q4,
    }


def find_window(ts: str, wins: list[dict[str, str]], a: str, b: str) -> int:
    for i, w in enumerate(wins):
        if w[a] <= ts < w[b]:
            return i
    return -1


def pct(values: list[int], p: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


# --------------------------------------------------------------------------- analyze
class TierStats:
    def __init__(self, wins: dict[str, Any]) -> None:
        self.n = 0
        self.bytes = 0
        self.pat_bytes: dict[str, int] = defaultdict(int)
        self.org_bytes: dict[str, int] = defaultdict(int)
        self.cls_bytes: dict[str, int] = defaultdict(int)
        self.q3_docs = [0] * 12
        self.q3_bytes = [0] * 12
        self.q4s = [0] * 36
        self.q4l = [0] * 36
        self.wins = wins

    def add(self, d: dict[str, Any], size: int) -> None:
        self.n += 1
        self.bytes += size
        self.pat_bytes[d["PATIENT"]] += size
        self.org_bytes[d.get("ORGANIZATION", "")] += size
        self.cls_bytes[d.get("ENCOUNTERCLASS", "")] += size
        st = d["START"]
        if st >= self.wins["q3_windows"][0]["qStart"]:
            qi = find_window(st, self.wins["q3_windows"], "qStart", "qEnd")
            if qi >= 0:
                self.q3_docs[qi] += 1
                self.q3_bytes[qi] += size
            mi = find_window(st, self.wins["q4_windows"], "mStart", "mEnd")
            if mi >= 0:
                codes = {c.get("CODE") for c in d.get("conditions", [])}
                if Q4S_CODE in codes:
                    self.q4s[mi] += 1
                if Q4L_CODE in codes:
                    self.q4l[mi] += 1

    @staticmethod
    def min_imbalance_2shards(vals: list[int]) -> float:
        """Cận dưới Imbalance(%) đạt được trên 2 shard.

        Khóa có khối lượng > chunk là nguyên tử (không chia được); phần còn lại coi như
        chia được tùy ý. |S1-S2|_min = max(0, D_atomic - divisible), D_atomic là chênh lệch
        nhỏ nhất khi phân hoạch các khối nguyên tử (subset-sum theo MB).
        """
        total = sum(vals)
        atoms = [v for v in vals if v > CHUNK_BYTES]
        if not atoms or total == 0:
            return 0.0
        divisible = total - sum(atoms)
        mb = [max(1, round(a / 2**20)) for a in atoms]
        reach = 1
        for w in mb:
            reach |= reach << w
        s = sum(mb)
        best = min(abs(s - 2 * k) for k in range(s + 1) if (reach >> k) & 1)
        diff = max(0.0, best * 2**20 - divisible)
        return round(100 * diff / total, 2)

    @staticmethod
    def key_mass(m: dict[str, int]) -> dict[str, Any]:
        vals = list(m.values())
        over = [v for v in vals if v > CHUNK_BYTES]
        return {
            "min_imbalance_pct_2shards": TierStats.min_imbalance_2shards(vals),
            "distinct_keys": len(vals),
            "max_mb": round(max(vals) / 2**20, 2) if vals else 0,
            "p99_mb": round(pct(vals, 99) / 2**20, 3),
            "keys_over_chunk": len(over),
            "mass_over_chunk_pct": round(100 * sum(over) / max(1, sum(vals)), 2),
            "top1_pct": round(100 * max(vals) / max(1, sum(vals)), 2) if vals else 0,
        }

    def summary(self, hot: dict[str, Any]) -> dict[str, Any]:
        return {
            "encounters": self.n,
            "bson_mb": round(self.bytes / 2**20, 1),
            "avg_bson_bytes": round(self.bytes / max(1, self.n), 1),
            "chunks_at_32mb": round(self.bytes / CHUNK_BYTES, 1),
            "key_mass_PATIENT": self.key_mass(self.pat_bytes),
            "key_mass_ORGANIZATION": self.key_mass(self.org_bytes),
            "key_mass_ENCOUNTERCLASS": self.key_mass(self.cls_bytes),
            "q3_docs_per_quarter": {"min": min(self.q3_docs), "max": max(self.q3_docs),
                                     "mean": round(sum(self.q3_docs) / 12, 1)},
            "q3_mb_per_quarter_max": round(max(self.q3_bytes) / 2**20, 1),
            "q3_quarter_exceeds_one_chunk": max(self.q3_bytes) > CHUNK_BYTES,
            "q4s_docs_per_month": {"min": min(self.q4s), "max": max(self.q4s), "mean": round(sum(self.q4s) / 36, 1)},
            "q4l_docs_per_month": {"min": min(self.q4l), "max": max(self.q4l), "mean": round(sum(self.q4l) / 36, 1)},
            **hot,
        }


def hot_set(per_patient: dict[str, list[tuple[str, int]]], d12: str) -> dict[str, Any]:
    """Byte bị chạm khi MỌI bệnh nhân đều được truy vấn ít nhất một lần."""
    q1 = q2 = 0
    for lst in per_patient.values():
        lst.sort(reverse=True)
        q1 += sum(s for _, s in lst[:10])
        q2 += sum(s for t, s in lst if t >= d12)
    return {"q1_hotset_mb_all_patients": round(q1 / 2**20, 1), "q2_hotset_mb_all_patients": round(q2 / 2**20, 1)}


def cmd_analyze(root: Path) -> None:
    summary = json.loads((root / "DATASET_SUMMARY.json").read_text())
    wins = windows(summary["D3M"]["max_start"])
    tier_sets = {t: read_ids(root / t / "patient_ids.txt") for t in TIERS[:-1]}
    stats = {t: TierStats(wins) for t in TIERS}
    per_patient: dict[str, list[tuple[str, int]]] = defaultdict(list)
    tier_of: dict[str, int] = {}

    t0 = time.time()
    for i, line in enumerate(iter_jsonl(root / "D3M" / "encounters.jsonl.gz")):
        d = json.loads(line)
        pid = d["PATIENT"]
        ti = tier_of.get(pid)
        if ti is None:
            ti = next((k for k, t in enumerate(TIERS[:-1]) if pid in tier_sets[t]), len(TIERS) - 1)
            tier_of[pid] = ti
        size = bson_size(d)
        for t in TIERS[ti:]:
            stats[t].add(d, size)
        per_patient[pid].append((d["START"], size))
        if i % 500_000 == 0:
            print(f"  D3M pass: {i:,} docs ({time.time() - t0:.0f}s)", flush=True)

    out: dict[str, Any] = {"chunk_mb": CHUNK_MB, "windows": wins, "q4s_code": Q4S_CODE, "q4l_code": Q4L_CODE, "tiers": {}}
    for k, t in enumerate(TIERS):
        sub = {p: lst for p, lst in per_patient.items() if tier_of[p] <= k}
        out["tiers"][t] = stats[t].summary(hot_set(sub, wins["d12mAgo"]))
        print(f"  {t}: done", flush=True)
    del per_patient

    hs = TierStats(wins)
    hp: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for line in iter_jsonl(root / "D1M-heavy" / "encounters.jsonl.gz"):
        d = json.loads(line)
        s = bson_size(d)
        hs.add(d, s)
        hp[d["PATIENT"]].append((d["START"], s))
    out["tiers"]["D1M-heavy"] = hs.summary(hot_set(hp, wins["d12mAgo"]))

    dst = root / "V2_ANALYSIS.json"
    dst.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Wrote {dst} in {time.time() - t0:.0f}s")


# --------------------------------------------------------------------------- workload
def cmd_workload(root: Path) -> None:
    summary = json.loads((root / "DATASET_SUMMARY.json").read_text())
    wins = windows(summary["D3M"]["max_start"])
    for ds in TIERS + ["D1M-heavy"]:
        ids = sorted(read_ids(root / ds / "patient_ids.txt"))
        rng = random.Random(SEED)
        samples = []
        for s in range(5):
            samples.append({
                "sample": s + 1,
                "pid": ids[rng.randrange(len(ids))],
                "qStart": wins["q3_windows"][2 * s + 1]["qStart"],
                "qEnd": wins["q3_windows"][2 * s + 1]["qEnd"],
                "mStart": wins["q4_windows"][6 * s + 3]["mStart"],
                "mEnd": wins["q4_windows"][6 * s + 3]["mEnd"],
            })
        wl = {
            "version": 2,
            "dataset": ds,
            "num_patients": len(ids),
            "pid_sampling": {
                "rule": "uniform_with_replacement_over_all_patient_ids",
                "patient_ids_file": "patient_ids.txt (sorted lexicographically before sampling)",
                "stream_seed": "SEED*1000 + rep  (rep = 1..R); same stream for every env",
                "base_seed": SEED,
            },
            "d12mAgo": wins["d12mAgo"],
            "q3_windows": wins["q3_windows"],
            "q4_windows": wins["q4_windows"],
            "window_selection": "round-robin over ALL windows, identical for SA/B1/SH-hash/SH-range; "
                                 "number of targeted shards is recorded as an OUTCOME, never used as a filter",
            "q4s_code": Q4S_CODE,
            "q4l_code": Q4L_CODE,
            "zipf": {"thetas": ZIPF_THETAS, "rank_to_patient_permutation_seeds": ZIPF_PERM_SEEDS},
            "explain_samples": samples,
        }
        (root / ds / "workload_v2.json").write_text(json.dumps(wl, indent=2))
        print(f"Wrote {root / ds / 'workload_v2.json'}")


# --------------------------------------------------------------------------- loadorder
def external_sort_by_start(src_lines: Iterator[str], dst: Path, tmp_dir: Path) -> int:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    raw = tmp_dir / (dst.parent.name + "_keyed.tsv")
    n = 0
    with raw.open("w", encoding="utf-8") as f:
        for line in src_lines:
            d = json.loads(line)
            f.write(d["START"] + "\t" + line.rstrip("\n") + "\n")
            n += 1
    env = dict(os.environ, LC_ALL="C")
    sorted_path = tmp_dir / (dst.parent.name + "_sorted.tsv")
    subprocess.run(["sort", "-s", "-t", "\t", "-k1,1", "-S", "1G", "-T", str(tmp_dir),
                    "-o", str(sorted_path), str(raw)], check=True, env=env)
    raw.unlink()
    with sorted_path.open(encoding="utf-8") as fin, gzip.open(dst, "wt", encoding="utf-8", compresslevel=6) as fout:
        for line in fin:
            fout.write(line.split("\t", 1)[1])
    sorted_path.unlink()
    return n


def cmd_d2m(root: Path, target: int = 2_000_000) -> None:
    """Tạo mốc D2M lồng nhau: tiền tố nhỏ nhất của danh sách bệnh nhân D3M đạt >= 2M encounters."""
    counts: dict[str, int] = defaultdict(int)
    for line in iter_jsonl(root / "D3M" / "encounters.jsonl.gz"):
        counts[json.loads(line)["PATIENT"]] += 1
    ids = [l.strip() for l in (root / "D3M" / "patient_ids.txt").open(encoding="utf-8") if l.strip()]
    d1m = read_ids(root / "D1M" / "patient_ids.txt")
    assert set(ids[:len(d1m)]) == d1m, "D1M must be a prefix of D3M patient_ids.txt"
    acc, k = 0, 0
    while acc < target:
        acc += counts[ids[k]]
        k += 1
    out = root / "D2M"
    out.mkdir(exist_ok=True)
    (out / "patient_ids.txt").write_text("\n".join(ids[:k]) + "\n", encoding="utf-8")
    (out / "README.txt").write_text(
        "D2M là mốc trung gian (D1M ⊂ D2M ⊂ D3M) được suy ra từ D3M: "
        f"{k:,} bệnh nhân đầu tiên của D3M/patient_ids.txt, {acc:,} encounters.\n"
        "Không có file encounters riêng: dùng data/load_v2/S1..S4 để nạp.\n", encoding="utf-8")
    print(f"D2M: {k:,} patients, {acc:,} encounters")


def cmd_loadorder(root: Path, tmp_dir: Path) -> None:
    out_root = root / "load_v2"
    manifest: dict[str, Any] = {"order": "encounters sorted by START within each step",
                                "source": "D3M (all smaller tiers are patient-prefix subsets)", "steps": []}
    cumulative = 0
    for step, ds, prev in STEPS:
        keep = read_ids(root / ds / "patient_ids.txt")
        if prev:
            keep -= read_ids(root / prev / "patient_ids.txt")
        d = out_root / step
        d.mkdir(parents=True, exist_ok=True)
        enc = (l for l in iter_jsonl(root / "D3M" / "encounters.jsonl.gz") if json.loads(l)["PATIENT"] in keep)
        t0 = time.time()
        n = external_sort_by_start(enc, d / "encounters.jsonl.gz", tmp_dir)
        cumulative += n
        np_ = 0
        with gzip.open(d / "patients.jsonl.gz", "wt", encoding="utf-8") as fp:
            for l in iter_jsonl(root / "D3M" / "patients.jsonl.gz"):
                if json.loads(l)["_id"] in keep:
                    fp.write(l if l.endswith("\n") else l + "\n")
                    np_ += 1
        manifest["steps"].append({"step": step, "cumulative_dataset": ds, "new_patients": np_,
                                  "new_encounters": n, "cumulative_encounters": cumulative})
        print(f"  {step} ({ds} minus {prev}): {np_:,} patients, {n:,} encounters, cumulative {cumulative:,} "
              f"({time.time() - t0:.0f}s)", flush=True)

    d = out_root / "HEAVY"
    d.mkdir(parents=True, exist_ok=True)
    n = external_sort_by_start(iter_jsonl(root / "D1M-heavy" / "encounters.jsonl.gz"), d / "encounters.jsonl.gz", tmp_dir)
    shutil.copyfile(root / "D1M-heavy" / "patients.jsonl.gz", d / "patients.jsonl.gz")
    manifest["steps"].append({"step": "HEAVY", "cumulative_dataset": "D1M-heavy", "new_encounters": n})
    (out_root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"Wrote {out_root}/MANIFEST.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", type=Path, default=Path("data"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("d2m")
    sub.add_parser("analyze")
    sub.add_parser("workload")
    lo = sub.add_parser("loadorder")
    lo.add_argument("--tmp-dir", type=Path, default=Path("data/.tmp"))
    args = ap.parse_args()
    if args.cmd == "d2m":
        cmd_d2m(args.data_root)
    elif args.cmd == "analyze":
        cmd_analyze(args.data_root)
    elif args.cmd == "workload":
        cmd_workload(args.data_root)
    else:
        cmd_loadorder(args.data_root, args.tmp_dir)


if __name__ == "__main__":
    sys.exit(main())
