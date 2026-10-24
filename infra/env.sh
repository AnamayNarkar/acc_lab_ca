# source this file: maps the non-standard .env names to AWS vars. Never prints values.
set -a; . "$(dirname "${BASH_SOURCE[0]}")/../.env"; set +a
export AWS_ACCESS_KEY_ID="$AWS_ADMIN_IAM_USER_ACCES_KEY"
export AWS_SECRET_ACCESS_KEY="$AWS_ADMIN_IAM_USER_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION=ap-south-1
