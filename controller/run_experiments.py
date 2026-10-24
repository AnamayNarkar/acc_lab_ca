"""Run arms A-D sequentially (same trace and seed), then collect CloudWatch stats. Usage: run_experiments.py [ARMS...]  (default A B C D)
Between arms: ASG -> 0 and wait. Always followed by `make down` (the Makefile target does NOT run it; run it yourself)."""
import json, os, subprocess, sys, time, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "loadgen")); sys.path.insert(0, str(ROOT / "infra"))
import lgcommon as lg
from awscommon import c, NAMES
ARMS = {"A": "A_reactive", "B": "B_static", "C": "C_ml", "D": "D_ml_spike"}
cal = json.load(open(ROOT / "results/calibration.json"))
worst_launch = max(cal["launch_to_healthy_s"] + [cal.get("launch_to_healthy_s_first_ever_launch_earlier_run", 0)])
interval = 4 * worst_launch                                         # decision interval >= 4x worst measured launch time
interval = min(interval, 400.0)                                    # arm <= 40 min (6 intervals)
if os.environ.get("INTERVAL_OVERRIDE"): interval = float(os.environ["INTERVAL_OVERRIDE"])   # smoke tests only
print("decision interval (s per trace hour):", interval, "-> arm length", 6 * interval / 60, "min")
sel = [a for a in (sys.argv[1:] or list(ARMS))]
asg = c("autoscaling")
def drain():
    lg.set_weights(0, 999)
    asg.update_auto_scaling_group(AutoScalingGroupName=NAMES["asg"], MinSize=0)
    try: asg.delete_policy(AutoScalingGroupName=NAMES["asg"], PolicyName="costscale-tt-cpu")
    except Exception: pass
    lg.set_desired(0)
    for _ in range(60):
        g = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[NAMES["asg"]])["AutoScalingGroups"][0]
        if not g["Instances"]: break
        time.sleep(5)
for a in sel:
    arm = ARMS[a]; out = ROOT / os.environ.get("LIVE_OUTDIR", "results/live") / arm; out.mkdir(parents=True, exist_ok=True)   # LIVE_OUTDIR keeps demo runs from overwriting the recorded results
    drain(); time.sleep(20)
    t_start = datetime.datetime.utcnow()
    env = dict(os.environ, ARM=arm, INTERVAL_S=str(interval), OUTDIR=str(out))
    cmd = [str(ROOT / ".venv/bin/locust"), "-f", str(ROOT / "loadgen/locustfile.py"), "--headless", "--csv", str(out / "locust"),
           "--csv-full-history", "--run-time", f"{int(6 * interval) + 20}s", "-u", "1", "-r", "50", "--only-summary"]
    print("RUN", arm, flush=True); subprocess.run(cmd, env=env, cwd=ROOT / "loadgen", check=False)
    t_end = datetime.datetime.utcnow(); time.sleep(90)    # let CloudWatch settle
    cw, ids = c("cloudwatch"), None
    def stat(ns, name, dims, stat_, period=60):
        r = cw.get_metric_statistics(Namespace=ns, MetricName=name, Dimensions=dims, StartTime=t_start, EndTime=t_end + datetime.timedelta(minutes=2), Period=period, Statistics=[stat_])
        return sorted([(d["Timestamp"].isoformat(), d[stat_]) for d in r["Datapoints"]])
    m = {"ec2_cpu_avg": stat("AWS/EC2", "CPUUtilization", [{"Name": "AutoScalingGroupName", "Value": NAMES["asg"]}], "Average"),
         "lambda_invocations": stat("AWS/Lambda", "Invocations", [{"Name": "FunctionName", "Value": NAMES["fn"]}], "Sum"),
         "lambda_duration_sum_ms": stat("AWS/Lambda", "Duration", [{"Name": "FunctionName", "Value": NAMES["fn"]}], "Sum"),
         "lambda_concurrent_max": stat("AWS/Lambda", "ConcurrentExecutions", [{"Name": "FunctionName", "Value": NAMES["fn"]}], "Maximum"),
         "asg_in_service": stat("AWS/AutoScaling", "GroupInServiceInstances", [{"Name": "AutoScalingGroupName", "Value": NAMES["asg"]}], "Average"),
         "start_utc": t_start.isoformat(), "end_utc": t_end.isoformat(), "interval_s": interval}
    json.dump(m, open(out / "cloudwatch.json", "w"), indent=1)
drain()
print("DONE. Now run: make down")
