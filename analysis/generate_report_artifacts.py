#!/usr/bin/env python3
"""Aggregate clean single-host benchmark results and generate publication-ready figures (PNG + PDF)."""

import glob
import json
import os
import statistics
from collections import Counter
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-cache")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "results"
FIG_DIR = REPO / "report" / "figures"
OUT_JSON = REPO / "analysis" / "summary_tables.json"

FIG_DIR.mkdir(parents=True, exist_ok=True)

# Clean academic palette (IEEE-friendly, colorblind-safe)
C_SA = "#1f4e79"       # Navy blue
C_HASH = "#1b7f79"     # Teal
C_RANGE = "#c0392b"    # Crimson red
C_S1 = "#2c6e9b"       # Shard 1 blue
C_S2 = "#e08e45"       # Shard 2 amber
C_Q1 = "#1b7f79"       # Q1 teal
C_Q3 = "#c0392b"       # Q3 crimson
C_Q4 = "#2c6e9b"       # Q4 navy
C_GRAY = "#5d6d7e"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.edgecolor": "#444444",
    "axes.linewidth": 0.8,
    "grid.color": "#d5d8dc",
    "grid.linestyle": "--",
    "grid.linewidth": 0.6,
    "legend.frameon": True,
    "legend.facecolor": "white",
    "legend.edgecolor": "#cccccc",
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "pdf.fonttype": 42,
})


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_wt_stats(status_dir: Path, tag_prefix: str, reps: list[int], is_sharded: bool, n_success_total: int):
    total_pages_read = 0
    total_pages_req = 0
    for r in reps:
        if not is_sharded:
            cand = glob.glob(str(status_dir / f"{tag_prefix}_r{r}_*.json"))
            st = load_json(cand[0])
            total_pages_read += st["wt_cache_delta"].get("pages_read_into_cache", 0)
            total_pages_req += st["wt_cache_delta"].get("pages_requested", 0)
        else:
            s1 = load_json(status_dir / f"{tag_prefix}_r{r}_s1.json")
            s2 = load_json(status_dir / f"{tag_prefix}_r{r}_s2.json")
            total_pages_read += (
                s1["wt_cache_delta"].get("pages_read_into_cache", 0)
                + s2["wt_cache_delta"].get("pages_read_into_cache", 0)
            )
            total_pages_req += (
                s1["wt_cache_delta"].get("pages_requested", 0)
                + s2["wt_cache_delta"].get("pages_requested", 0)
            )
    hit_ratio = (1.0 - min(1.0, total_pages_read / max(1, total_pages_req))) * 100.0
    pages_per_req = total_pages_read / max(1, n_success_total)
    return round(hit_ratio, 2), round(pages_per_req, 2), round(total_pages_read / max(1, len(reps)))


def summarize_read_group(rq_dir: Path, tag_prefix: str, reps: list[int], is_sharded: bool):
    metas = [load_json(rq_dir / "meta" / f"{tag_prefix}_r{r}.json") for r in reps]
    p95s = [m["p95_ms"] for m in metas]
    p50s = [m["p50_ms"] for m in metas]
    qpss = [m["qps_or_inserts_s"] for m in metas]
    cli_nets = [m["net_kb_per_req"] for m in metas if m.get("net_kb_per_req") is not None]
    sh_nets = [m["shard_net_kb_per_req"] for m in metas if m.get("shard_net_kb_per_req") is not None]
    amps = [m["net_amp_ratio"] for m in metas if m.get("net_amp_ratio") is not None]
    cpus = [m["client_cpu_max"] for m in metas]
    n_tot = sum(m["n_success"] for m in metas)

    hit_ratio, pages_per_req, pages_mean = compute_wt_stats(
        rq_dir / "status", tag_prefix, reps, is_sharded, n_tot
    )
    return {
        "reps": len(metas),
        "p95_mean": round(statistics.mean(p95s), 2),
        "p95_std": round(statistics.stdev(p95s), 2) if len(p95s) > 1 else 0.0,
        "p50_mean": round(statistics.mean(p50s), 2),
        "qps_mean": round(statistics.mean(qpss), 1),
        "qps_std": round(statistics.stdev(qpss), 1) if len(qpss) > 1 else 0.0,
        "client_net_kb_mean": round(statistics.mean(cli_nets), 2) if cli_nets else None,
        "shard_net_kb_mean": round(statistics.mean(sh_nets), 2) if sh_nets else None,
        "net_amp_ratio_mean": round(statistics.mean(amps), 2) if amps else None,
        "client_cpu_max": round(max(cpus), 1),
        "pages_read_mean": pages_mean,
        "pages_read_per_req": pages_per_req,
        "wt_hit_ratio_mean": hit_ratio,
    }


