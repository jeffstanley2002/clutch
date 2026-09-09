#!/usr/bin/env bash
set -euo pipefail

endpoint="${AWS_ENDPOINT_URL:-http://localhost:4566}"
region="${AWS_REGION:-${AWS_DEFAULT_REGION:-ap-southeast-1}}"

curl -fsS "$endpoint/_localstack/health" >/dev/null
echo "LocalStack health endpoint is reachable."

if ! command -v aws >/dev/null 2>&1; then
  cat <<MSG
AWS CLI is not installed, so the AWS resource smoke was skipped.
After installing AWS CLI v2, run:

  AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=$region \\
    aws --endpoint-url=$endpoint ec2 describe-vpcs
  AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=$region \\
    aws --endpoint-url=$endpoint logs describe-log-groups
  AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=$region \\
    aws --endpoint-url=$endpoint secretsmanager list-secrets
MSG
  exit 0
fi

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="$region"
export AWS_REGION="$region"

echo "VPCs:"
aws --endpoint-url="$endpoint" ec2 describe-vpcs \
  --query "Vpcs[].VpcId" \
  --output table

echo "CloudWatch log groups:"
aws --endpoint-url="$endpoint" logs describe-log-groups \
  --query "logGroups[].logGroupName" \
  --output table

echo "Secrets:"
aws --endpoint-url="$endpoint" secretsmanager list-secrets \
  --query "SecretList[].Name" \
  --output table

echo "ECR/ECS are skipped by default; this LocalStack license returned 501 for both services."
