"""Live figures from results/live/<arm>/{controller_ticks,requests}.csv"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
BLUE, ORANGE, AQUA, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})
CAL = json.load(open(ROOT / "results/calibration.json")); CAP = CAL["sustainable_rps_per_instance"]
ARMS = [("A_reactive", "A  reactive (ASG target tracking)"), ("B_static", "B  hybrid-static"), ("C_ml", "C  hybrid-ML"), ("D_ml_spike", "D  hybrid-ML, x4 spike in hour 4")]
data = {}
for a, _ in ARMS:
    d = ROOT / "results/live" / a
    if (d / "requests.csv").exists(): data[a] = (pd.read_csv(d / "controller_ticks.csv"), pd.read_csv(d / "requests.csv"), json.load(open(d / "cloudwatch.json"))["interval_s"])
OUT = ROOT / "report/figures"
fig, axs = plt.subplots(2, 2, figsize=(9.2, 5.8), sharex=True, sharey=True)
for ax, (a, lab) in zip(axs.flat, ARMS):
    if a not in data: ax.set_visible(False); continue
    t, r, iv = data[a]; tick = iv / 60.0; x = t.minute / 60.0
    ax.plot(x, t.planned_rps, color=GRAY, lw=1, ls="--", label="Planned load")
    ax.plot(x, t.observed_rps, color=BLUE, lw=1.5, label="Observed load")
    ax.step(x, t.healthy * CAP if a != "A_reactive" else t.instances * CAP, where="post", color=ORANGE, lw=1.6, label="EC2 capacity (healthy x %d rps)" % CAP)
    lam = r[r.backend == "lambda"]; bins = np.floor(lam.t.values / tick).astype(int); cnt = np.bincount(bins, minlength=360)[:360] / tick
    ax.fill_between(np.arange(360) / 60.0, cnt, color=AQUA, alpha=0.55, step="post", label="Lambda-served rate")
    ax.set_title(lab, fontsize=9, loc="left")
for ax in axs[1]: ax.set_xlabel("Trace hour")
for ax in axs[:, 0]: ax.set_ylabel("Requests per second")
for ax in axs.flat: ax.grid(color="#e3e2de", lw=0.6)
h, l = axs[0, 0].get_legend_handles_labels(); fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=8)
fig.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(OUT / "live_timelines.png", bbox_inches="tight"); plt.close(fig)

fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.5)); cols = {"A_reactive": ORANGE, "B_static": GRAY, "C_ml": BLUE, "D_ml_spike": AQUA}; mk = {"A_reactive": "^", "B_static": "s", "C_ml": "o", "D_ml_spike": "D"}
for a, lab in ARMS:
    if a not in data: continue
    t, r, iv = data[a]; ok = r[r.status == 200]; hrs = np.floor(ok.t.values / iv).astype(int); xs, ys = [], []
    for h in range(6):
        v = ok.latency_ms.values[hrs == h]
        if len(v) > 20: xs.append(h + 0.5); ys.append(np.percentile(v, 95))
    axs[0].plot(xs, ys, color=cols[a], marker=mk[a], lw=1.5, ms=5, mec="white", label=lab.split("  ")[0] + " " + lab.split("  ")[1].split(" (")[0])
    axs[1].plot(t.minute / 60.0, t.cost, color=cols[a], lw=1.6)
    axs[1].text(6.02, t.cost.iloc[-1], a[0], color=cols[a], fontsize=9, va="center")
axs[0].axhline(CAL["p95_target_ms"], color=MUTED, lw=1, ls=":"); axs[0].text(0.02, CAL["p95_target_ms"] + 20, "p95 target %d ms" % CAL["p95_target_ms"], fontsize=7.5, color=MUTED)
axs[0].set_xlabel("Trace hour"); axs[0].set_ylabel("p95 latency per trace hour, ms"); axs[0].set_yscale("log"); axs[0].legend(frameon=False, fontsize=7.5)
axs[1].set_xlabel("Trace hour"); axs[1].set_ylabel("Cumulative running cost, USD"); axs[1].set_xlim(0, 6.4)
for ax in axs: ax.grid(color="#e3e2de", lw=0.6)
fig.tight_layout(); fig.savefig(OUT / "live_latency_cost.png", bbox_inches="tight"); plt.close(fig)
print("live figs ok", list(data))
