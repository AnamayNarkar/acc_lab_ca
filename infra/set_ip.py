"""Re-point the ALB security group at the laptop's current public IP (it changes on mobile/CGNAT networks)."""
import urllib.request
from awscommon import *
ec2 = c("ec2"); s = load(); ip = urllib.request.urlopen("https://checkip.amazonaws.com").read().decode().strip()
sg = s["sg_alb"]; cur = ec2.describe_security_groups(GroupIds=[sg])["SecurityGroups"][0]["IpPermissions"]
old = [r["CidrIp"] for p in cur for r in p.get("IpRanges", [])]
if f"{ip}/32" in old: print("ip ok", ip)
else:
    if cur: ec2.revoke_security_group_ingress(GroupId=sg, IpPermissions=cur)
    ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": f"{ip}/32", "Description": "laptop"}]}])
    s["my_ip"] = ip; save(s); print("ip updated", ip)
