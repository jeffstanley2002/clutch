# Infrastructure Memory

## Current state

- `compose.yaml`: pgvector Postgres, Redis, GitHub MCP, FastAPI, and Streamlit
  with health-gated startup.
- `backend/Dockerfile`, `frontend/Dockerfile`, and
  `docker/github-mcp.Dockerfile`: pinned Python base, UID/GID 10001.
- `terraform/`: AWS Budget, VPC/subnets/security groups, ECR, ECS/Fargate, ALB,
  Cloud Map, RDS, TLS ElastiCache, CloudWatch, managed-secret IAM, and outputs.

All three images built locally. The full Compose stack migrated and passed
health/review/persistence/cache smoke checks. Terraform was formatted and
validated with Terraform 1.16.1 and AWS provider 6.63.0; it was not planned
against an account or applied.

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

## Known gaps / checkpoint

- Do not apply until the user confirms AWS account, region, budget email and
  ceiling, ingress range, credentials, and teardown policy.
- Staging plan/cost estimate, ECR push, migration task, deployment smoke, and
  rollback rehearsal remain unverified.
