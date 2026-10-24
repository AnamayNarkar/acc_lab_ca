"""Create AWS Budgets email alerts at $30/$60/$80 (idempotent). Usage: budgets.py EMAIL"""
import sys, boto3
email = sys.argv[1]
acct = boto3.client("sts").get_caller_identity()["Account"]
b = boto3.client("budgets", region_name="us-east-1")  # Budgets is a global service
for amt in (30, 60, 80):
    name = f"costscale-{amt}usd"
    try:
        b.create_budget(
            AccountId=acct,
            Budget={"BudgetName": name, "BudgetType": "COST", "TimeUnit": "MONTHLY",
                    "BudgetLimit": {"Amount": str(amt), "Unit": "USD"}},
            NotificationsWithSubscribers=[{
                "Notification": {"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN",
                                 "Threshold": 100, "ThresholdType": "PERCENTAGE"},
                "Subscribers": [{"SubscriptionType": "EMAIL", "Address": email}]}],
            ResourceTags=[{"Key": "project", "Value": "costscale"}])
        print("created", name)
    except b.exceptions.DuplicateRecordException:
        print("exists", name)
