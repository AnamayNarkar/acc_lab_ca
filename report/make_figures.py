"""Simulation figures (static PNG, report/figures). Palette: validated default categorical (blue, orange, aqua) + neutrals; direct labels on marks."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
OUT = ROOT / "report/figures"; OUT.mkdir(parents=True, exist_ok=True)
BLUE, ORANGE, AQUA, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})
S = json.load(open(ROOT / "results/sim_results.json")); F = json.load(open(ROOT / "results/forecast_results.json"))
T = S["ec2"]["test"]

# ---- Fig: architecture
def box(ax, x, y, w, h, text, fc="#ffffff", ec=MUTED, fs=8.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else None)
def arrow(ax, a, b, txt=None, c=MUTED, ls="-"):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", color=c, lw=1.3, ls=ls))
    if txt: ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.12, txt, ha="center", fontsize=7.5, color=c)
fig, ax = plt.subplots(figsize=(8.4, 4.6)); ax.set_xlim(0, 10.4); ax.set_ylim(0, 6); ax.axis("off")
box(ax, 0.1, 2.3, 1.5, 1.0, "Clients\n(Locust,\nlaptop)", "#f3f2ef")
box(ax, 2.5, 2.1, 2.0, 1.4, "Application Load\nBalancer (ALB)\nweighted listener", "#e8f0fb", BLUE, bold=True)
box(ax, 6.1, 3.5, 2.7, 1.3, "tg-ec2: Auto Scaling Group\nt3.medium instances\nBASE (always on, cheap)", "#e8f0fb", BLUE)
box(ax, 6.1, 0.6, 2.7, 1.2, "tg-lambda: AWS Lambda\nOVERFLOW (instant,\npay per use)", "#fdeee7", ORANGE)
box(ax, 2.2, 4.9, 3.2, 0.9, "Controller (local Python)", "#e9f7f1", AQUA, bold=True)
box(ax, 0.1, 4.9, 1.7, 0.9, "LightGBM\nforecaster", "#e9f7f1", AQUA)
box(ax, 8.6, 4.9, 1.7, 0.9, "CloudWatch\nCostScale\ndashboard", "#f3f2ef")
arrow(ax, (1.6, 2.8), (2.5, 2.8), "HTTP")
arrow(ax, (4.5, 3.1), (6.2, 4.0), "weight w")
arrow(ax, (4.5, 2.5), (6.2, 1.4), "weight 1-w")
arrow(ax, (1.8, 5.35), (2.2, 5.35), None, AQUA)
ax.text(0.95, 4.65, "next-hour\nquantiles", fontsize=7.5, color=AQUA, ha="center", va="top")
arrow(ax, (3.2, 4.9), (3.2, 3.5), None, AQUA); ax.text(3.3, 4.2, "ALB weights\n(every minute)", fontsize=7.5, color=AQUA, va="center")
arrow(ax, (5.4, 5.1), (7.0, 4.8), None, AQUA); ax.text(5.95, 4.7, "set desired\ncapacity (hourly)", fontsize=7.5, color=AQUA, ha="right", va="top")
arrow(ax, (5.4, 5.5), (8.6, 5.5), None, MUTED, "--"); ax.text(7.0, 5.15, "", fontsize=7)
ax.text(7.55, 5.55, "metrics", fontsize=7.5, color=MUTED, ha="center", va="bottom")
ax.text(0.1, 0.2, "Overflow = load above base capacity. EC2 share w = min(1, base_rps / observed_rps). Region: ap-south-1.", fontsize=8, color=MUTED)
fig.savefig(OUT / "architecture.png", bbox_inches="tight"); plt.close(fig)

# ---- Fig: cost comparison
rows = [("All-Lambda", T["1_all_lambda"], GRAY), ("Reactive u=0.7", T["3_reactive_u0.7"], ORANGE), ("Reactive u=0.5", T["3_reactive_u0.5"], ORANGE),
        ("Reactive u=0.3", T["3_reactive_u0.3"], ORANGE), ("Seasonal u=0.7 (emul.)", T["4_seasonal_u0.7"], ORANGE),
        ("Hybrid-static", T["5_hybrid_static"], BLUE), ("Hybrid-rolling 6 h", T["6_hybrid_rolling"], BLUE), ("Hybrid-ML", T["7_hybrid_ML"], BLUE), ("Hybrid-oracle", T["8_hybrid_oracle"], BLUE)]
fig, ax = plt.subplots(figsize=(7.6, 3.9)); XMAX = 130000
for i, (n, v, col) in enumerate(rows[::-1]):
    cost = min(v["cost"], XMAX)
    ax.barh(i, cost, color=col, height=0.62, hatch="///" if v["unserved_pct"] > 0.01 else None, edgecolor="white", lw=0.6)
    lab = f"${v['cost'] / 1000:,.1f}k" + (f"   {v['unserved_pct']:.1f}% unserved" if v["unserved_pct"] > 0.01 else "")
    ax.text(cost + 1200, i, lab, va="center", fontsize=8)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows[::-1]]); ax.set_xlim(0, 175000)
ax.set_xlabel("Monthly cost, USD (test days 13-14 scaled to 30 days, EC2 base, measured capacity)")
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"${x / 1000:.0f}k")); ax.grid(axis="x", color="#e3e2de", lw=0.6); ax.set_axisbelow(True)
ax.text(0.99, 0.02, f"Peak-sized x1.2: ${T['2_peak_x1.2']['cost'] / 1000:,.0f}k (off scale), {T['2_peak_x1.2']['unserved_pct']:.2f}% unserved\nHatched = load dropped (no Lambda fallback)", transform=ax.transAxes, ha="right", fontsize=7.5, color=MUTED)
fig.savefig(OUT / "cost_comparison.png", bbox_inches="tight"); plt.close(fig)

# ---- Fig: cost vs unserved
fig, ax = plt.subplots(figsize=(6.6, 3.9))
for pre, lab, col, mk in (("3_reactive_u", "Reactive", ORANGE, "o"), ("4_seasonal_u", "Seasonal (emul.)", AQUA, "s")):
    pts = [(T[f"{pre}{u}"]["cost"], T[f"{pre}{u}"]["unserved_pct"], u) for u in (0.7, 0.5, 0.3, 0.2, 0.1)]
    ax.plot([p[0] / 1000 for p in pts], [p[1] for p in pts], color=col, marker=mk, ms=6, lw=1.6, mec="white", label=lab)
    for c_, u_, uu in pts: ax.annotate(f"u={uu}", (c_ / 1000, u_), textcoords="offset points", xytext=(4, 5), fontsize=7, color=MUTED)
for k, lab in (("5_hybrid_static", "Hybrid-static"), ("6_hybrid_rolling", "Hybrid-rolling"), ("7_hybrid_ML", "Hybrid-ML"), ("8_hybrid_oracle", "Oracle")):
    ax.scatter(T[k]["cost"] / 1000, 0, color=BLUE, s=42, zorder=5, edgecolor="white")
ax.annotate("Hybrids: 0% unserved\n$30-34k", (32, 0), xytext=(46, 1.2), fontsize=8, color=BLUE, arrowprops=dict(arrowstyle="-", color=BLUE, lw=0.8))
ax.set_xscale("log"); ax.set_xlim(25, 800); ax.set_xticks([30, 50, 100, 200, 400, 800]); ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"${x:.0f}k")); ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax.set_ylim(-0.5, 10); ax.set_xlabel("Monthly cost, USD thousands (log scale)"); ax.set_ylabel("Unserved load, % of requests")
ax.grid(color="#e3e2de", lw=0.6); ax.set_axisbelow(True); ax.legend(frameon=False, loc="upper right", fontsize=8)
fig.savefig(OUT / "unserved_vs_cost.png", bbox_inches="tight"); plt.close(fig)

# ---- Fig: quantile coverage (test)
fig, ax = plt.subplots(figsize=(5.6, 3.8)); qs = [0.5, 0.7, 0.8, 0.9, 0.95, 0.99]
ax.plot([0.45, 1], [0.45, 1], color=GRAY, lw=1, ls="--"); ax.text(0.6, 0.55, "ideal", color=MUTED, fontsize=8, rotation=28)
for m, lab, col, mk in (("lightgbm", "LightGBM", BLUE, "o"), ("rolling6h", "Rolling 6 h quantile", ORANGE, "s"), ("persistence", "Persistence (last hour)", AQUA, "^")):
    ax.plot(qs, [F["accuracy"][m]["test"][str(q)]["coverage"] for q in qs], color=col, marker=mk, lw=1.6, ms=5, mec="white", label=lab)
ax.set_xlabel("Nominal quantile q"); ax.set_ylabel("Observed coverage (share of minutes <= forecast)"); ax.grid(color="#e3e2de", lw=0.6); ax.legend(frameon=False, fontsize=8, loc="upper left")
fig.savefig(OUT / "quantile_coverage.png", bbox_inches="tight"); plt.close(fig)

# ---- Fig: sensitivity
sens = S["sensitivity_test"]; names = ["cap_x0.5", "cap_x1.5", "lambda_price_x0.5", "lambda_price_x2", "ec2_savings_-30pct_hypothetical", "fargate_base"]
lab = ["Capacity/unit x0.5", "Capacity/unit x1.5", "Lambda price x0.5", "Lambda price x2", "EC2 -30% (hypothetical)", "Fargate base"]
base_ratio = T["6_hybrid_rolling"]["cost"] / T["1_all_lambda"]["cost"]
fig, ax = plt.subplots(figsize=(6.6, 3.5))
vals = [base_ratio] + [sens[n]["6_hybrid_rolling"]["cost"] / sens[n]["1_all_lambda"]["cost"] for n in names]
labs = ["Baseline"] + lab
for i, (v, l) in enumerate(zip(vals[::-1], labs[::-1])):
    ax.barh(i, v, color=BLUE if l != "Baseline" else GRAY, height=0.6); ax.text(v + 0.01, i, f"{v:.2f}", va="center", fontsize=8)
ax.axvline(1.0, color=ORANGE, lw=1.2); ax.text(1.01, len(labs) - 0.45, "all-Lambda = 1.0", color=ORANGE, fontsize=8)
ax.set_yticks(range(len(labs))); ax.set_yticklabels(labs[::-1]); ax.set_xlim(0, 1.25); ax.set_xlabel("Hybrid-rolling cost / all-Lambda cost (test)")
ax.grid(axis="x", color="#e3e2de", lw=0.6); ax.set_axisbelow(True)
fig.savefig(OUT / "sensitivity.png", bbox_inches="tight"); plt.close(fig)

# ---- Fig: spike
sp = F["spike_test_ec2"]; fig, axs = plt.subplots(1, 2, figsize=(7.8, 3.4))
mult = ["3", "4", "5"]; clean = F["decision_cost_test_ec2"]
for k, lab, col, mk in (("hybrid_ML", "Hybrid-ML", BLUE, "o"), ("hybrid_rolling", "Hybrid-rolling", AQUA, "s"), ("reactive_u0.7", "Reactive u=0.7", ORANGE, "^")):
    axs[0].plot([0] + [int(m) for m in mult], [S["ec2"]["test"]["7_hybrid_ML" if k == "hybrid_ML" else "6_hybrid_rolling" if k == "hybrid_rolling" else "3_reactive_u0.7"]["cost"] / 1000] + [sp[m][k]["cost"] / 1000 for m in mult], color=col, marker=mk, lw=1.6, mec="white", label=lab)
    axs[1].plot([0] + [int(m) for m in mult], [S["ec2"]["test"]["7_hybrid_ML" if k == "hybrid_ML" else "6_hybrid_rolling" if k == "hybrid_rolling" else "3_reactive_u0.7"]["unserved_pct"]] + [sp[m][k]["unserved_pct"] for m in mult], color=col, marker=mk, lw=1.6, mec="white")
axs[0].set_ylabel("Monthly cost, USD thousands"); axs[1].set_ylabel("Unserved load, %")
for a in axs: a.set_xlabel("Spike multiplier on one hour per app (0 = none)"); a.set_xticks([0, 3, 4, 5]); a.grid(color="#e3e2de", lw=0.6)
axs[0].legend(frameon=False, fontsize=8); fig.tight_layout(); fig.savefig(OUT / "spike.png", bbox_inches="tight"); plt.close(fig)

# ---- Fig: forecast vs actual (live app, test days)
from run_sim import *
conc, meta, heavy, _ = setup(); idx = np.load(ROOT / "data/processed/pop_idx.npy"); wl = json.load(open(ROOT / "results/live_workload.json"))
row = int(np.where(idx == wl["idx"])[0][0]); E = make_env(conc, meta, idx, "ec2")
ml = np.load(ROOT / "results/cache/ml_base_test.npy")[row]; ro = base_rolling(E, TEST)[row]; orc = base_oracle(E, TEST)[row]
x = E["c"][row, TEST].reshape(48, 60)
fig, ax = plt.subplots(figsize=(7.8, 3.5)); hrs = np.arange(48)
ax.fill_between(hrs, x.mean(1), color="#dfe9f7", step="mid", label="Actual hourly mean")
ax.step(hrs, orc, where="mid", color=GRAY, lw=1.2, ls="--", label="Oracle q* of the hour")
ax.step(hrs, ro, where="mid", color=ORANGE, lw=1.5, label="Rolling 6 h forecast"); ax.step(hrs, ml, where="mid", color=BLUE, lw=1.8, label="LightGBM forecast")
ax.set_xlabel("Hour of test period (days 13-14)"); ax.set_ylabel("Concurrency (trace units)"); ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper left")
ax.set_title(f"Live-demo function (index {wl['idx']}): base capacity per hour", fontsize=9, loc="left"); ax.grid(color="#e3e2de", lw=0.6)
fig.savefig(OUT / "forecast_vs_actual.png", bbox_inches="tight"); plt.close(fig)
print("figures ok", sorted(p.name for p in OUT.iterdir()))
