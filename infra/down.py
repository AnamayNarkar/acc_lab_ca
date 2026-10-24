"""Destroy everything tagged project=costscale that `up.py` created, then verify with the tagging API.
Budgets (cost safeguards) are deliberately kept and excluded from the verification."""
import time
from awscommon import *
ec2, elb, lam, iam, asg, cw, logs, tagging = (c(x) for x in ("ec2", "elbv2", "lambda", "iam", "autoscaling", "cloudwatch", "logs", "resourcegroupstaggingapi"))
def ok(f, *a, **k):
    try: return f(*a, **k)
    except Exception as e: print("  (skip)", type(e).__name__, str(e)[:100]); return None

print("ASG ...")
if asg.describe_auto_scaling_groups(AutoScalingGroupNames=[NAMES["asg"]])["AutoScalingGroups"]:
    ok(asg.delete_auto_scaling_group, AutoScalingGroupName=NAMES["asg"], ForceDelete=True)
    for _ in range(60):
        if not asg.describe_auto_scaling_groups(AutoScalingGroupNames=[NAMES["asg"]])["AutoScalingGroups"]: break
        time.sleep(5)
print("listeners/ALB ...")
a = ok(elb.describe_load_balancers, Names=[NAMES["alb"]])
if a:
    arn = a["LoadBalancers"][0]["LoadBalancerArn"]
    for l in elb.describe_listeners(LoadBalancerArn=arn)["Listeners"]: ok(elb.delete_listener, ListenerArn=l["ListenerArn"])
    ok(elb.delete_load_balancer, LoadBalancerArn=arn)
    for _ in range(40):
        if not ok(elb.describe_load_balancers, Names=[NAMES["alb"]]): break
        time.sleep(5)
    time.sleep(20)  # let ENIs detach
for n in (NAMES["tg_ec2"], NAMES["tg_lambda"]):
    t = ok(elb.describe_target_groups, Names=[n])
    if t: ok(elb.delete_target_group, TargetGroupArn=t["TargetGroups"][0]["TargetGroupArn"])
print("launch template, lambda, role, logs, dashboard ...")
ok(ec2.delete_launch_template, LaunchTemplateName=NAMES["lt"])
ok(lam.delete_function, FunctionName=NAMES["fn"])
ok(logs.delete_log_group, logGroupName=f"/aws/lambda/{NAMES['fn']}")
ok(iam.detach_role_policy, RoleName=NAMES["role"], PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
ok(iam.delete_role, RoleName=NAMES["role"])
ok(cw.delete_dashboards, DashboardNames=[NAMES["dash"]])
print("security groups ...")
for key in ("sg_ec2", "sg_alb"):
    for _ in range(12):
        g = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [NAMES[key]]}])["SecurityGroups"]
        if not g: break
        if ok(ec2.delete_security_group, GroupId=g[0]["GroupId"]) is not None: break
        time.sleep(10)
# --- verify
print("verifying ...")
def leftovers():
    out = []
    for r in tagging.get_paginator("get_resources").paginate(TagFilters=[{"Key": "project", "Values": ["costscale"]}]):
        out += [x["ResourceARN"] for x in r["ResourceTagMappingList"] if ":budget/" not in x["ResourceARN"]]
    # the tagging index lags: drop terminated instances and volumes that no longer exist
    live = []
    for arn in out:
        rid = arn.split("/")[-1]
        if ":instance/" in arn:
            st = [i["State"]["Name"] for rv in ec2.describe_instances(InstanceIds=[rid])["Reservations"] for i in rv["Instances"]]
            if st and st[0] != "terminated": live.append(arn)
        elif ":volume/" in arn:
            try:
                if ec2.describe_volumes(VolumeIds=[rid])["Volumes"]: live.append(arn)
            except Exception: pass
        else: live.append(arn)
    return live
left = None
for _ in range(20):
    left = leftovers()
    if not left: break
    time.sleep(15)   # tagging index is eventually consistent
direct = dict(asg=len(asg.describe_auto_scaling_groups()["AutoScalingGroups"]), alb=len(elb.describe_load_balancers()["LoadBalancers"]),
              instances=sum(len(r["Instances"]) for r in ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}])["Reservations"]))
print("direct check (should be 0):", direct)
if left or any(direct.values()): print("LEFTOVERS:", left); raise SystemExit(1)
STATE.unlink(missing_ok=True)
print("DOWN: nothing tagged project=costscale remains (budgets kept).")
