#!/usr/bin/env bash
set -euo pipefail

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-ap-southeast-1}"
export AWS_REGION="${AWS_REGION:-$AWS_DEFAULT_REGION}"
export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:4566}"

echo "AWS_REGION=$AWS_REGION"
echo "AWS_ENDPOINT_URL=$AWS_ENDPOINT_URL"
