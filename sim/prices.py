"""Pull ap-south-1 prices from the AWS Price List API -> results/prices.json (value + retrieval date)."""
import json, datetime, boto3
pl = boto3.client("pricing", region_name="us-east-1")
REG = "ap-south-1"

def products(service, filters):
    f = [{"Type": "TERM_MATCH", "Field": k, "Value": v} for k, v in filters.items()]
    out, tok = [], None
    while True:
        r = pl.get_products(ServiceCode=service, Filters=f, MaxResults=100, **({"NextToken": tok} if tok else {}))
        out += [json.loads(x) for x in r["PriceList"]]
        tok = r.get("NextToken")
        if not tok: return out

def ondemand_usd(p):
    t = next(iter(p["terms"]["OnDemand"].values()))
    return [(d["description"], d["unit"], float(d["pricePerUnit"]["USD"])) for d in t["priceDimensions"].values()]

res = {"region": REG, "retrieved": datetime.date.today().isoformat(), "source": "AWS Price List API (get_products)"}
# Lambda
lam = products("AWSLambda", {"regionCode": REG})
rows = [(p["product"]["attributes"].get("group"), p["product"]["attributes"].get("usagetype"), d) for p in lam for d in ondemand_usd(p)]
res["lambda_raw"] = [(g, u, *d) for g, u, d in rows if g in ("AWS-Lambda-Duration", "AWS-Lambda-Requests")]
# EC2 t3.medium
ec2 = products("AmazonEC2", {"regionCode": REG, "instanceType": "t3.medium", "operatingSystem": "Linux",
                             "tenancy": "Shared", "preInstalledSw": "NA", "capacitystatus": "Used"})
res["ec2_t3_medium_raw"] = [d for p in ec2 for d in ondemand_usd(p)]
# Fargate
fg = products("AmazonECS", {"regionCode": REG})
res["fargate_raw"] = [(p["product"]["attributes"].get("usagetype"), *d) for p in fg for d in ondemand_usd(p)
                      if "Fargate" in p["product"]["attributes"].get("usagetype", "")]
json.dump(res, open("results/prices_raw.json", "w"), indent=1)
for k in ("lambda_raw", "ec2_t3_medium_raw", "fargate_raw"): print(k, res[k][:12])
