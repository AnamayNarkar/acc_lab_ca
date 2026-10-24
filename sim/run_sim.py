"""Phase 2 simulator: replay real trace, 8 strategies. Tune on validation only; test evaluated once (final)."""
import json, sys
from pathlib import Path
import numpy as np
from core import *

def setup(kind="ec2", p=P, cap=None, fscale=1.0, lscale=1.0):
    conc, meta = load_all()
    mem, dur = meta.app_memory_mb.values, meta.avg_duration_ms.values
    # heavy = best single-platform monthly cost on TRAIN days >= $50 (EC2 base, assumed capacities)
    Lm = lambda_unit_min(mem, dur)  # $/unit-min
    f0 = f_unit_min("ec2")
    lam_month = (conc[:, TRAIN].sum(1) * Lm) * (MONTH_MIN / (10 * MIN))
    peak_month = 1.2 * conc[:, TRAIN].max(1) * f0 * MONTH_MIN
    best = np.minimum(lam_month, peak_month)
    heavy = best >= 50
    return conc, meta, heavy, best

def make_env(conc, meta, idx, kind, p=P, cap=None, fscale=1.0, lscale=1.0):
    mem, dur = meta.app_memory_mb.values[idx], meta.avg_duration_ms.values[idx]
    f = f_unit_min(kind, p, cap, fscale)
    L = lambda_unit_min(mem, dur, p, lscale)
    gbs_per_unit_min = 60.0 * np.maximum(128.0, mem) / 1024.0  # GB-s to serve one unit for a minute
    return dict(c=conc[idx], f=f, L=L, q=qstar(f, L), gb=gbs_per_unit_min, kind=kind, cap=cap or CAP[kind])

def hybrid_eval(E, per, B, ceil=False):
    """B: base capacity [n, hours of period] (units). Overflow billed Lambda."""
    x = E["c"][:, per]; n, T = x.shape
    if ceil: B = np.ceil(B / E["cap"]) * E["cap"]
    Bm = np.repeat(B, 60, axis=1)
    over = np.maximum(0, x - Bm)
    served = np.minimum(x, Bm)
    cont = Bm.sum() * E["f"]
    lam = (over.sum(1) * E["L"]).sum()
    tot_load = x.sum()
    util = served.sum() / max(Bm.sum(), 1e-9)
    gbs = (over.sum(1) * E["gb"]).sum()
    en = energy_wh(Bm.sum(), util, gbs, E["kind"])
    return dict(cost=cont + lam, cost_container=cont, cost_lambda=lam, unserved_pct=0.0, util=util,
                lambda_share=over.sum() / tot_load, energy_wh=en, minutes=T,
                per_app=((Bm.sum(1) * E["f"]) + over.sum(1) * E["L"]))

def capped_eval(E, per, Cap):
    """Container-only: Cap [n, T]. Load above Cap is unserved (no fallback)."""
    x = E["c"][:, per]
    served = np.minimum(x, Cap)
    unserved = np.maximum(0, x - Cap)
    cont = Cap.sum() * E["f"]
    util = served.sum() / max(Cap.sum(), 1e-9)
    en = energy_wh(Cap.sum(), util, 0.0, E["kind"])
    return dict(cost=cont, cost_container=cont, cost_lambda=0.0, unserved_pct=100 * unserved.sum() / x.sum(),
                util=util, lambda_share=0.0, energy_wh=en, minutes=x.shape[1], per_app=Cap.sum(1) * E["f"])

def all_lambda(E, per):
    x = E["c"][:, per]
    lam = (x.sum(1) * E["L"]); gbs = (x.sum(1) * E["gb"]).sum()
    return dict(cost=lam.sum(), cost_container=0.0, cost_lambda=lam.sum(), unserved_pct=0.0, util=float("nan"),
                lambda_share=1.0, energy_wh=energy_wh(0, 0, gbs), minutes=x.shape[1], per_app=lam)

