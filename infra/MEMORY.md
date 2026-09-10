# Infrastructure Memory

## Current state

- `compose.yaml`: pgvector Postgres, Redis, GitHub MCP, FastAPI, and Streamlit
  with health-gated startup.
- `compose.localstack.yaml`: LocalStack Pro gateway for AWS API emulation,
  reading `LOCALSTACK_AUTH_TOKEN` from the shell and persisting ignored state
  under `infra/localstack/volume/`.
- `backend/Dockerfile`, `frontend/Dockerfile`, and
  `docker/github-mcp.Dockerfile`: pinned Python base, UID/GID 10001.
- `terraform/`: AWS Budget, VPC/subnets/security groups, ECR, ECS/Fargate, ALB,
  Cloud Map, RDS, TLS ElastiCache, CloudWatch, managed-secret IAM, and outputs.
- `localstack/terraform`: separate local-only Terraform harness for emulated
  VPC networking, Secrets Manager, IAM, and CloudWatch Logs. ECR/ECS resources
  are optional flags because the current LocalStack license does not include
  those services.

All three images were rebuilt on 2026-09-09. The full Compose stack migrated,
all five services became healthy, and review/interview/feedback/progress passed
through real HTTP/UI boundaries. Terraform was formatted and validated with
Terraform 1.16.x and AWS provider 6.63.0; it was not planned against an account
or applied.

LocalStack was started successfully on 2026-09-09 with an activated Pro license.
The default local harness applied the supported subset: VPC/subnet/security
group, IAM role/policy, Secrets Manager API key, and CloudWatch log groups.
ECR and ECS returned LocalStack 501 license errors, so they remain optional
flags rather than default resources.

## Decisions

- Alembic runs as an explicit one-off task.
- ECS desired count defaults to zero; immutable Git SHA tags are expected.
- ECS tasks use public subnets only for low-cost outbound access, but ingress is
  security-group restricted; RDS/Redis remain in isolated data subnets.
- Streamlit reaches FastAPI via private Cloud Map; FastAPI reaches private MCP;
  the ALB independently exposes UI and API routes.
- ECS cannot start public services without a Secrets Manager API-key ARN. The
  key is injected into backend and server-side frontend only. Paid calls reserve
  against configurable $0.10 per-call/$1.00 daily defaults in shared Redis.
- Budget creation is a dependency of paid ALB/RDS/Redis resources.
- LocalStack is a control-plane rehearsal, not a replacement for the production
  AWS saved-plan/apply checkpoint.
- For near-term public deployment, prefer Neon/Render/Streamlit Community Cloud
  over AWS to avoid AWS spend. Keep AWS Terraform as architecture evidence and
  future migration material.
- `docs/free-deployment.md`, `render.yaml`, and `scripts/hosted_smoke.sh`
  document the already-prepared Neon data layer followed by Render backend and
  Streamlit Cloud UI deployment. The runbook maps every hosted secret to its
  provider, distinguishes pooled runtime from direct admin database URLs, and
  keeps Streamlit's `CLUTCH_*` settings above `[auth]` so TOML parses them at the
  root.
- Local app runtime can run without app containers: keep Docker Postgres/Redis
  and LocalStack up, then run MCP, FastAPI, and Streamlit from `.venv`.

## Known gaps / checkpoint

- Do not apply until the user confirms AWS account, region, budget email and
  ceiling, ingress range, credentials, and teardown policy.
- Neon production migration/seed is verified. Render backend deploy, Streamlit
  Community Cloud UI deploy, hosted smoke, AWS staging plan/cost estimate, ECR
  push, migration task, and rollback rehearsal remain unverified.
- Terraform is not installed on PATH because Homebrew Terraform is blocked by
  outdated Xcode; use the Docker fallback in `scripts/localstack_terraform.sh`.
- LocalStack cannot currently rehearse ECR/ECS without a higher license tier.
