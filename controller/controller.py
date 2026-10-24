"""CostScale controller (local). Per decision interval: forecast -> ASG desired capacity.
Per tick (= 1 trace minute, compressed): read observed rps -> set ALB weights, EC2 share = min(1, healthy_capacity_rps / observed_rps).
Arms: reactive (ASG target tracking, 100% EC2), static, ml, ml_spike."""
import csv, json, pickle, sys, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for p in ("sim", "forecast", "loadgen", "infra"): sys.path.insert(0, str(ROOT / p))
import numpy as np
from awscommon import c, load, NAMES
import lgcommon as lg
from features import feats_at, QS

EC2_HOURLY, LAM_GBS, LAM_REQ = 0.0448, 1.66667e-5, 2e-7
LAMBDA_GB = 1769 / 1024.0

class Workload:
    def __init__(self, interval_s):
        self.w = json.load(open(ROOT / "results/live_workload.json"))
        fp = pickle.load(open(ROOT / "results/cache/forecaster.pkl", "rb"))
        self.models, self.level_all, self.trig_all, self.idx = fp["models"], fp["level"], fp["trigger"], fp["idx"]
        self.row = int(np.where(self.idx == self.w["idx"])[0][0])
        sys.path.insert(0, str(ROOT / "sim")); from core import load_all
        conc, meta = load_all()
        self.C = conc[self.w["idx"]].copy()[None, :]                   # trace concurrency [1, T]
        inv = np.load(ROOT / "data/processed/inv.npy", mmap_mode="r")[self.w["idx"]]
        self.inv = np.asarray(inv, dtype=float)                        # req/min
        self.dur_s = self.w["avg_duration_ms"] / 1000.0
        self.scale = self.w["scale_factor"]; self.h0 = self.w["window_start_hour_abs"]
        self.level = self.level_all[self.row:self.row + 1]; self.trig = self.trig_all[self.row:self.row + 1]
        self.interval_s = interval_s; self.tick_s = interval_s / 60.0
        self.rps = self.inv[self.h0 * 60:(self.h0 + 6) * 60] / 60.0 * self.scale    # live req/s per trace minute
        self.spike = None   # (hour_in_window, mult)

    def apply_spike(self, hour, mult):
        self.spike = (hour, mult)
        self.rps = self.rps.copy(); self.rps[hour * 60:(hour + 1) * 60] *= mult
        self.C = self.C.copy(); a = (self.h0 + hour) * 60
        self.C[0, a:a + 60] *= mult                                   # later forecasts see the spike in their history

    def conc_to_rps(self, conc): return conc / self.dur_s * self.scale

