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
    h3 = D["hours"][3]
    return (f"On a smooth six-hour ramp, reactive scaling (arm A) and the ML hybrid (arm C) cost the same (${A['total_cost_cw']:.3f} and ${C['total_cost_cw']:.3f}) with p95 latencies of {A['latency_ms']['all']['p95']:.0f} ms and {C['latency_ms']['all']['p95']:.0f} ms, "
            f"while a static base (arm B) cost {B['total_cost_cw']/C['total_cost_cw']:.1f} times as much. With an unseen 4x spike (arm D) no request failed and {100*h3['lambda_share']:.0f}% of that hour's requests went to Lambda, but {100*D['slo_violation_share']:.0f}% of all requests exceeded the 800 ms target because the load balancer let EC2 run at its limit. "
            "The live runs therefore show that the mechanism works and expose its weak points, but do not show an advantage over reactive scaling on this window; the cost advantage appears in the simulation across bursty functions.")

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
        out.append(f"**Reactive against hybrid (arms A and C).** On this window the two are practically equal. Arm A had {A['errors']} failed requests out of {A['requests']:,} ({100*A['error_rate']:.2f}%), a p95 of {A['latency_ms']['all']['p95']:.0f} ms and a total cost of ${A['total_cost_cw']:.4f}; arm C had no failed requests, a p95 of {C['latency_ms']['all']['p95']:.0f} ms and ${C['total_cost_cw']:.4f}. Both used about {A['instance_hours']:.2f} instance-hours. The window is a smooth ramp (from about 3 to 18 requests per second on average over {6*interval/60:.0f} minutes, minute-level coefficient of variation 0.21), so CPU-based target tracking kept up. The simulator's dropped load for reactive scaling comes from minute-level bursts across the whole population of heavy functions, which this one window does not contain. The honest reading is that arms A to C show the hybrid works and costs about the same as reactive scaling here; they do **not** reproduce the simulated advantage.")
    if B and C:
        import json as _j
        _bdec = _j.load(open(ROOT / 'results/live/B_static/decisions.json'))[0]
        out.append(f"**Static against ML (arms B and C).** Arm B cost ${B['total_cost_cw']:.4f}, {B['total_cost_cw']/C['total_cost_cw']:.1f} times arm C (${C['total_cost_cw']:.4f}). The static base is the q* quantile of the training period, {_bdec['forecast_base_rps']:.1f} requests per second, which is {_bdec['desired']} instances for the whole run, while the window ramps up from a few requests per second; arm B therefore pays for idle capacity (mean CPU {B['mean_ec2_cpu_pct']:.0f}% against {C['mean_ec2_cpu_pct']:.0f}% in arm C). The forecast follows the ramp. This is the clearest live benefit of forecasting, and it is against a static base, not against the rolling baseline.")
    if C and D:
        h3 = D["hours"][3]
        out.append(f"**Unseen spike (arm D).** In the spiked hour the planned load was {h3['planned_rps']:.1f} requests per second against a base of one instance (16 requests per second). No request failed in the whole run, and {100*h3['lambda_share']:.0f}% of that hour's requests went to Lambda. But the hour's p95 latency was {h3['p95_ms']:.0f} ms and the median latency of requests served by EC2 was {h3['ec2_p50_ms']:.0f} ms, so {100*D['slo_violation_share']:.0f}% of all requests in arm D were slower than the 800 ms target or failed. Two causes are visible. First, the weights give EC2 its full measured capacity (about 16 requests per second), which leaves no headroom: with random arrivals a server fed at its limit builds a queue, so the p95-at-capacity measured in calibration does not hold on a sustained basis. Second, the load balancer's weight change takes about {sum(CAL['weight_propagation_s'])/len(CAL['weight_propagation_s']):.0f} s to apply and the observed rate is a 10-second average, so the first seconds of the spike went to EC2 unchanged. A safety factor on capacity (for example weights based on 70 to 80% of the measured capacity) would be the first fix; we did not test it. The Lambda-served requests in this arm were fast (p95 {D['latency_ms']['lambda']['p95']:.0f} ms).")
        out.append(f"**Delivered load.** The load generator is closed-loop: each simulated user waits for its response before sending the next request, so when latency rises the offered rate falls. In the spiked hour the generator delivered {h3['observed_rps']:.1f} requests per second against {h3['planned_rps']:.1f} planned, and arm D served {D['requests']:,} requests in total against {D['planned_requests_replay']:,.0f} planned. The spike was therefore smaller in practice than intended. The same effect makes the slow EC2 tail self-limiting, which means the latency numbers are, if anything, optimistic.")
    gaps = [(k2, v["gap"]["lambda_share_pts"], v["gap"]["cost_pct"]) for k2, v in L.items()]
    if gaps:
        small = [g for g in gaps if g[0] != "D_ml_spike"]
        out.append(f"**Sim-to-real gap.** The replay assumes capacity is available instantly and that only the overflow reaches Lambda. For arms A, B and C the live Lambda share is {min(g[1] for g in small):+.2f} to {max(g[1] for g in small):+.2f} percentage points from the replay and the measured cost is {min(g[2] for g in small):+.1f}% to {max(g[2] for g in small):+.1f}% from it, which is small and, for arms B and C, in the direction of leakage (a little load reaches Lambda that the replay keeps on EC2). The replay of arm A uses the instance counts that the Auto Scaling Group actually had, so its cost agrees by construction. For arm D the gap is large: the live Lambda share is {gaps[3][1]:+.1f} points and the cost {gaps[3][2]:+.0f}% from the replay, because the replay assumes the full planned spike is delivered and that exactly the overflow goes to Lambda, whereas live the generator delivered about 82% of the planned requests and EC2 absorbed more than its share. Weight changes take about {sum(CAL['weight_propagation_s'])/len(CAL['weight_propagation_s']):.0f} s to apply and new instances need {CAL['launch_to_healthy_s'][0]:.0f} to {CAL['launch_to_healthy_s'][1]:.0f} s to become healthy.")
    out.append("**Start-up transient.** In each arm the first trace hour shows a slow tail (for example arm D hour 0: EC2 p95 of about 2.4 s), when the first instance has only just become healthy and is serving its first requests.")
    for t in out: d.para(t)

