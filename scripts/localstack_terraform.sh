#!/usr/bin/env bash
set -euo pipefail

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-ap-southeast-1}"
export AWS_REGION="${AWS_REGION:-$AWS_DEFAULT_REGION}"
export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:4566}"

terraform_dir="infra/localstack/terraform"
command="${1:-plan}"
shift || true

run_terraform() {
  if command -v terraform >/dev/null 2>&1; then
    terraform -chdir="$terraform_dir" "$@"
    return
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "terraform is not installed and Docker is unavailable for the Terraform fallback." >&2
    exit 1
  fi

  docker run --rm \
    --network host \
    -e AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY \
    -e AWS_DEFAULT_REGION \
    -e AWS_REGION \
    -e AWS_ENDPOINT_URL \
    -v "$PWD/$terraform_dir:/workspace" \
    -w /workspace \
    hashicorp/terraform:1.16.1 "$@"
}

case "$command" in
  init)
    run_terraform init "$@"
    ;;
  fmt)
    run_terraform fmt -recursive "$@"
    ;;
  validate)
    run_terraform validate "$@"
    ;;
  plan)
    run_terraform plan -out=localstack.tfplan "$@"
    ;;
  apply)
    if [[ -f "$terraform_dir/localstack.tfplan" && "$#" -eq 0 ]]; then
      run_terraform apply localstack.tfplan
    else
      run_terraform apply "$@"
    fi
    ;;
  destroy)
    run_terraform destroy "$@"
    ;;
  output)
    run_terraform output "$@"
    ;;
  *)
    echo "Usage: $0 {init|fmt|validate|plan|apply|destroy|output} [terraform args...]" >&2
    exit 1
    ;;
esac
