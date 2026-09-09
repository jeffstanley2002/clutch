#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${LOCALSTACK_AUTH_TOKEN:-}" ]]; then
  if [[ -f ".env.localstack" ]]; then
    set -a
    source ".env.localstack"
    set +a
  fi
fi

if [[ -z "${LOCALSTACK_AUTH_TOKEN:-}" ]]; then
  echo "LOCALSTACK_AUTH_TOKEN is not set. Export a rotated token in your shell; do not write it to the repo." >&2
  exit 1
fi

docker compose -f compose.localstack.yaml up -d localstack

echo "Waiting for LocalStack at http://localhost:4566 ..."
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:4566/_localstack/health" >/dev/null; then
    curl -fsS "http://localhost:4566/_localstack/info" || true
    echo
    echo "LocalStack is ready."
    exit 0
  fi
  sleep 2
done

echo "LocalStack did not become ready within 120 seconds." >&2
docker compose -f compose.localstack.yaml logs --tail=80 localstack >&2
exit 1
