"""Spend so far: Cost Explorer month-to-date by service (lags ~24h) + local estimate of running ALB hours."""
import datetime, time
from awscommon import *
ce = c("ce", "us-east-1"); today = datetime.date.today(); start = today.replace(day=1)
r = ce.get_cost_and_usage(TimePeriod={"Start": str(start), "End": str(today + datetime.timedelta(days=1))}, Granularity="MONTHLY",
                          Metrics=["UnblendedCost"], GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}])
tot = 0
for g in r["ResultsByTime"][0]["Groups"]:
    v = float(g["Metrics"]["UnblendedCost"]["Amount"]); tot += v
    if v: print(f"{g['Keys'][0]:45s} ${v:.4f}")
print(f"TOTAL month-to-date for the WHOLE account (Cost Explorer, may lag; includes anyone else using this account): ${tot:.4f}")
s = load()
if s.get("up_time"): print(f"stack up for {(time.time()-s['up_time'])/3600:.2f} h -> ALB ~ ${(time.time()-s['up_time'])/3600*0.0239:.3f} (+LCU)")
