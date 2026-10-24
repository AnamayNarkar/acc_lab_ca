"""Analyse live arms -> results/live_results.json, including a simulator replay of each arm (sim-to-real gap)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
import numpy as np, pandas as pd
EC2_H, GBS, REQ, LGB = 0.0448, 1.66667e-5, 2e-7, 1769 / 1024.0
cal = json.load(open(ROOT / "results/calibration.json")); CAP = cal["sustainable_rps_per_instance"]; SVC = cal["service_ms"] / 1000.0
PER_REQ = SVC * LGB * GBS + REQ
TARGET_P95 = cal["p95_target_ms"]
def ccf_w(util): return 0.74 + util * (3.5 - 0.74)

res = {}
for arm in ("A_reactive", "B_static", "C_ml", "D_ml_spike"):
    d = ROOT / "results/live" / arm
    if not (d / "requests.csv").exists(): continue
    r = pd.read_csv(d / "requests.csv"); t = pd.read_csv(d / "controller_ticks.csv"); cwj = json.load(open(d / "cloudwatch.json"))
    interval = cwj["interval_s"]; tick_s = interval / 60.0; dur_s = interval * 6
    ok = r[r.status == 200]; out = {"requests": int(len(r)), "errors": int((r.status != 200).sum()), "error_rate": float((r.status != 200).mean()),
                                    "lambda_share": float((ok.backend == "lambda").mean()), "duration_s": dur_s, "interval_s": interval}
    out["latency_ms"] = {"all": {f"p{q}": float(np.percentile(ok.latency_ms, q)) for q in (50, 95, 99)}}
    for b in ("ec2", "lambda"):
        x = ok[ok.backend == b].latency_ms
        out["latency_ms"][b] = {"n": int(len(x)), **({f"p{q}": float(np.percentile(x, q)) for q in (50, 95, 99)} if len(x) else {})}
    out["slo_violation_share"] = float((ok.latency_ms > TARGET_P95).mean() + out["error_rate"])
    # cost: controller ledger and CloudWatch-based
    inst_s = float((t.instances * tick_s).sum()); out["instance_seconds"] = inst_s; out["instance_hours"] = inst_s / 3600
    out["ec2_cost"] = inst_s / 3600 * EC2_H
    lam_n = float(sum(v for _, v in cwj["lambda_invocations"])); lam_ms = float(sum(v for _, v in cwj["lambda_duration_sum_ms"]))
    out["lambda_invocations_cw"] = lam_n; out["lambda_requests_client"] = int((r.backend == "lambda").sum())
    out["lambda_cost_cw"] = lam_ms / 1000 * LGB * GBS + lam_n * REQ
    out["lambda_cost_client_est"] = out["lambda_requests_client"] * PER_REQ
    out["total_cost_cw"] = out["ec2_cost"] + out["lambda_cost_cw"]; out["controller_ledger_cost"] = float(t.cost.iloc[-1])
    out["mean_ec2_cpu_pct"] = float(np.mean([v for _, v in cwj["ec2_cpu_avg"]])) if cwj["ec2_cpu_avg"] else None
    util = (out["mean_ec2_cpu_pct"] or 0) / 100
    out["energy_wh_est"] = {"ec2": inst_s / 3600 * 2 * ccf_w(util), "lambda": lam_ms / 1000 * LGB * (1024 / 1792.0) / 3600 * ccf_w(0.5)}
    out["energy_wh_est"]["total"] = sum(out["energy_wh_est"].values())
    # cost per served request
    out["cost_per_1k_requests"] = out["total_cost_cw"] / max(len(ok), 1) * 1000
    # ---- simulator replay of the same arm: same schedule + same decisions, ideal (instant) capacity, exact overflow
    plan = t.planned_rps.values                                  # req/s per tick (trace minute), spiked for D
    if arm == "A_reactive":
        cap_rps = t.instances.values * CAP                        # replay uses the instance counts the ASG actually had
    else:
        dec = json.load(open(d / "decisions.json")); n_h = np.array([x["desired"] for x in dec] + [dec[-1]["desired"]] * (6 - len(dec)))[:6]
        cap_rps = np.repeat(n_h * CAP, 60)[:len(plan)].astype(float)
    over = np.maximum(0, plan - cap_rps); served = np.minimum(plan, cap_rps)
    sim = {"ec2_cost": float((cap_rps / CAP).sum() * tick_s / 3600 * EC2_H), "lambda_requests": float(over.sum() * tick_s),
           "total_requests": float(plan.sum() * tick_s)}
    if arm == "A_reactive": sim["unserved_share"] = float(over.sum() / plan.sum()); sim["lambda_cost"] = 0.0; sim["lambda_share"] = 0.0
    else: sim["lambda_cost"] = sim["lambda_requests"] * PER_REQ; sim["lambda_share"] = sim["lambda_requests"] / sim["total_requests"]; sim["unserved_share"] = 0.0
    sim["total_cost"] = sim["ec2_cost"] + sim["lambda_cost"]
    out["sim_replay"] = sim
    out["gap"] = {"lambda_share_pts": 100 * (out["lambda_share"] - sim["lambda_share"]), "cost_pct": 100 * (out["total_cost_cw"] - sim["total_cost"]) / max(sim["total_cost"], 1e-9)}
    res[arm] = out
json.dump(res, open(ROOT / "results/live_results.json", "w"), indent=1)
for a, v in res.items():
    print(a, "reqs", v["requests"], "err %.2f%%" % (100 * v["error_rate"]), "lam %.1f%%" % (100 * v["lambda_share"]), "p95 %.0f" % v["latency_ms"]["all"]["p95"],
          "cost $%.3f (sim $%.3f)" % (v["total_cost_cw"], v["sim_replay"]["total_cost"]), "inst-h %.3f" % v["instance_hours"])
