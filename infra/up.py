"""Create the CostScale stack in ap-south-1 (default VPC, no NAT/RDS). Everything tagged project=costscale.
ASG starts at 0 instances: idle cost is the ALB only (~$0.024/h)."""
import base64, io, json, time, urllib.request, zipfile
from awscommon import *

s = load()
ec2, elb, lam, iam, asg, cw, ssm = (c(x) for x in ("ec2", "elbv2", "lambda", "iam", "autoscaling", "cloudwatch", "ssm"))
vpc = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
subnets = [x["SubnetId"] for x in ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc]}, {"Name": "default-for-az", "Values": ["true"]}])["Subnets"]]
myip = urllib.request.urlopen("https://checkip.amazonaws.com").read().decode().strip()
s.update(vpc=vpc, subnets=subnets, my_ip=myip); save(s)
tagspec = lambda rt: [{"ResourceType": rt, "Tags": TAGS}]

def sg(name, desc, rules):
    ex = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [name]}, {"Name": "vpc-id", "Values": [vpc]}])["SecurityGroups"]
    if ex: return ex[0]["GroupId"]
    gid = ec2.create_security_group(GroupName=name, Description=desc, VpcId=vpc, TagSpecifications=tagspec("security-group"))["GroupId"]
    ec2.authorize_security_group_ingress(GroupId=gid, IpPermissions=rules); return gid

