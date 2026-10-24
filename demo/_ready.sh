# sourced by the demo scripts: loads the project credentials and allows this laptop's CURRENT public address.
# (curl is used to find the address, the same path the demo requests take; the address can change between runs.)
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
. infra/env.sh
_IP=$(curl -s --no-keepalive -m 8 https://checkip.amazonaws.com | tr -d '[:space:]')
_SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=costscale-alb-sg --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)
if [ -z "$_SG" ] || [ "$_SG" = "None" ]; then echo "No CostScale stack found. Run: make up"; return 1 2>/dev/null || exit 1; fi
if ! aws ec2 describe-security-groups --group-ids "$_SG" --query 'SecurityGroups[0].IpPermissions[].IpRanges[].CidrIp' --output text | tr '\t' '\n' | grep -qx "$_IP/32"; then
  aws ec2 authorize-security-group-ingress --group-id "$_SG" --protocol tcp --port 80 --cidr "$_IP/32" >/dev/null 2>&1 && echo "[ready] allowed your current address $_IP" && sleep 8
fi
