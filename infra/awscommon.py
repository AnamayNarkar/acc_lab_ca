import json, os
from pathlib import Path
import boto3
ROOT = Path(__file__).resolve().parent.parent
REGION = "ap-south-1"
STATE = ROOT / "results" / "cache" / "infra_state.json"
STATE.parent.mkdir(parents=True, exist_ok=True)
TAG = {"Key": "project", "Value": "costscale"}
TAGS = [TAG]
P = "costscale"
NAMES = dict(sg_alb=f"{P}-alb-sg", sg_ec2=f"{P}-ec2-sg", role=f"{P}-lambda-role", fn=f"{P}-fn", tg_ec2="costscale-tg-ec2",
             tg_lambda="costscale-tg-lambda", alb=f"{P}-alb", lt=f"{P}-lt", asg=f"{P}-asg", dash="CostScale")
def c(svc, region=REGION): return boto3.client(svc, region_name=region)
def load(): return json.loads(STATE.read_text()) if STATE.exists() else {}
def save(s): STATE.write_text(json.dumps(s, indent=1))
def tag_dict(): return {"project": "costscale"}
