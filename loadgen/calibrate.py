"""Phase 4 calibration -> results/calibration.json. Requires `make up`. Measures:
 1 ASG launch-to-healthy time (2 trials)   2 sustainable req/s per t3.medium at p95 target   3 Lambda cold vs warm latency
 4 ALB weight-update propagation delay (both directions)."""
import json, time, statistics as st
import numpy as np
from lgcommon import *
lam = c("lambda"); out = {"service_ms": SERVICE_MS, "cpu_ms": CPU_MS, "region": REGION, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
u = url()
def pct(xs, p): return float(np.percentile(xs, p)) if len(xs) else float("nan")

# 1 launch time
launch = []
for trial in range(2):
    set_weights(0, 999); set_desired(1); t0 = time.time()
    while healthy_count() < 1:
        if time.time() - t0 > 600: raise SystemExit("instance never healthy")
        time.sleep(2)
    launch.append(time.time() - t0); print("launch-to-healthy", launch[-1], flush=True)
    if trial == 0:
        set_desired(0); t1 = time.time()
        while c("autoscaling").describe_auto_scaling_groups(AutoScalingGroupNames=[NAMES["asg"]])["AutoScalingGroups"][0]["Instances"] and time.time() - t1 < 300: time.sleep(5)
out["launch_to_healthy_s"] = launch

# 2 capacity (EC2 only, 100% weight)
set_weights(999, 0); time.sleep(8)
run_rate(u, 3, 10)  # warm
steps = []
for rps in (4, 8, 12, 16, 20, 24):
    r = run_rate(u, rps, 45); r = [x for x in r if x[0] >= 0]; r = r[int(len(r) * 0.2):]
    lat = [x[2] for x in r if x[3] == 200]; err = 1 - len(lat) / len(r)
    steps.append(dict(rps=rps, p50=pct(lat, 50), p95=pct(lat, 95), p99=pct(lat, 99), error_rate=err)); print(steps[-1], flush=True)
    if err > 0.2 or pct(lat, 95) > 5000: break
out["capacity_steps"] = steps
TARGET_P95 = 2 * SERVICE_MS     # 800 ms
ok = [s for s in steps if s["p95"] <= TARGET_P95 and s["error_rate"] < 0.01]
sus = max([s["rps"] for s in ok]) if ok else 0
out["p95_target_ms"] = TARGET_P95; out["sustainable_rps_per_instance"] = sus
out["capacity_units"] = {"ec2": sus * SERVICE_MS / 1000.0}   # concurrent requests per t3.medium (feeds sim)

# 3 lambda cold vs warm
set_weights(0, 999)
lam.update_function_configuration(FunctionName=NAMES["fn"], Environment={"Variables": {"V": str(time.time())}})
lam.get_waiter("function_updated_v2").wait(FunctionName=NAMES["fn"]); time.sleep(3)
cold, warm = [], []
with ThreadPoolExecutor(16) as pool:
    cold = [f.result() for f in [pool.submit(one, u, time.time()) for _ in range(8)]]
    for _ in range(3):
        time.sleep(1); warm += [f.result() for f in [pool.submit(one, u, time.time()) for _ in range(8)]]
cl = [x[2] for x in cold if x[3] == 200]; wl = [x[2] for x in warm if x[3] == 200]
out["lambda_cold_ms"] = dict(median=pct(cl, 50), max=max(cl)); out["lambda_warm_ms"] = dict(median=pct(wl, 50), p95=pct(wl, 95))
out["lambda_cold_overhead_ms"] = pct(cl, 50) - pct(wl, 50)
print("lambda cold/warm", out["lambda_cold_ms"], out["lambda_warm_ms"], flush=True)

# 4 weight propagation (needs 1 healthy instance)
set_desired(1)
while healthy_count() < 1: time.sleep(2)
def propagation(frm, to):
    set_weights(*frm); time.sleep(20)
    t0 = time.time(); res = []; stop = threading.Event()
    def sender():
        with ThreadPoolExecutor(32) as pool:
            while not stop.is_set():
                res.extend(f.result() for f in [pool.submit(one, u, t0) for _ in range(10)]); time.sleep(0.1)
    th = threading.Thread(target=sender); th.start(); time.sleep(3)
    ts = time.time() - t0; set_weights(*to); tset = time.time() - t0
    time.sleep(40); stop.set(); th.join()
    old = "ec2" if frm[0] > frm[1] else "lambda"
    last_old = max([x[0] for x in res if x[1] == old and x[0] > tset] or [tset])
    return last_old - tset
prop = [propagation((999, 0), (0, 999)), propagation((0, 999), (999, 0)), propagation((999, 0), (0, 999))]
out["weight_propagation_s"] = prop; print("propagation", prop, flush=True)
set_desired(0)
json.dump(out, open(ROOT / "results/calibration.json", "w"), indent=1)
print(json.dumps(out, indent=1))
