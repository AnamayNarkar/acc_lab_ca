"""Text that depends on live results (abstract, section 8.8, conclusion). Numbers come from results/live_results.json."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "report/figures"
ARMS = [("A_reactive", "A reactive (ASG target tracking)"), ("B_static", "B hybrid-static"), ("C_ml", "C hybrid-ML"), ("D_ml_spike", "D hybrid-ML + x4 spike")]

def _k(x): return f"${x/1000:,.1f}k"

def abstract(DS, SIM, FC, CAL, LIVE, T, N_POP, CAPU):
    a1 = ("Cloud providers sell computation both as cheap, slow-to-provision capacity (virtual machines and containers) and as expensive, instant, pay-per-use functions. "
          "Plain reactive autoscaling follows load with a delay and, without a fallback, drops or delays the load that arrives while capacity catches up. "
          "CostScale combines the two: a base of always-on EC2 capacity sized from an hourly quantile forecast of load, with everything above the base sent to AWS Lambda through an Application Load Balancer with weighted target groups.")
    a2 = (f"The base size follows from the newsvendor problem: it is the q*-quantile of forecast load, with q* = 1 - f/L, where f is the container cost and L the Lambda cost of serving one unit of load for a minute. "
          f"A trace-driven simulation over {N_POP} heavy functions of the Azure Functions 2019 trace, priced with AWS ap-south-1 prices and the container capacity measured on AWS, finds that a hybrid with a rolling quantile base costs {_k(T['6_hybrid_rolling']['cost'])} per month against {_k(T['1_all_lambda']['cost'])} for all-Lambda and {_k(T['3_reactive_u0.7']['cost'])} for the cheapest reactive setting, which also drops {T['3_reactive_u0.7']['unserved_pct']:.1f}% of the load; the hybrids drop none. "
          f"A LightGBM quantile forecaster is {abs(FC['ml_vs_rolling_pct']):.2f}% {'cheaper' if FC['ml_vs_rolling_pct']<0 else 'more expensive'} than the rolling baseline on test, which is within noise, so most of the benefit comes from the newsvendor rule rather than from machine learning.")
    if LIVE:
        a3 = ("A live AWS deployment in ap-south-1 ran four time-compressed experiment arms against the same trace window and compared them with a simulator replay of each arm. " + _abs_live(LIVE) +
              " Energy is only an estimate; storage and networking are out of scope.")
    else: a3 = "[LIVE RESULTS PENDING]"
    return [a1, a2, a3]

def _abs_live(L):
    A, B, C, D = (L.get(k) for k in ("A_reactive", "B_static", "C_ml", "D_ml_spike"))
    if not (A and B and C and D): return ""
    return (f"Reactive scaling (arm A) had {100*A['error_rate']:.1f}% errors and a p95 latency of {A['latency_ms']['all']['p95']:.0f} ms, against {100*C['error_rate']:.1f}% errors and {C['latency_ms']['all']['p95']:.0f} ms for the ML hybrid (arm C), "
            f"at a measured cost of ${A['total_cost_cw']:.2f} against ${C['total_cost_cw']:.2f} for the same run length.")

def live_section(d, L, CAL, WL, R):
    if not L:
        d.para("[LIVE RESULTS PENDING]"); return
    interval = next(iter(L.values()))["interval_s"]
    d.para(f"Four arms were run one after another against the same trace window (function {WL['idx']}, scale factor {WL['scale_factor']:.2f}, peak {WL['live_peak_rps']:.0f} req/s) with the same seed, from a laptop in Mumbai to the load balancer in ap-south-1. One trace hour lasts {interval:.0f} s, so each arm is {6*interval/60:.1f} minutes. Arm A is ASG target tracking on CPU at 50% with all traffic to EC2. Arms B and C use the controller of Section 6 with the static and the LightGBM forecast; arm D is arm C with the load multiplied by 4 during the fourth trace hour, after the forecast for that hour had been made. Predictive scaling was skipped (Section 7.5).")
    rows = []
    for key, lab in ARMS:
        v = L.get(key)
        if not v: continue
        e, l = v["latency_ms"]["ec2"], v["latency_ms"]["lambda"]
        rows.append([lab, f"{v['requests']:,}", f"{100*v['error_rate']:.1f}%", f"{100*v['lambda_share']:.1f}%", f"{v['latency_ms']['all']['p50']:.0f}", f"{v['latency_ms']['all']['p95']:.0f}", f"{v['latency_ms']['all']['p99']:.0f}",
                     f"{100*v['slo_violation_share']:.1f}%"])
    d.table(["Arm", "Requests", "Errors", "Lambda share", "p50 ms", "p95 ms", "p99 ms", "Over 800 ms or failed"], rows, [4.6, 1.9, 1.6, 2.0, 1.3, 1.3, 1.3, 2.3], "Live results: latency, errors and routing", font=9)
    rows = []
    for key, lab in ARMS:
        v = L.get(key)
        if not v: continue
        e, l = v["latency_ms"]["ec2"], v["latency_ms"]["lambda"]
        rows.append([lab, f"{e.get('p50', float('nan')):.0f} / {e.get('p95', float('nan')):.0f}" if e["n"] else "-", f"{l.get('p50', float('nan')):.0f} / {l.get('p95', float('nan')):.0f}" if l["n"] else "-",
                     f"{v['instance_hours']:.3f}", f"${v['ec2_cost']:.3f}", f"${v['lambda_cost_cw']:.3f}", f"${v['total_cost_cw']:.3f}", f"{v['energy_wh_est']['total']:.0f}"])
    d.table(["Arm", "EC2 p50 / p95 ms", "Lambda p50 / p95 ms", "Instance-hours", "EC2 cost", "Lambda cost", "Total cost", "Energy Wh (est.)"], rows, [4.2, 2.2, 2.4, 1.8, 1.5, 1.6, 1.5, 1.8], "Live results: backend latency, resources, cost and energy estimate", font=9)
    d.para("Costs are computed from the instance-time recorded by the controller and from the CloudWatch Lambda duration and invocation counts at the Mumbai prices of Section 5.1; the load balancer, public addresses and CloudWatch are not included, because they are the same for every arm. Energy uses the estimate methodology of Section 8.6 with the measured mean CPU utilisation.")
    d.figure(FIG / "live_timelines.png", 15.5, "Live timelines: request rate, base capacity and EC2 share for each arm")
    d.figure(FIG / "live_latency_cost.png", 15.0, "Live p95 latency per window and cumulative cost for each arm")
    # sim replay table
    rows = []
    for key, lab in ARMS:
        v = L.get(key)
        if not v: continue
        s = v["sim_replay"]
        rows.append([lab, f"{100*v['lambda_share']:.1f}%", f"{100*s['lambda_share']:.1f}%", f"{v['gap']['lambda_share_pts']:+.1f}", f"${v['total_cost_cw']:.3f}", f"${s['total_cost']:.3f}", f"{v['gap']['cost_pct']:+.0f}%"])
    d.table(["Arm", "Lambda share live", "Lambda share replay", "Gap (points)", "Cost live", "Cost replay", "Cost gap"], rows, [4.6, 2.2, 2.4, 1.8, 1.6, 1.8, 1.6], "Reconciliation: live arms against a simulator replay of the same arm", font=9)
    A, B, C, D = (L.get(k) for k in ("A_reactive", "B_static", "C_ml", "D_ml_spike"))
    out = []
    if A and C:
        out.append(f"**Reactive against hybrid.** Arm A, the reactive baseline, had {100*A['error_rate']:.1f}% failed requests and a p99 of {A['latency_ms']['all']['p99']:.0f} ms; arm C had {100*C['error_rate']:.1f}% failed and a p99 of {C['latency_ms']['all']['p99']:.0f} ms. Arm A used {A['instance_hours']:.3f} instance-hours and cost ${A['total_cost_cw']:.3f}; arm C used {C['instance_hours']:.3f} instance-hours and {100*C['lambda_share']:.1f}% of requests went to Lambda, for a total of ${C['total_cost_cw']:.3f}.")
    if B and C:
        out.append(f"**Static against ML.** Arm B cost ${B['total_cost_cw']:.3f} and arm C ${C['total_cost_cw']:.3f} ({100*(C['total_cost_cw']-B['total_cost_cw'])/B['total_cost_cw']:+.0f}%); arm B sent {100*B['lambda_share']:.1f}% of requests to Lambda and arm C {100*C['lambda_share']:.1f}%. With one run per arm and a six-hour window this difference should not be read as a general ranking.")
    if C and D:
        out.append(f"**Unseen spike.** In arm D the extra load in the spiked hour went to Lambda ({100*D['lambda_share']:.1f}% of requests against {100*C['lambda_share']:.1f}% in arm C), with {100*D['error_rate']:.1f}% failed requests and a p95 of {D['latency_ms']['all']['p95']:.0f} ms against {C['latency_ms']['all']['p95']:.0f} ms, at a cost of ${D['total_cost_cw']:.3f} against ${C['total_cost_cw']:.3f}.")
    gaps = [v["gap"]["lambda_share_pts"] for k2, v in L.items() if k2 != "A_reactive"]
    if gaps:
        out.append(f"**Sim-to-real gap.** The replay assumes capacity is available at once and that only the overflow goes to Lambda. In the live system the weighted load balancer leaks load in both directions, instances take time to become healthy, and weight changes take about {sum(CAL['weight_propagation_s'])/len(CAL['weight_propagation_s']):.0f} s to apply. The measured Lambda share is between {min(gaps):+.1f} and {max(gaps):+.1f} percentage points away from the replay for the hybrid arms, and cost differs by {min(v['gap']['cost_pct'] for k2, v in L.items() if k2 != 'A_reactive'):+.0f}% to {max(v['gap']['cost_pct'] for k2, v in L.items() if k2 != 'A_reactive'):+.0f}%.")
    for t in out: d.para(t)

def conclusion(T, FC, SIM, LIVE, CAL, k):
    out = [(f"CostScale keeps a cheap always-on base sized by a newsvendor quantile and sends the rest to Lambda. In simulation over {SIM['population']} heavy Azure functions priced at AWS ap-south-1 rates with the container capacity measured on AWS, the hybrid with a rolling base costs {k(T['6_hybrid_rolling']['cost'])} per month, {100*(1-T['6_hybrid_rolling']['cost']/T['1_all_lambda']['cost']):.0f}% less than all-Lambda and {100*(1-T['6_hybrid_rolling']['cost']/T['3_reactive_u0.7']['cost']):.0f}% less than the cheapest reactive setting, while serving all load; reactive scaling drops between {T['3_reactive_u0.1']['unserved_pct']:.1f}% and {T['3_reactive_u0.7']['unserved_pct']:.1f}% of load at every utilisation target tried. The newsvendor rule matches brute-force search almost exactly."),
           (f"Three results are weaker than the idea might suggest and are reported as found. The ML forecaster is only {abs(FC['ml_vs_rolling_pct']):.2f}% {'cheaper' if FC['ml_vs_rolling_pct']<0 else 'more expensive'} than a rolling six-hour quantile on test, inside the noise of the assumptions, and the whole remaining headroom to the oracle is {FC['headroom_rolling_to_oracle_pct']:.1f}%. The advantage depends strongly on measured capacity per container and on the Lambda price (Section 8.7). By a documented estimate, the hybrid does not save energy relative to all-Lambda."),]
    if LIVE: out.append("The live AWS runs reproduced the qualitative ordering of the simulator, and the gap between live and replay results is reported in Section 8.8 together with its causes. Each live arm was run once in compressed time from one laptop, so the live evidence supports the design rather than a statistical ranking.")
    return out