def conclusion(T, FC, SIM, LIVE, CAL, k):
    out = [(f"CostScale keeps a cheap always-on base sized by a newsvendor quantile and sends the rest to Lambda. In simulation over {SIM['population']} heavy Azure functions priced at AWS ap-south-1 rates with the container capacity measured on AWS, the hybrid with a rolling base costs {k(T['6_hybrid_rolling']['cost'])} per month, {100*(1-T['6_hybrid_rolling']['cost']/T['1_all_lambda']['cost']):.0f}% less than all-Lambda and {100*(1-T['6_hybrid_rolling']['cost']/T['3_reactive_u0.7']['cost']):.0f}% less than the cheapest reactive setting, while serving all load; reactive scaling drops between {T['3_reactive_u0.1']['unserved_pct']:.1f}% and {T['3_reactive_u0.7']['unserved_pct']:.1f}% of load at every utilisation target tried. The newsvendor rule matches brute-force search almost exactly."),
           (f"Three results are weaker than the idea might suggest and are reported as found. The ML forecaster is only {abs(FC['ml_vs_rolling_pct']):.2f}% {'cheaper' if FC['ml_vs_rolling_pct']<0 else 'more expensive'} than a rolling six-hour quantile on test, inside the noise of the assumptions, and the whole remaining headroom to the oracle is {FC['headroom_rolling_to_oracle_pct']:.1f}%. The advantage depends strongly on measured capacity per container and on the Lambda price (Section 8.7). By a documented estimate, the hybrid does not save energy relative to all-Lambda."),]
    if LIVE:
        A, B, C, D = (LIVE.get(k) for k in ("A_reactive", "B_static", "C_ml", "D_ml_spike"))
        out.append(f"The live AWS runs confirm that the mechanism works: the controller sets instance counts from the forecast, shifts traffic to Lambda when load exceeds healthy capacity, and the replay of arms A to C agrees with the measurements to within about 2% in cost. They do not confirm a cost advantage over reactive scaling: on a smooth ramp arms A and C cost the same (${A['total_cost_cw']:.3f} and ${C['total_cost_cw']:.3f}), and the benefit shown was against a static base (arm B cost {B['total_cost_cw']/C['total_cost_cw']:.1f} times as much). The spike arm exposed a real weakness: with no failed requests, {100*D['slo_violation_share']:.0f}% of requests exceeded the latency target because EC2 was fed up to its measured capacity. Each live arm ran once, in compressed time, from one laptop, so the live evidence supports the design rather than a statistical ranking.")
    return out