class Controller:
    def __init__(self, arm, interval_s, outdir, cal):
        self.arm, self.interval_s, self.out = arm, interval_s, Path(outdir); self.out.mkdir(parents=True, exist_ok=True)
        self.cal = cal; self.cap = cal["sustainable_rps_per_instance"]
        self.wl = Workload(interval_s)
        if arm == "D_ml_spike": self.wl.apply_spike(3, 4.0)
        self.f_rpsmin = EC2_HOURLY / 60.0 / self.cap                                  # $/rps-minute container
        per_req = SERVICE_MS_S * LAMBDA_GB * LAM_GBS + LAM_REQ
        self.L_rpsmin = 60.0 * per_req                                                # $/rps-minute Lambda
        self.qstar = max(0.0, 1 - self.f_rpsmin / self.L_rpsmin)
        self.cw, self.asg, self.elb = c("cloudwatch"), c("autoscaling"), c("elbv2")
        self.log = []; self.decisions = []; self.cost = 0.0; self.lam_reqs = 0; self.stop = threading.Event(); self.t0 = None
        self.share = 1.0; self.base_rps = 0.0; self.fcst_rps = 0.0
        json.dump(dict(arm=arm, qstar=self.qstar, f_rpsmin=self.f_rpsmin, L_rpsmin=self.L_rpsmin, cap=self.cap), open(self.out / "params.json", "w"))

    # ---- forecasting
    def forecast_base_rps(self, hour):
        h = self.wl.h0 + hour
        if self.arm == "B_static":
            tr = self.wl.C[0, :10 * 1440]; conc = float(np.quantile(tr, self.qstar))
        else:
            F = feats_at(self.wl.C, h, self.wl.level, self.wl.trig)
            P = np.maximum.accumulate(np.maximum(np.array([self.models_pred(q, F) for q in QS]), 0)) * self.wl.level[0]
            conc = float(np.interp(self.qstar, [0.0] + QS, np.concatenate([[0.0], P])))
        return self.wl.conc_to_rps(conc)
    def models_pred(self, q, F): return float(self.wl.models[q].predict(F)[0])

    def decide(self, hour):
        base = self.forecast_base_rps(hour)
        n = int(np.ceil(base / self.cap - 1e-9)) if base > 0 else 0
        n = min(n, 8)
        self.asg.set_desired_capacity(AutoScalingGroupName=NAMES["asg"], DesiredCapacity=n, HonorCooldown=False)
        self.base_rps, self.fcst_rps = n * self.cap, base
        self.decisions.append(dict(hour=hour, t=time.time() - self.t0, forecast_base_rps=base, desired=n, base_cap_rps=n * self.cap))
        print(f"[{self.arm}] hour {hour}: base {base:.1f} rps -> desired {n}", flush=True)

    # ---- per tick
    def tick(self, minute, observed, lam_reqs_since):
        healthy = lg.healthy_count() if self.arm != "A_reactive" else None
        if self.arm == "A_reactive": ew, lw, share = 999, 0, 1.0
        else:
            cap_now = healthy * self.cap
            share = 1.0 if observed <= 0 else min(1.0, cap_now / observed)
            ew = int(round(999 * share)); lw = 999 - ew
            if ew == 0 and lw == 0: lw = 1
            lg.set_weights(ew, lw)
        asg = self.asg.describe_auto_scaling_groups(AutoScalingGroupNames=[NAMES["asg"]])["AutoScalingGroups"][0]
        inst = sum(1 for i in asg["Instances"] if i["LifecycleState"] in ("InService", "Pending", "Pending:Wait", "Pending:Proceed"))
        self.cost += inst * EC2_HOURLY * self.wl.tick_s / 3600.0
        self.cost += lam_reqs_since * (SERVICE_MS_S * LAMBDA_GB * LAM_GBS + LAM_REQ)
        row = dict(t=time.time() - self.t0, minute=minute, observed_rps=observed, planned_rps=float(self.wl.rps[minute]) if minute < 360 else 0,
                   share=share, ec2_w=ew, healthy=healthy if healthy is not None else inst, instances=inst, forecast_rps=self.fcst_rps,
                   base_cap_rps=self.base_rps, cost=self.cost)
        self.log.append(row)
        try:
            d = [{"Name": "Arm", "Value": self.arm}]
            self.cw.put_metric_data(Namespace="CostScale", MetricData=[
                {"MetricName": "Forecast", "Dimensions": d, "Value": self.fcst_rps}, {"MetricName": "Actual", "Dimensions": d, "Value": observed},
                {"MetricName": "BaseCapacity", "Dimensions": d, "Value": self.base_rps}, {"MetricName": "Weight", "Dimensions": d, "Value": 100 * share},
                {"MetricName": "RunningCost", "Dimensions": d, "Value": self.cost}])
        except Exception as e: print("metric err", e)

    def setup_arm(self):
        pol = "costscale-tt-cpu"
        if self.arm == "A_reactive":
            self.asg.update_auto_scaling_group(AutoScalingGroupName=NAMES["asg"], MinSize=1, MaxSize=8, DesiredCapacity=1)
            self.asg.put_scaling_policy(AutoScalingGroupName=NAMES["asg"], PolicyName=pol, PolicyType="TargetTrackingScaling", EstimatedInstanceWarmup=60,
                TargetTrackingConfiguration={"PredefinedMetricSpecification": {"PredefinedMetricType": "ASGAverageCPUUtilization"}, "TargetValue": 50.0})
            lg.set_weights(999, 0)
        else:
            try: self.asg.delete_policy(AutoScalingGroupName=NAMES["asg"], PolicyName=pol)
            except Exception: pass
            self.asg.update_auto_scaling_group(AutoScalingGroupName=NAMES["asg"], MinSize=0, MaxSize=8)

    def finish(self):
        with open(self.out / "controller_ticks.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(self.log[0].keys())); w.writeheader(); w.writerows(self.log)
        json.dump(self.decisions, open(self.out / "decisions.json", "w"), indent=1)

SERVICE_MS_S = lg.SERVICE_MS / 1000.0
