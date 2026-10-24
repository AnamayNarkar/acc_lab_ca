"""Print the headline tables from results/*.json for the screencast (no AWS access needed)."""
import json, sys
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "results"
S, F = json.load(open(R / "sim_results.json")), json.load(open(R / "forecast_results.json")); T = S["ec2"]["test"]
what = sys.argv[1] if len(sys.argv) > 1 else "sim"
if what == "sim":
    print(f"{'strategy':22s} {'$/month':>10s} {'unserved':>9s} {'util':>6s} {'lambda':>7s}")
    for k in ("1_all_lambda", "2_peak_x1.2", "3_reactive_u0.7", "3_reactive_u0.3", "4_seasonal_u0.7", "5_hybrid_static", "6_hybrid_rolling", "7_hybrid_ML", "8_hybrid_oracle"):
        v = T[k]; u = "  n/a" if v["util"] != v["util"] else f"{v['util']:.2f}"
        print(f"{k:22s} {v['cost']:>10,.0f} {v['unserved_pct']:>8.2f}% {u:>6s} {v['lambda_share']:>7.2f}")
    print(f"\nML vs rolling-6h decision cost (test): {F['ml_vs_rolling_pct']:+.2f}%   headroom rolling->oracle: {F['headroom_rolling_to_oracle_pct']:.1f}%")
elif what == "live":
    L = json.load(open(R / "live_results.json"))
    print(f"{'arm':12s} {'reqs':>6s} {'err%':>6s} {'lambda%':>8s} {'p95ms':>6s} {'cost$':>7s} {'sim$':>7s}")
    for a, v in L.items(): print(f"{a:12s} {v['requests']:>6d} {100*v['error_rate']:>6.1f} {100*v['lambda_share']:>8.1f} {v['latency_ms']['all']['p95']:>6.0f} {v['total_cost_cw']:>7.3f} {v['sim_replay']['total_cost']:>7.3f}")