def aggregate_all():
    summary = {"rq1": {}, "rq2": {}, "rq3": {}, "rq3_slope": {}, "meta_info": {}}

    hosts = Counter()
    for rq in ["RQ1", "RQ2", "RQ3"]:
        for p in sorted(glob.glob(str(RESULTS / rq / "meta" / "*.json"))):
            d = load_json(p)
            hosts[f"{d['env']}|{d['client_host']}|{d['mongo_version']}"] += 1
    summary["meta_info"]["hosts"] = dict(hosts)

    # --- RQ1 ---
    for ds in ["D100K", "D500K", "D1M", "D3M"]:
        summary["rq1"][ds] = {}
        for t in [1, 4, 8]:
            summary["rq1"][ds][str(t)] = {}
            for env in ["SA", "SH-hash"]:
                tag_prefix = f"{env}_{ds}_TN1_Q1_t{t}"
                summary["rq1"][ds][str(t)][env] = summarize_read_group(
                    RESULTS / "RQ1", tag_prefix, [1, 2, 3], is_sharded=(env != "SA")
                )

    # --- RQ2 ---
    for env in ["SA", "SH-hash", "SH-range"]:
        metas = [
            load_json(RESULTS / "RQ2" / "meta" / f"{env}_D1M_TN2-write_t4_r{r}.json")
            for r in [1, 2, 3]
        ]
        p95s = [m["p95_ms"] for m in metas]
        rates = [m["qps_or_inserts_s"] for m in metas]
        entry = {
            "inserts_s_mean": round(statistics.mean(rates), 1),
            "inserts_s_std": round(statistics.stdev(rates), 1),
            "p95_mean": round(statistics.mean(p95s), 2),
            "p95_std": round(statistics.stdev(p95s), 2),
            "client_cpu_max": round(max(m["client_cpu_max"] for m in metas), 1),
        }
        dist = load_json(RESULTS / "RQ2" / "dist" / f"{env}_D1M_dist.json")
        if env == "SA":
            sn = dist["shards"]["single_node"]
            entry["data_pct"] = [100.0, 0.0]
            entry["data_mb"] = [round(sn["size_mb"], 2), 0.0]
            entry["storage_mb"] = [round(sn["storage_mb"], 2), 0.0]
            entry["index_mb"] = [round(sn["index_mb"], 2), 0.0]
            entry["write_pct"] = [100.0, 0.0]
        else:
            s1_d = dist["shards"]["shard1RS"]
            s2_d = dist["shards"]["shard2RS"]
            entry["data_pct"] = [round(s1_d["size_pct"], 2), round(s2_d["size_pct"], 2)]
            entry["data_mb"] = [round(s1_d["size_mb"], 2), round(s2_d["size_mb"], 2)]
            entry["data_count"] = [s1_d["count"], s2_d["count"]]
            entry["storage_mb"] = [round(s1_d["storage_mb"], 2), round(s2_d["storage_mb"], 2)]
            entry["index_mb"] = [round(s1_d["index_mb"], 2), round(s2_d["index_mb"], 2)]

            post_p = RESULTS / "RQ2" / "dist" / f"{env}_D1M_dist_post_compact.json"
            if post_p.exists():
                pdist = load_json(post_p)
                ps1, ps2 = pdist["shards"]["shard1RS"], pdist["shards"]["shard2RS"]
                entry["post_compact_storage_mb"] = [round(ps1["storage_mb"], 2), round(ps2["storage_mb"], 2)]
                entry["post_compact_index_mb"] = [round(ps1["index_mb"], 2), round(ps2["index_mb"], 2)]

            p1s, p2s = [], []
            for r in [1, 2, 3]:
                s1 = load_json(RESULTS / "RQ2" / "status" / f"{env}_D1M_TN2-write_t4_r{r}_s1.json")
                s2 = load_json(RESULTS / "RQ2" / "status" / f"{env}_D1M_TN2-write_t4_r{r}_s2.json")
                i1, i2 = s1["opcounters_delta"]["insert"], s2["opcounters_delta"]["insert"]
                p1s.append(100.0 * i1 / (i1 + i2))
                p2s.append(100.0 * i2 / (i1 + i2))
            entry["write_pct"] = [round(statistics.mean(p1s), 2), round(statistics.mean(p2s), 2)]
        summary["rq2"][env] = entry

    # --- RQ3 (D1M main comparison, complete Q1/Q3/Q4 for both SH-hash & SH-range) ---
    for env in ["SH-hash", "SH-range"]:
        summary["rq3"][env] = {}
        for q in ["Q1", "Q3", "Q4"]:
            ex_files = sorted(glob.glob(str(RESULTS / "RQ3" / "explain" / f"{env}_D1M_{q}_*.json")))
            shards_c = Counter()
            merge_c = Counter()
            stage_c = Counter()
            for ef in ex_files:
                ed = load_json(ef)
                st = ed.get("shards_targeted")
                n_sh = len(st) if isinstance(st, list) else st
                shards_c[n_sh] += 1
                merge_c[ed.get("merge_type")] += 1
                stage_c[ed.get("winning_stage")] += 1

            info = {
                "explain_samples": len(ex_files),
                "shards_targeted": dict(shards_c),
                "merge_type": dict(merge_c),
                "winning_stage": dict(stage_c),
            }
            if q == "Q1" and env == "SH-hash":
                perf = summary["rq1"]["D1M"]["1"]["SH-hash"]
            else:
                perf = summarize_read_group(
                    RESULTS / "RQ3", f"{env}_D1M_TN3-read_{q}_t1", [1, 2, 3], is_sharded=True
                )
            info.update(perf)
            summary["rq3"][env][q] = info

    # --- RQ3 slope 100K -> 3M on SH-hash (all 3 reps) ---
    for ds in ["D100K", "D500K", "D1M", "D3M"]:
        summary["rq3_slope"][ds] = {}
        summary["rq3_slope"][ds]["Q1"] = summary["rq1"][ds]["1"]["SH-hash"]
        for q in ["Q3", "Q4"]:
            summary["rq3_slope"][ds][q] = summarize_read_group(
                RESULTS / "RQ3", f"SH-hash_{ds}_TN3-read_{q}_t1", [1, 2, 3], is_sharded=True
            )

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Saved summary to {OUT_JSON}")
    return summary


