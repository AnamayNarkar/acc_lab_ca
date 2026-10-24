import json, datetime
from core import P
json.dump({"region": "ap-south-1", "retrieved": datetime.date.today().isoformat(), "source": "AWS Price List API",
           "values": P, "notes": "Lambda tier-1 duration price; Fargate x86 Linux; t3.medium Linux on-demand shared tenancy"},
          open(__import__("pathlib").Path(__file__).resolve().parent.parent / "results/prices.json", "w"), indent=1)
