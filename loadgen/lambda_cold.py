"""Redo calibration step 3 correctly: wait for ALB weight propagation (~12 s), then keep only responses served by Lambda."""
import json, time
import numpy as np
from lgcommon import *
start_ip_watchdog()
lam = c("lambda"); u = url(); set_weights(0, 999); time.sleep(25)
def batch(n):
    with ThreadPoolExecutor(32) as pool: return [f.result() for f in [pool.submit(one, u, time.time()) for _ in range(n)]]
cold_all, warm_all = [], []
for trial in range(3):
    lam.update_function_configuration(FunctionName=NAMES["fn"], Environment={"Variables": {"VER": str(time.time())}})
    lam.get_waiter("function_updated_v2").wait(FunctionName=NAMES["fn"]); time.sleep(2)
    cold_all += batch(8)
    for _ in range(2): time.sleep(1); warm_all += batch(8)
cold = [x[2] for x in cold_all if x[3] == 200 and x[1] == "lambda"]; warm = [x[2] for x in warm_all if x[3] == 200 and x[1] == "lambda"]
res = dict(cold_n=len(cold), warm_n=len(warm), cold_median=float(np.median(cold)), cold_p95=float(np.percentile(cold, 95)), cold_max=float(max(cold)),
           warm_median=float(np.median(warm)), warm_p95=float(np.percentile(warm, 95)),
           non_lambda_dropped=len(cold_all) + len(warm_all) - len(cold) - len(warm))
res["cold_overhead_ms_median"] = res["cold_median"] - res["warm_median"]
cal = json.load(open(ROOT / "results/calibration.json"))
cal["lambda_cold_warm_v2"] = res
for k in ("lambda_cold_ms", "lambda_warm_ms", "lambda_cold_overhead_ms"): cal.pop(k, None)
cal["note_step3"] = "first calibration run measured cold/warm before ALB weights propagated (~12 s) so mixed in EC2 responses; replaced by lambda_cold_warm_v2"
cal["launch_to_healthy_s_first_ever_launch_earlier_run"] = 93.83
json.dump(cal, open(ROOT / "results/calibration.json", "w"), indent=1); print(json.dumps(res, indent=1))