def plot_fig4_1(summary):
    """Fig 4.1: p95 latency across 100K -> 3M for SA vs SH-hash (1, 4, 8 threads)."""
    datasets = ["D100K", "D500K", "D1M", "D3M"]
    labels = ["100K", "500K", "1M", "3M"]
    x = np.arange(len(datasets))

    fig, axes = plt.subplots(1, 3, figsize=(11.8, 4.1), sharex=True)
    threads = [1, 4, 8]
    titles = ["(a) 1 luồng đồng thời", "(b) 4 luồng đồng thời", "(c) 8 luồng đồng thời"]
    halo = dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.82)

    for ax, t, title in zip(axes, threads, titles):
        sa_y = [summary["rq1"][ds][str(t)]["SA"]["p95_mean"] for ds in datasets]
        sh_y = [summary["rq1"][ds][str(t)]["SH-hash"]["p95_mean"] for ds in datasets]

        ax.plot(x, sa_y, marker="o", linewidth=2.2, markersize=6.5, color=C_SA, label="SA (1 nút)")
        ax.plot(x, sh_y, marker="s", linewidth=2.2, markersize=6.5, color=C_HASH, label="SH-hash (2 shard)")
        ax.axvline(x=1, color=C_GRAY, linestyle=":", linewidth=1.1, alpha=0.8)

        ymax = max(max(sa_y), max(sh_y))
        ax.set_ylim(0, ymax * 1.28)
        ax.set_xlim(-0.28, 3.35)

        for xi, (yv_sa, yv_sh) in enumerate(zip(sa_y, sh_y)):
            if t == 1:
                sa_off = [(18, 0), (-8, 10), (-14, 10), (-8, 10)][xi]
                sh_off = [(0, 11), (14, -2), (10, -11), (4, -14)][xi]
            elif t == 4:
                sa_off = [(18, -3), (-8, 10), (-14, 10), (-8, 10)][xi]
                sh_off = [(0, 11), (10, -11), (10, -11), (4, -14)][xi]
            else:  # t == 8
                sa_off = [(-2, 12), (20, 8), (0, -15), (0, 11)][xi]
                sh_off = [(15, -10), (0, -13), (12, -11), (-22, 6)][xi]

            ax.annotate(f"{yv_sa:.1f}", (xi, yv_sa), textcoords="offset points", xytext=sa_off,
                        ha="center", va="center", fontsize=8.1, color=C_SA, fontweight="bold", bbox=halo)
            ax.annotate(f"{yv_sh:.1f}", (xi, yv_sh), textcoords="offset points", xytext=sh_off,
                        ha="center", va="center", fontsize=8.1, color=C_HASH, fontweight="bold", bbox=halo)

        if t == 8:
            ax.annotate("SA tràn cache\n(hit 80% vs 100%)", xy=(0.93, sa_y[1] + 0.5), xytext=(-0.22, ymax * 1.09),
                        fontsize=7.7, color=C_RANGE, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.24", fc="#fdf2e9", ec=C_RANGE, lw=0.8),
                        arrowprops=dict(arrowstyle="->", color=C_RANGE, lw=1.0, connectionstyle="arc3,rad=0.18"))

        ax.set_title(title, pad=8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_xlabel("Quy mô dữ liệu (mốc phân loại)")
        ax.grid(True, axis="y", alpha=0.6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[0].set_ylabel("Độ trễ p95 (ms)")
    handles, leg_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, leg_labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.05), frameon=True)
    fig.tight_layout()

    for ext in ["png", "pdf"]:
        fig.savefig(FIG_DIR / f"fig4_1_rq1_latency.{ext}")
    plt.close(fig)