# ---- base capacity generators (hourly, per app) for a period slice
def hours_of(per): return range(per.start // 60, per.stop // 60)

def base_static(E, per):
    q = E["q"]; tr = E["c"][:, TRAIN]
    b = quantile_per_row(tr, q); b[q == 0] = 0
    return np.repeat(b[:, None], len(hours_of(per)), axis=1)

def base_rolling(E, per, delta=0.0, win=360):
    q = np.clip(E["q"] + delta, 0, 1) * (E["q"] > 0); out = []
    for h in hours_of(per):
        w = E["c"][:, h * 60 - win:h * 60]
        b = quantile_per_row(w, q); b[q == 0] = 0; out.append(b)
    return np.stack(out, 1)

def base_oracle(E, per):
    q = E["q"]; out = []
    for h in hours_of(per):
        w = E["c"][:, h * 60:(h + 1) * 60]
        b = quantile_per_row(w, q); b[q == 0] = 0; out.append(b)
    return np.stack(out, 1)

def cap_reactive(E, per, u):
    x = E["c"]; lag = x[:, per.start - 5:per.stop - 5]
    return lag / u

def cap_seasonal(E, per, u, ndays=3):
    out = []
    for h in hours_of(per):
        ms = [E["c"][:, h * 60 - d * MIN:h * 60 - d * MIN + 60].max(1) for d in range(1, ndays + 1)]
        out.append(np.mean(ms, 0) / u)
    return np.repeat(np.stack(out, 1), 60, axis=1)

def cap_peak(E, per):
    pk = 1.2 * E["c"][:, TRAIN].max(1)
    return np.repeat(pk[:, None], per.stop - per.start, axis=1)

def run_all(E, per, ml_base=None, ceil=False):
    R = {"1_all_lambda": all_lambda(E, per), "2_peak_x1.2": capped_eval(E, per, cap_peak(E, per))}
    for u in (0.7, 0.5, 0.3, 0.2, 0.1):
        R[f"3_reactive_u{u}"] = capped_eval(E, per, cap_reactive(E, per, u))
        R[f"4_seasonal_u{u}"] = capped_eval(E, per, cap_seasonal(E, per, u))
    R["5_hybrid_static"] = hybrid_eval(E, per, base_static(E, per), ceil)
    R["6_hybrid_rolling"] = hybrid_eval(E, per, base_rolling(E, per), ceil)
    if ml_base is not None: R["7_hybrid_ML"] = hybrid_eval(E, per, ml_base, ceil)
    R["8_hybrid_oracle"] = hybrid_eval(E, per, base_oracle(E, per), ceil)
    return R

def monthly(R, per):
    days = (per.stop - per.start) / MIN
    return {k: {**{m: (float(v[m]) * 30 / days if m.startswith("cost") or m == "energy_wh" else float(v[m]))
                   for m in ("cost", "cost_container", "cost_lambda", "unserved_pct", "util", "lambda_share", "energy_wh")}}
            for k, v in R.items()}

if __name__ == "__main__":
    conc, meta, heavy, best = setup()
    trig = meta.trigger.values
    summ = json.load(open(ROOT / "results/dataset_summary.json"))
    summ["heavy_functions"] = int(heavy.sum())
    summ["heavy_by_trigger"] = {t: int(((trig == t) & heavy).sum()) for t in np.unique(trig)}
    summ["heavy_rule"] = "min(all-Lambda, peak-x1.2 EC2 containers) monthly cost on TRAIN days >= $50"
    json.dump(summ, open(ROOT / "results/dataset_summary.json", "w"), indent=2)
    print(summ["heavy_functions"], summ["heavy_by_trigger"])
    idx = np.where(heavy & (trig != "timer"))[0]
    np.save(ROOT / "data/processed/pop_idx.npy", idx)
    print("population (heavy, non-timer):", len(idx))
    out = {"population": int(len(idx)), "capacity_units": CAP, "prices": P}
    ml = {}
    for nm, per in (("val", VAL), ("test", TEST)):
        pth = ROOT / f"results/cache/ml_base_{nm}.npy"
        ml[nm] = np.load(pth) if pth.exists() else None
    for kind in ("ec2", "fargate"):
        E = make_env(conc, meta, idx, kind)
        out[kind] = {nm: monthly(run_all(E, per, ml[nm]), per) for nm, per in (("val", VAL), ("test", TEST))}
    # q* delta sweep (validation) -- does theory q* beat nudged quantiles?
    E = make_env(conc, meta, idx, "ec2"); sweep = {}
    for d in (-0.2, -0.1, -0.05, 0, 0.05, 0.1):
        sweep[str(d)] = monthly({"x": hybrid_eval(E, VAL, base_rolling(E, VAL, d))}, VAL)["x"]["cost"]
    out["qstar_sweep_rolling_val_cost"] = sweep
    out["qstar_stats"] = dict(median=float(np.median(E["q"])), frac_zero=float((E["q"] == 0).mean()))
    # sensitivity (test, hybrid-rolling & oracle & reactive u=0.3 & all-lambda)
    sens = {}
    for name, kw in {"cap_x0.5": dict(cap=CAP["ec2"] * .5), "cap_x1.5": dict(cap=CAP["ec2"] * 1.5),
                     "lambda_price_x0.5": dict(lscale=.5), "lambda_price_x2": dict(lscale=2.0),
                     "ec2_savings_-30pct_hypothetical": dict(fscale=.7), "fargate_base": dict(kind="fargate")}.items():
        kind = kw.pop("kind", "ec2")
        Es = make_env(conc, meta, idx, kind, **kw)
        R = {"1_all_lambda": all_lambda(Es, TEST), "3_reactive_u0.3": capped_eval(Es, TEST, cap_reactive(Es, TEST, .3)),
             "5_hybrid_static": hybrid_eval(Es, TEST, base_static(Es, TEST)),
             "6_hybrid_rolling": hybrid_eval(Es, TEST, base_rolling(Es, TEST)),
             "8_hybrid_oracle": hybrid_eval(Es, TEST, base_oracle(Es, TEST))}
        sens[name] = monthly(R, TEST)
    R = {"6_hybrid_rolling": hybrid_eval(E, TEST, base_rolling(E, TEST), ceil=True),
         "8_hybrid_oracle": hybrid_eval(E, TEST, base_oracle(E, TEST), ceil=True)}
    sens["integer_instances_per_app"] = monthly(R, TEST)
    out["sensitivity_test"] = sens
    # per-app distribution (test): ratio of hybrid-rolling cost to best of all-Lambda / reactive.3
    Rt = run_all(E, TEST, ml["test"])
    pa = {k: v["per_app"] for k, v in Rt.items()}
    ratio = pa["6_hybrid_rolling"] / np.minimum(pa["1_all_lambda"], pa["2_peak_x1.2"])
    out["per_app_ratio_rolling_vs_best_single"] = {f"p{q}": float(np.percentile(ratio, q)) for q in (5, 25, 50, 75, 95)}
    out["per_app_frac_hybrid_cheaper_than_all_lambda"] = float((pa["6_hybrid_rolling"] < pa["1_all_lambda"]).mean())
    np.save(ROOT / "results/cache/per_app_test.npy", np.stack([pa[k] for k in sorted(pa)]), allow_pickle=False) if (ROOT/"results/cache").exists() else None
    json.dump(out, open(ROOT / "results/sim_results.json", "w"), indent=1, default=float)
    for k, v in out["ec2"]["test"].items():
        print(f"{k:22s} ${v['cost']:>10,.0f}  unserved {v['unserved_pct']:5.2f}%  util {v['util']:.2f}  lam {v['lambda_share']:.2f}")
