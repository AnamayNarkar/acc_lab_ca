"""Lambda backend behind ALB (same logic as server.py)."""
import json
from work import do_work

def handler(event, context):
    q = event.get("queryStringParameters") or {}
    if event.get("path") == "/health":
        body = {"ok": True}
    else:
        ms = float(q.get("ms", 400)); cpu = float(q.get("cpu", 80))
        body = {"backend": "lambda", "took_ms": round(do_work(ms, cpu), 1)}
    return {"statusCode": 200, "statusDescription": "200 OK", "isBase64Encoded": False,
            "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}