def plot_fig4_2(summary):
    """Fig 4.2: (a) 8-thread QPS across 100K->3M; (b) QPS at D3M across 1/4/8 threads."""
    datasets = ["D100K", "D500K", "D1M", "D3M"]
    ds_labels = ["100K", "500K", "1M", "3M"]
    x1 = np.arange(len(datasets))
    w = 0.36

    sa_t8 = [summary["rq1"][ds]["8"]["SA"]["qps_mean"] for ds in datasets]
    sa_t8_std = [summary["rq1"][ds]["8"]["SA"]["qps_std"] for ds in datasets]
    sh_t8 = [summary["rq1"][ds]["8"]["SH-hash"]["qps_mean"] for ds in datasets]
    sh_t8_std = [summary["rq1"][ds]["8"]["SH-hash"]["qps_std"] for ds in datasets]

    threads = [1, 4, 8]
    x2 = np.arange(len(threads))
    sa_d3m = [summary["rq1"]["D3M"][str(t)]["SA"]["qps_mean"] for t in threads]
    sa_d3m_std = [summary["rq1"]["D3M"][str(t)]["SA"]["qps_std"] for t in threads]
    sh_d3m = [summary["rq1"]["D3M"][str(t)]["SH-hash"]["qps_mean"] for t in threads]
    sh_d3m_std = [summary["rq1"]["D3M"][str(t)]["SH-hash"]["qps_std"] for t in threads]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.2), gridspec_kw={"width_ratios": [1.22, 1.0]})

    # Panel (a): 8-thread QPS across all 4 scales
    b1 = ax1.bar(x1 - w / 2, sa_t8, yerr=sa_t8_std, capsize=3.5, width=w, color=C_SA,
                 label="SA (1 nút)", edgecolor="white", linewidth=0.7, error_kw={"elinewidth": 1.1, "ecolor": "#333333"})
    b2 = ax1.bar(x1 + w / 2, sh_t8, yerr=sh_t8_std, capsize=3.5, width=w, color=C_HASH,
                 label="SH-hash (2 shard)", edgecolor="white", linewidth=0.7, error_kw={"elinewidth": 1.1, "ecolor": "#333333"})

    for bar, s, col in zip(b1, sa_t8_std, [C_SA] * 4):
        h = bar.get_height()
        ax1.annotate(f"{h:,.0f}", (bar.get_x() + bar.get_width() / 2, h + s),
                     textcoords="offset points", xytext=(0, 3),
                     ha="center", va="bottom", fontsize=8.0, fontweight="bold", color=col)
    for idx, (bar, s) in enumerate(zip(b2, sh_t8_std)):
        h = bar.get_height()
        ax1.annotate(f"{h:,.0f}", (bar.get_x() + bar.get_width() / 2, h + s),
                     textcoords="offset points", xytext=(0, 3),
                     ha="center", va="bottom", fontsize=8.0, fontweight="bold", color=C_HASH)
        ratio = sh_t8[idx] / sa_t8[idx]
        badge_col = C_GRAY if ratio < 1.05 else C_RANGE
        badge_bg = "#f2f4f6" if ratio < 1.05 else "#fdf2e9"
        ax1.annotate(f"{ratio:.2f}x", xy=(x1[idx] + w / 2, h + s),
                     textcoords="offset points", xytext=(0, 18),
                     ha="center", va="bottom", fontsize=7.9, fontweight="bold",
                     color=badge_col, bbox=dict(boxstyle="round,pad=0.18", fc=badge_bg, ec=badge_col, lw=0.8))

    ax1.set_ylim(0, max(max(sa_t8), max(sh_t8)) * 1.28)
    ax1.set_xticks(x1)
    ax1.set_xticklabels(ds_labels)
    ax1.set_xlabel("Quy mô dữ liệu (mốc phân loại)")
    ax1.set_ylabel("Thông lượng đọc Q1 (QPS)")
    ax1.set_title("(a) Thông lượng ở 8 luồng qua 4 mốc quy mô", pad=10)
    ax1.grid(True, axis="y", alpha=0.6)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel (b): D3M QPS across 1/4/8 threads
    b3 = ax2.bar(x2 - w / 2, sa_d3m, yerr=sa_d3m_std, capsize=3.5, width=w, color=C_SA,
                 label="SA (1 nút)", edgecolor="white", linewidth=0.7, error_kw={"elinewidth": 1.1, "ecolor": "#333333"})
    b4 = ax2.bar(x2 + w / 2, sh_d3m, yerr=sh_d3m_std, capsize=3.5, width=w, color=C_HASH,
                 label="SH-hash (2 shard)", edgecolor="white", linewidth=0.7, error_kw={"elinewidth": 1.1, "ecolor": "#333333"})

    for bar, s in zip(b3, sa_d3m_std):
        h = bar.get_height()
        ax2.annotate(f"{h:.1f}", (bar.get_x() + bar.get_width() / 2, h + s),
                     textcoords="offset points", xytext=(0, 3),
                     ha="center", va="bottom", fontsize=8.2, fontweight="bold", color=C_SA)
    for idx, (bar, s) in enumerate(zip(b4, sh_d3m_std)):
        h = bar.get_height()
        ax2.annotate(f"{h:.1f}", (bar.get_x() + bar.get_width() / 2, h + s),
                     textcoords="offset points", xytext=(0, 3),
                     ha="center", va="bottom", fontsize=8.2, fontweight="bold", color=C_HASH)
        ratio = sh_d3m[idx] / sa_d3m[idx]
        ax2.annotate(f"{ratio:.2f}x", xy=(x2[idx] + w / 2, h + s),
                     textcoords="offset points", xytext=(0, 18),
                     ha="center", va="bottom", fontsize=8.0, fontweight="bold",
                     color=C_RANGE, bbox=dict(boxstyle="round,pad=0.18", fc="#fdf2e9", ec=C_RANGE, lw=0.8))

    ax2.set_ylim(0, max(sh_d3m) * 1.32)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(["1 luồng", "4 luồng", "8 luồng"])
    ax2.set_xlabel("Mức tải đồng thời tại D3M")
    ax2.set_ylabel("Thông lượng đọc Q1 (QPS)")
    ax2.set_title("(b) Thông lượng tại mốc lớn nhất D3M (3 triệu lượt khám)", pad=10)
    ax2.grid(True, axis="y", alpha=0.6)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    handles, leg_labels = ax1.get_legend_handles_labels()
    fig.legend(handles, leg_labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.05), frameon=True)
    fig.tight_layout()

    for ext in ["png", "pdf"]:
        fig.savefig(FIG_DIR / f"fig4_2_rq1_qps_d3m.{ext}")
    plt.close(fig)


