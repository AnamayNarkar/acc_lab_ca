#!/usr/bin/env bash
# Preflight for the CostScale demo. Prints account id and ARN only; never prints keys.
cd "$(dirname "$0")/.." || exit 1
ok(){ echo "  [ OK ] $*"; }; bad(){ echo "  [FAIL] $*"; FAIL=1; }; FAIL=0
echo "== credentials"
[ -f .env ] && ok ".env present" || bad ".env missing"
. infra/env.sh 2>/dev/null
[ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ] && ok "credentials mapped (values not shown)" || bad "credential variables empty (check names in .env)"
[ "$AWS_DEFAULT_REGION" = "ap-south-1" ] && ok "region ap-south-1" || bad "region is not ap-south-1"
IDENT=$(aws sts get-caller-identity --query '[Account,Arn]' --output text 2>&1) && ok "sts: $IDENT" || bad "sts failed: $(echo "$IDENT" | head -1 | cut -c1-120)"
echo "== service access (needs the SCP RegionFloor edit that allows ap-south-1)"
aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text >/dev/null 2>&1 && ok "EC2" || bad "EC2 denied"
aws lambda get-account-settings >/dev/null 2>&1 && ok "Lambda" || bad "Lambda denied"
aws elbv2 describe-load-balancers >/dev/null 2>&1 && ok "ELBv2" || bad "ELBv2 denied"
echo "== project files"
for f in results/calibration.json results/sim_results.json results/forecast_results.json results/live_results.json results/cache/forecaster.pkl data/processed/inv.npy; do
  [ -f "$f" ] && ok "$f" || bad "$f missing"; done
[ -x .venv/bin/python ] && ok "venv" || bad "venv missing"
echo "== what is running now"
# only CostScale's own resources are counted (the account may be shared; never touch anyone else's)
N_ASG=$(aws autoscaling describe-auto-scaling-groups --query "length(AutoScalingGroups[?starts_with(AutoScalingGroupName,'costscale')])" --output text 2>/dev/null)
N_ALB=$(aws elbv2 describe-load-balancers --query "length(LoadBalancers[?starts_with(LoadBalancerName,'costscale')])" --output text 2>/dev/null)
N_EC2=$(aws ec2 describe-instances --filters Name=tag:project,Values=costscale Name=instance-state-name,Values=pending,running --query 'length(Reservations[].Instances[])' --output text 2>/dev/null)
echo "  ASGs=$N_ASG  load balancers=$N_ALB  running instances=$N_EC2  (ASGs/instances at 0 = no servers; a load balancer count above 0 means the ALB is still billing about $0.024/h until make down)"
echo "== spend so far (Cost Explorer lags about a day)"
.venv/bin/python infra/cost.py 2>&1 | grep -v Warning | tail -6
echo "== laptop public IP (the ALB security group must contain it; the load generator adds it automatically)"
curl -s -m 5 https://checkip.amazonaws.com || echo "  could not reach checkip"
[ $FAIL -eq 0 ] && echo "PREFLIGHT PASSED" || { echo "PREFLIGHT FAILED - fix the [FAIL] lines above"; exit 1; }
