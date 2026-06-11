"""Generate figures for the graduation thesis from the real measurement log.

Reads logs/metrics.jsonl and produces PNG figures in thesis/figures/.
Also writes thesis/stats.json with per-link summary statistics that the
document builder embeds, so every reported number is traceable to the data.
"""

import json
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "thesis", "figures")
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 200,
})

# ASCII-only display labels (the source uses Turkish chars that some fonts drop)
DISP = {
    "karargah": "HQ",
    "iha1": "UAV-1",
    "iha2": "UAV-2",
    "tank1": "Tank-1",
}


def link_label(src, dst):
    return f"{DISP[src]} -> {DISP[dst]}"


def load():
    rows = []
    with open(os.path.join(ROOT, "logs", "metrics.jsonl")) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    rows = load()
    # group by directed link key (src,dst)
    links = {}
    for r in rows:
        key = (r["src"], r["dst"])
        links.setdefault(key, []).append(r)

    order = [
        ("karargah", "iha1"), ("karargah", "iha2"), ("karargah", "tank1"),
        ("iha1", "iha2"), ("tank1", "iha1"),
    ]
    order = [k for k in order if k in links]
    labels = [link_label(*k) for k in order]

    def series(key, field):
        return [r[field] for r in links[key] if r.get(field) is not None]

    def mean(key, field):
        v = series(key, field)
        return statistics.fmean(v) if v else float("nan")

    def std(key, field):
        v = series(key, field)
        return statistics.pstdev(v) if len(v) > 1 else 0.0

    # ---- stats.json (real numbers for the report) ----
    stats = {"n_cycles": max(len(v) for v in links.values()), "links": {}}
    for k in order:
        stats["links"][link_label(*k)] = {
            "samples": len(links[k]),
            "throughput_mean": round(mean(k, "throughput_mbps"), 2),
            "throughput_std": round(std(k, "throughput_mbps"), 2),
            "latency_mean": round(mean(k, "latency_ms"), 2),
            "latency_std": round(std(k, "latency_ms"), 2),
            "jitter_mean": round(mean(k, "jitter_ms"), 3),
            "loss_mean": round(mean(k, "loss_pct"), 2),
            "retransmits_mean": round(mean(k, "retransmits"), 1),
        }
    with open(os.path.join(ROOT, "thesis", "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    colors = plt.cm.tab10.colors

    # ---- Figure: topology diagram ----
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.axis("off")
    pos = {
        "karargah": (0.5, 0.85),
        "iha1": (0.15, 0.45),
        "iha2": (0.85, 0.45),
        "tank1": (0.5, 0.12),
    }
    ips = {"karargah": "172.30.0.10", "iha1": "172.30.0.11",
           "iha2": "172.30.0.12", "tank1": "172.30.0.13"}
    for k, (x, y) in pos.items():
        box = FancyBboxPatch((x - 0.13, y - 0.06), 0.26, 0.12,
                             boxstyle="round,pad=0.01", linewidth=1.4,
                             edgecolor="#1f3b57", facecolor="#dce6f1")
        ax.add_patch(box)
        ax.text(x, y + 0.015, DISP[k], ha="center", va="center",
                fontsize=11, fontweight="bold")
        ax.text(x, y - 0.032, ips[k], ha="center", va="center", fontsize=8)
    for (s, d) in order:
        x1, y1 = pos[s]
        x2, y2 = pos[d]
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                     arrowstyle="-|>", mutation_scale=12,
                     color="#888", linewidth=1.1,
                     shrinkA=22, shrinkB=22, alpha=0.8))
    ax.text(0.5, 0.99, "tactical_net  bridge  172.30.0.0/24",
            ha="center", va="top", fontsize=9, style="italic", color="#444")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.03)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "topology.png"), bbox_inches="tight")
    plt.close(fig)

    # ---- Figure: throughput time series ----
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    for i, k in enumerate(order):
        y = series(k, "throughput_mbps")
        ax.plot(range(1, len(y) + 1), y, marker="o", ms=3, lw=1.2,
                color=colors[i], label=link_label(*k))
    ax.set_xlabel("Measurement cycle")
    ax.set_ylabel("TCP throughput (Mbit/s)")
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "throughput_ts.png"), bbox_inches="tight")
    plt.close(fig)

    # ---- Figure: mean throughput bar ----
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    means = [mean(k, "throughput_mbps") for k in order]
    errs = [std(k, "throughput_mbps") for k in order]
    ax.bar(labels, means, yerr=errs, capsize=4,
           color=[colors[i] for i in range(len(order))])
    ax.set_ylabel("Mean TCP throughput (Mbit/s)")
    ax.tick_params(axis="x", labelrotation=20)
    for i, v in enumerate(means):
        ax.text(i, v + max(means) * 0.01, f"{v:.1f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "throughput_bar.png"), bbox_inches="tight")
    plt.close(fig)

    # ---- Figure: mean latency bar ----
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    means = [mean(k, "latency_ms") for k in order]
    errs = [std(k, "latency_ms") for k in order]
    ax.bar(labels, means, yerr=errs, capsize=4, color="#4c72b0")
    ax.set_ylabel("Mean RTT latency (ms)")
    ax.tick_params(axis="x", labelrotation=20)
    for i, v in enumerate(means):
        ax.text(i, v + max(means) * 0.01, f"{v:.1f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "latency_bar.png"), bbox_inches="tight")
    plt.close(fig)

    # ---- Figure: jitter & loss grouped ----
    fig, ax1 = plt.subplots(figsize=(6.6, 3.6))
    import numpy as np
    x = np.arange(len(order))
    w = 0.38
    jit = [mean(k, "jitter_ms") for k in order]
    los = [mean(k, "loss_pct") for k in order]
    ax1.bar(x - w / 2, jit, w, color="#55a868", label="Jitter (ms)")
    ax1.set_ylabel("Mean jitter (ms)", color="#3a7d4f")
    ax2 = ax1.twinx()
    ax2.bar(x + w / 2, los, w, color="#c44e52", label="Packet loss (%)")
    ax2.set_ylabel("Mean packet loss (%)", color="#9b3b3e")
    ax2.grid(False)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=20)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "jitter_loss_bar.png"), bbox_inches="tight")
    plt.close(fig)

    print("Figures written to", FIG)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
