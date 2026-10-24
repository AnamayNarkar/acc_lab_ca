#!/usr/bin/env bash
# One demo request through the load balancer.
. "$(dirname "$0")/_ready.sh" || exit 1
URL="http://$(.venv/bin/python -c "import json;print(json.load(open('results/cache/infra_state.json'))['alb_dns'])")/work?ms=400&cpu=80"
curl -sS --retry 3 --retry-delay 2 --retry-connrefused -m 15 "$URL"; echo