s["sg_alb"] = sg(NAMES["sg_alb"], "costscale alb (my ip only)", [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": f"{myip}/32", "Description": "laptop"}]}]); save(s)
s["sg_ec2"] = sg(NAMES["sg_ec2"], "costscale ec2 (from alb only)", [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "UserIdGroupPairs": [{"GroupId": s["sg_alb"]}]}]); save(s)

# --- Lambda
try: role_arn = iam.get_role(RoleName=NAMES["role"])["Role"]["Arn"]
except iam.exceptions.NoSuchEntityException:
    role_arn = iam.create_role(RoleName=NAMES["role"], Tags=TAGS, AssumeRolePolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}))["Role"]["Arn"]
    iam.attach_role_policy(RoleName=NAMES["role"], PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
    time.sleep(12)
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(ROOT / "app/work.py", "work.py"); z.write(ROOT / "app/lambda_handler.py", "lambda_handler.py")
try:
    fn = lam.get_function(FunctionName=NAMES["fn"])["Configuration"]
    lam.update_function_code(FunctionName=NAMES["fn"], ZipFile=buf.getvalue())
except lam.exceptions.ResourceNotFoundException:
    fn = lam.create_function(FunctionName=NAMES["fn"], Runtime="python3.12", Role=role_arn, Handler="lambda_handler.handler",
        Code={"ZipFile": buf.getvalue()}, MemorySize=1769, Timeout=30, Tags=tag_dict())
lam.get_waiter("function_active_v2").wait(FunctionName=NAMES["fn"])
fn_arn = lam.get_function(FunctionName=NAMES["fn"])["Configuration"]["FunctionArn"]; s["fn_arn"] = fn_arn; save(s)
try: lam.add_permission(FunctionName=NAMES["fn"], StatementId="alb", Action="lambda:InvokeFunction", Principal="elasticloadbalancing.amazonaws.com")
except lam.exceptions.ResourceConflictException: pass

# --- ALB + target groups
def find(f, *a, **k):
    try: return f(*a, **k)
    except Exception: return None
tg = find(elb.describe_target_groups, Names=[NAMES["tg_ec2"]])
if tg: tg_ec2 = tg["TargetGroups"][0]["TargetGroupArn"]
else:
    tg_ec2 = elb.create_target_group(Name=NAMES["tg_ec2"], Protocol="HTTP", Port=80, VpcId=vpc, TargetType="instance", HealthCheckPath="/health",
        HealthCheckIntervalSeconds=5, HealthCheckTimeoutSeconds=2, HealthyThresholdCount=2, UnhealthyThresholdCount=2, Tags=TAGS)["TargetGroups"][0]["TargetGroupArn"]
    elb.modify_target_group_attributes(TargetGroupArn=tg_ec2, Attributes=[{"Key": "deregistration_delay.timeout_seconds", "Value": "5"}])
tg = find(elb.describe_target_groups, Names=[NAMES["tg_lambda"]])
if tg: tg_lam = tg["TargetGroups"][0]["TargetGroupArn"]
else:
    tg_lam = elb.create_target_group(Name=NAMES["tg_lambda"], TargetType="lambda", Tags=TAGS)["TargetGroups"][0]["TargetGroupArn"]
    elb.register_targets(TargetGroupArn=tg_lam, Targets=[{"Id": fn_arn}])
s.update(tg_ec2=tg_ec2, tg_lambda=tg_lam); save(s)
a = find(elb.describe_load_balancers, Names=[NAMES["alb"]])
if a: alb = a["LoadBalancers"][0]
else:
    alb = elb.create_load_balancer(Name=NAMES["alb"], Subnets=subnets, SecurityGroups=[s["sg_alb"]], Scheme="internet-facing", Type="application", Tags=TAGS)["LoadBalancers"][0]
s.update(alb_arn=alb["LoadBalancerArn"], alb_dns=alb["DNSName"]); save(s)
ls = elb.describe_listeners(LoadBalancerArn=s["alb_arn"])["Listeners"]
fwd = {"Type": "forward", "ForwardConfig": {"TargetGroups": [{"TargetGroupArn": tg_ec2, "Weight": 0}, {"TargetGroupArn": tg_lam, "Weight": 999}]}}
if ls: s["listener_arn"] = ls[0]["ListenerArn"]
else: s["listener_arn"] = elb.create_listener(LoadBalancerArn=s["alb_arn"], Protocol="HTTP", Port=80, DefaultActions=[fwd], Tags=TAGS)["Listeners"][0]["ListenerArn"]
save(s)

# --- launch template + ASG
b64 = lambda p: base64.b64encode((ROOT / p).read_bytes()).decode()
ud = f"""#!/bin/bash
mkdir -p /opt/costscale && cd /opt/costscale
echo {b64('app/work.py')} | base64 -d > work.py
echo {b64('app/server.py')} | base64 -d > server.py
cat > /etc/systemd/system/costscale.service <<'EOT'
[Service]
WorkingDirectory=/opt/costscale
ExecStart=/usr/bin/python3 /opt/costscale/server.py 80
Restart=always
[Install]
WantedBy=multi-user.target
EOT
systemctl daemon-reload && systemctl enable --now costscale
"""
ami = ssm.get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")["Parameter"]["Value"]
lt_data = dict(ImageId=ami, InstanceType="t3.medium", SecurityGroupIds=[s["sg_ec2"]], Monitoring={"Enabled": True},
               UserData=base64.b64encode(ud.encode()).decode(), MetadataOptions={"HttpTokens": "required"},
               TagSpecifications=tagspec("instance") + tagspec("volume"))
if not find(ec2.describe_launch_templates, LaunchTemplateNames=[NAMES["lt"]]):
    ec2.create_launch_template(LaunchTemplateName=NAMES["lt"], LaunchTemplateData=lt_data, TagSpecifications=tagspec("launch-template"))
if not asg.describe_auto_scaling_groups(AutoScalingGroupNames=[NAMES["asg"]])["AutoScalingGroups"]:
    asg.create_auto_scaling_group(AutoScalingGroupName=NAMES["asg"], LaunchTemplate={"LaunchTemplateName": NAMES["lt"], "Version": "$Latest"},
        MinSize=0, MaxSize=8, DesiredCapacity=0, VPCZoneIdentifier=",".join(subnets), TargetGroupARNs=[tg_ec2],
        HealthCheckType="ELB", HealthCheckGracePeriod=60, DefaultCooldown=0,
        Tags=[{"Key": "project", "Value": "costscale", "PropagateAtLaunch": True}])
    asg.enable_metrics_collection(AutoScalingGroupName=NAMES["asg"], Granularity="1Minute")

# --- dashboard
def w(title, metric, x, y):
    return {"type": "metric", "x": x, "y": y, "width": 12, "height": 6, "properties": {"title": title, "region": REGION, "view": "timeSeries",
        "metrics": [[{"expression": f"SEARCH('{{CostScale,Arm}} MetricName=\"{metric}\"', 'Average', 60)", "id": "e1"}]]}}
dash = {"widgets": [w("Forecast (concurrency->rps)", "Forecast", 0, 0), w("Actual request rate (rps)", "Actual", 12, 0),
                    w("BaseCapacity (rps)", "BaseCapacity", 0, 6), w("ALB EC2 weight", "Weight", 12, 6), w("RunningCost ($)", "RunningCost", 0, 12),
    {"type": "metric", "x": 12, "y": 12, "width": 12, "height": 6, "properties": {"title": "ASG in-service instances", "region": REGION,
        "metrics": [["AWS/AutoScaling", "GroupInServiceInstances", "AutoScalingGroupName", NAMES["asg"]]], "stat": "Average", "period": 60}}]}
cw.put_dashboard(DashboardName=NAMES["dash"], DashboardBody=json.dumps(dash))
s["dashboard"] = NAMES["dash"]; s["up_time"] = time.time(); save(s)
print("UP. ALB:", s["alb_dns"], "(ASG=0, weights ec2=0/lambda=999)")
