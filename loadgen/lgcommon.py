import sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "infra"))
import requests
from requests.adapters import HTTPAdapter
from awscommon import c, load, NAMES, REGION

SERVICE_MS, CPU_MS = 400, 80          # calibrated per-request service time (80 ms CPU + 320 ms wait)
PATH = f"/work?ms={SERVICE_MS}&cpu={CPU_MS}"
_sess = requests.Session(); _sess.mount("http://", HTTPAdapter(pool_connections=4, pool_maxsize=256))

def url(): return "http://" + load()["alb_dns"] + PATH

def one(u, t0):
    s = time.time()
    try:
        r = _sess.get(u, timeout=10); lat = (time.time() - s) * 1000
        b = r.json().get("backend", "?") if r.status_code == 200 else f"http{r.status_code}"
        return (s - t0, b, lat, r.status_code)
    except Exception as e:
        return (s - t0, "error", (time.time() - s) * 1000, 0)

def run_rate(u, rps, secs, t0=None, pool=None):
    """open-loop constant arrival rate"""
    t0 = t0 or time.time(); out = []; futs = []
    own = pool is None; pool = pool or ThreadPoolExecutor(256)
    n = int(rps * secs); start = time.time()
    for k in range(n):
        d = start + k / rps - time.time()
        if d > 0: time.sleep(d)
        futs.append(pool.submit(one, u, t0))
    out = [f.result() for f in futs]
    if own: pool.shutdown()
    return out

def set_weights(ec2_w, lam_w):
    s = load(); elb = c("elbv2")
    acts = [{"Type": "forward", "ForwardConfig": {"TargetGroups": [{"TargetGroupArn": s["tg_ec2"], "Weight": int(ec2_w)}, {"TargetGroupArn": s["tg_lambda"], "Weight": int(lam_w)}]}}]
    elb.modify_listener(ListenerArn=s["listener_arn"], DefaultActions=acts)

def healthy_count():
    s = load(); h = c("elbv2").describe_target_health(TargetGroupArn=s["tg_ec2"])["TargetHealthDescriptions"]
    return sum(1 for x in h if x["TargetHealth"]["State"] == "healthy")

def set_desired(n):
    c("autoscaling").set_desired_capacity(AutoScalingGroupName=NAMES["asg"], DesiredCapacity=int(n), HonorCooldown=False)

# ---- keep the ALB security group pointed at the laptop's CURRENT public IP (mobile network IP changes); adds exact /32s only
def ensure_ip():
    try:
        ip = requests.get("https://checkip.amazonaws.com", timeout=5).text.strip(); cidr = ip + "/32"
        s = load(); ec2 = c("ec2")
        cur = ec2.describe_security_groups(GroupIds=[s["sg_alb"]])["SecurityGroups"][0]["IpPermissions"]
        if cidr not in [r["CidrIp"] for p in cur for r in p.get("IpRanges", [])]:
            ec2.authorize_security_group_ingress(GroupId=s["sg_alb"], IpPermissions=[{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
                "IpRanges": [{"CidrIp": cidr, "Description": "laptop (auto-added)"}]}])
            print("[ip-watchdog] added", cidr, flush=True); time.sleep(8)
    except Exception as e: print("[ip-watchdog]", type(e).__name__, str(e)[:80], flush=True)

def start_ip_watchdog(period=10):
    ensure_ip()
    def loop():
        while True: time.sleep(period); ensure_ip()
    threading.Thread(target=loop, daemon=True).start()