def plot_fig4_3(summary):
    """Fig 4.3: RQ2 (a) Data & Write distribution S1/S2; (b) Write throughput (±std) & p95."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.2), gridspec_kw={"width_ratios": [1.1, 1.05]})

    cats = [
        "SH-range\nLượng ghi mới",
        "SH-range\nDữ liệu (MB)",
        "SH-hash\nLượng ghi mới",
        "SH-hash\nDữ liệu (MB)",
    ]
    s1_vals = [
        summary["rq2"]["SH-range"]["write_pct"][0],
        summary["rq2"]["SH-range"]["data_pct"][0],
        summary["rq2"]["SH-hash"]["write_pct"][0],
        summary["rq2"]["SH-hash"]["data_pct"][0],
    ]
    s2_vals = [
        summary["rq2"]["SH-range"]["write_pct"][1],
        summary["rq2"]["SH-range"]["data_pct"][1],
        summary["rq2"]["SH-hash"]["write_pct"][1],
        summary["rq2"]["SH-hash"]["data_pct"][1],
    ]
    y = np.arange(len(cats))
    ax1.barh(y, s1_vals, height=0.55, color=C_S1, label="Shard 1")
    ax1.barh(y, s2_vals, left=s1_vals, height=0.55, color=C_S2, label="Shard 2")
    ax1.axvline(50, color="#222222", linestyle="--", linewidth=1.0, alpha=0.75)

    for yi, (v1, v2) in enumerate(zip(s1_vals, s2_vals)):
        if v1 > 12:
            ax1.text(v1 / 2, yi, f"{v1:.1f}%", va="center", ha="center", color="white", fontweight="bold", fontsize=9)
        if v2 > 12:
            ax1.text(v1 + v2 / 2, yi, f"{v2:.1f}%", va="center", ha="center", color="white", fontweight="bold", fontsize=9)
        elif v2 == 0:
            ax1.text(98.5, yi, "Hotspot 100%!", va="center", ha="right", color="#fdebd0", fontweight="bold", fontsize=8.5)

    ax1.set_xlim(0, 100)
    ax1.set_yticks(y)
    ax1.set_yticklabels(cats)
    ax1.set_xlabel("Tỷ trọng trên từng shard (%)")
    ax1.set_title("(a) Phân bố dữ liệu & lượt ghi (mốc D1M)", pad=10)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    envs = ["SA\n(1 nút)", "SH-hash\n(băm PATIENT)", "SH-range\n(khoảng START)"]
    env_keys = ["SA", "SH-hash", "SH-range"]
    rates = [summary["rq2"][k]["inserts_s_mean"] for k in env_keys]
    stds = [summary["rq2"][k]["inserts_s_std"] for k in env_keys]
    p95s = [summary["rq2"][k]["p95_mean"] for k in env_keys]
    colors = [C_SA, C_HASH, C_RANGE]

    xb = np.arange(len(envs))
    bars = ax2.bar(xb, rates, yerr=stds, capsize=5, width=0.50, color=colors,
                   edgecolor="white", linewidth=0.8, error_kw={"elinewidth": 1.3, "ecolor": "#333333"})
    ymax = max(r + s for r, s in zip(rates, stds))
    ax2.set_ylim(0, ymax * 1.28)
    for bar, r, s, p in zip(bars, rates, stds, p95s):
        ax2.annotate(f"{r:,.1f} ± {s:.1f}\n(p95: {p:.2f} ms)",
                     (bar.get_x() + bar.get_width() / 2, r + s),
                     textcoords="offset points", xytext=(0, 6),
                     ha="center", va="bottom", fontsize=8.2, fontweight="bold", color="#222222")

    ax2.set_xticks(xb)
    ax2.set_xticklabels(envs)
    ax2.set_ylabel("Tốc độ ghi mới (inserts/s)")
    ax2.set_title("(b) Hiệu năng ghi 4 luồng (mốc D1M)", pad=10)
    ax2.grid(True, axis="y", alpha=0.6)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(FIG_DIR / f"fig4_3_rq2_write_dist.{ext}")
    plt.close(fig)


def plot_fig4_4(summary):
    """Fig 4.4: RQ3 (a) Direct D1M internal network comparison SH-hash vs SH-range (Q1, Q2, Q3);
    (b) Log-scale p95 slope 100K->3M on SH-hash (Q1, Q2, Q3).
    Note: Raw JSON keys Q1, Q3, Q4 map to report query labels Q1, Q2, Q3 respectively.
    """
    from matplotlib.ticker import FixedLocator, FixedFormatter

    datasets = ["D100K", "D500K", "D1M", "D3M"]
    ds_labels = ["100K", "500K", "1M", "3M"]
    halo = dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.82)

    # Panel (a) data: D1M internal shard <-> mongos network (KB/req) for Q1, Q2(raw Q3), Q3(raw Q4)
    raw_keys = ["Q1", "Q3", "Q4"]
    q_labels = ["Q1\n(1 bệnh nhân)", "Q2\n(Top-10 / quý)", "Q3\n(~834 docs / tháng)"]
    hash_net = [summary["rq3"]["SH-hash"][k]["shard_net_kb_mean"] for k in raw_keys]
    range_net = [summary["rq3"]["SH-range"][k]["shard_net_kb_mean"] for k in raw_keys]

    # Panel (b) data: 100K -> 3M p95 slope on SH-hash
    q1_p95 = [summary["rq3_slope"][ds]["Q1"]["p95_mean"] for ds in datasets]
    q2_p95 = [summary["rq3_slope"][ds]["Q3"]["p95_mean"] for ds in datasets]
    q3_p95 = [summary["rq3_slope"][ds]["Q4"]["p95_mean"] for ds in datasets]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 4.35), gridspec_kw={"width_ratios": [1.05, 1.1]})

    # --- Panel (a): Direct D1M SH-hash vs SH-range internal network ---
    xq = np.arange(len(raw_keys))
    w = 0.34
    b_hash = ax1.bar(xq - w / 2, hash_net, width=w, color=C_HASH, label="SH-hash (băm PATIENT)", edgecolor="white", lw=0.7)
    b_range = ax1.bar(xq + w / 2, range_net, width=w, color=C_RANGE, label="SH-range (khoảng START)", edgecolor="white", lw=0.7)

    ax1.set_yscale("log")
    ax1.set_ylim(0.8, 700)
    yticks_a = [1, 2, 5, 10, 20, 50, 100, 200, 500]
    ax1.yaxis.set_major_locator(FixedLocator(yticks_a))
    ax1.yaxis.set_major_formatter(FixedFormatter([str(v) for v in yticks_a]))
    ax1.yaxis.set_minor_locator(FixedLocator([]))

    for bar in b_hash:
        h = bar.get_height()
        ax1.annotate(f"{h:.2f}", (bar.get_x() + bar.get_width() / 2, h),
                     textcoords="offset points", xytext=(0, 3),
                     ha="center", va="bottom", fontsize=8.0, color=C_HASH, fontweight="bold")
    for bar in b_range:
        h = bar.get_height()
        ax1.annotate(f"{h:.2f}", (bar.get_x() + bar.get_width() / 2, h),
                     textcoords="offset points", xytext=(0, 3),
                     ha="center", va="bottom", fontsize=8.0, color=C_RANGE, fontweight="bold")

    # Clear ratio badges above each pair
    pair_notes = [
        (0, max(hash_net[0], range_net[0]), "SH-range +20%", C_GRAY, "#f2f4f6"),
        (1, max(hash_net[1], range_net[1]), "SH-hash gấp 10.3x!", C_RANGE, "#fdf2e9"),
        (2, max(hash_net[2], range_net[2]), "Tương đương (1.01x)", C_GRAY, "#f2f4f6"),
    ]
    for idx, top_v, txt, col, bg in pair_notes:
        ax1.annotate(txt, xy=(xq[idx], top_v), textcoords="offset points", xytext=(0, 18),
                     ha="center", va="bottom", fontsize=7.9, fontweight="bold", color=col,
                     bbox=dict(boxstyle="round,pad=0.22", fc=bg, ec=col, lw=0.8))

    ax1.set_xticks(xq)
    ax1.set_xticklabels(q_labels)
    ax1.set_ylabel("Mạng nội bộ shard <-> mongos (KB/req, log)")
    ax1.set_title("(a) Đối chiếu mạng nội bộ tại D1M (SH-hash vs SH-range)", pad=10)
    ax1.grid(True, axis="y", alpha=0.6)
    ax1.legend(loc="upper left", fontsize=8.1)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # --- Panel (b): Log-scale p95 slope 100K -> 3M on SH-hash ---
    x = np.arange(len(datasets))
    ax2.plot(x, q1_p95, marker="o", lw=2.2, ms=6.5, color=C_Q1, label="Q1 (1/2 shard, 1 bệnh nhân)")
    ax2.plot(x, q2_p95, marker="^", lw=2.2, ms=6.8, color=C_Q3, label="Q2 (2/2 shard, Top-10 / quý)")
    ax2.plot(x, q3_p95, marker="s", lw=2.2, ms=6.5, color=C_Q4, label="Q3 (2/2 shard, kết quả lớn)")

    ax2.set_yscale("log")
    ax2.set_ylim(0.8, 550)
    ax2.set_xlim(-0.28, 3.35)
    yticks_b = [1, 2, 5, 10, 20, 50, 100, 250]
    ax2.yaxis.set_major_locator(FixedLocator(yticks_b))
    ax2.yaxis.set_major_formatter(FixedFormatter([str(v) for v in yticks_b]))
    ax2.yaxis.set_minor_locator(FixedLocator([]))

    q2_offs = [(0, 11), (0, 11), (-10, 11), (-12, 11)]
    q3_offs = [(10, -11), (0, 11), (0, 11), (0, 11)]
    q1_offs = [(0, 11), (0, -12), (0, -12), (0, -13)]
    for xi in range(len(datasets)):
        ax2.annotate(f"{q2_p95[xi]:.1f}", (xi, q2_p95[xi]), textcoords="offset points", xytext=q2_offs[xi],
                     ha="center", va="center", fontsize=8.1, color=C_Q3, fontweight="bold", bbox=halo)
        ax2.annotate(f"{q3_p95[xi]:.1f}", (xi, q3_p95[xi]), textcoords="offset points", xytext=q3_offs[xi],
                     ha="center", va="center", fontsize=8.0, color=C_Q4, fontweight="bold", bbox=halo)
        ax2.annotate(f"{q1_p95[xi]:.1f}", (xi, q1_p95[xi]), textcoords="offset points", xytext=q1_offs[xi],
                     ha="center", va="center", fontsize=8.0, color=C_Q1, fontweight="bold", bbox=halo)

    ax2.set_xticks(x)
    ax2.set_xticklabels(ds_labels)
    ax2.set_xlabel("Quy mô dữ liệu (mốc phân loại)")
    ax2.set_ylabel("Độ trễ p95 (ms, thang logarit)")
    ax2.set_title("(b) Độ dốc độ trễ p95 trên SH-hash (100K -> 3M, 1 luồng)", pad=10)
    ax2.grid(True, axis="y", alpha=0.6)
    ax2.legend(loc="upper left", fontsize=8.1)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.tight_layout()
    for ext in ["png", "pdf"]:
        fig.savefig(FIG_DIR / f"fig4_4_rq3_slope_network.{ext}")
    plt.close(fig)


def main():
    summary = aggregate_all()
    plot_fig4_1(summary)
    plot_fig4_2(summary)
    plot_fig4_3(summary)
    plot_fig4_4(summary)
    print("Generated 4 figures (PNG + PDF) in", FIG_DIR)


if __name__ == "__main__":
    main()
