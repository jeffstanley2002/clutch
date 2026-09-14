# Cloud Plan

## Purpose and status

This document owns deployment/infra decisions. Product requirements live in
`PRD.md`; application design lives in `ARCHITECTURE.md`.

The local container boundary and Terraform root module are implemented and
verified. Terraform has been formatted and validated without AWS credentials;
it has never been planned against an account or applied. Creating paid cloud
resources is an explicit user checkpoint.

The practical production path is Neon, Render, and Vercel. See
`docs/vercel-deployment.md` for the current Next.js deployment. Historical AWS
Streamlit configuration remains unapplied and must be migrated before use.
Neon is already migrated and seeded; only the two application deployments
remain. The AWS module remains useful as portfolio architecture evidence and as
a future migration path, but it should not be applied while the owner wants to
avoid AWS spend.

## Target AWS shape

- One VPC across two availability zones.
- Public ALB routes the Streamlit UI by default and FastAPI endpoint paths to a
  separate backend target group.
- Three ECS/Fargate services: Streamlit, FastAPI + agent, and read-only GitHub
  MCP. Streamlit reaches FastAPI and FastAPI reaches MCP through private Cloud
  Map DNS.
- ECS tasks use public subnets for low-cost outbound access but accept ingress
  only from the ALB or calling service security group. This avoids a NAT
  Gateway for the small portfolio deployment.
- RDS PostgreSQL is private, encrypted, RDS-password-managed, and supports the
  pgvector extension created by Alembic.
- Single-node ElastiCache Redis is private with encryption at rest and TLS in
  transit.
- Three immutable ECR repositories, CloudWatch log groups, ECS execution/task
  roles, and least-privilege secret access.
- AWS Budget forecasted/actual alerts are created before ALB/RDS/Redis.
- Optional ACM certificate enables HTTPS and HTTP redirect. A public deployment
  must use ACM; plain HTTP is only a scaffold/local-equivalent mode.

The agent remains inside FastAPI. Split it only when measured scaling or
operational evidence requires another deployable.

## Low-cost hosted target

Use this path for the next real public deployment unless the owner explicitly
re-opens AWS funding:

- Vercel hosts the Next.js project in `frontend/`. Server-only environment
  variables replace Streamlit secrets; configure Stytch `/api/auth/callback`.
- Render hosts the FastAPI backend.
- Neon project `holy-feather-79203801`, branch `production`, provides hosted
  PostgreSQL with pgvector for durable review, interview, progress, and the
  versioned knowledge corpus.
- Upstash or Render Redis can replace ElastiCache for cache/spend-counter
  behavior when Redis is required across multiple replicas; it is optional for
  the initial single-instance deployment.
- Secrets stay in each provider's secret manager/environment settings; no
  secrets are committed.

The provider-specific runbook is
[`docs/free-deployment.md`](docs/free-deployment.md), with a Render backend
blueprint in `render.yaml` and a post-deploy smoke helper in
`scripts/hosted_smoke.sh`. Runtime uses Neon's pooled URL; Alembic and
administrative seeding use its direct URL.

## Local Compose parity

`compose.yaml` runs pgvector Postgres, Redis, GitHub MCP, FastAPI, and Next.js
with health-gated dependencies. Migrations are explicit:

```bash
export CLUTCH_DB_PASSWORD=replace-with-a-local-only-password
docker compose build
docker compose up -d postgres redis github-mcp
docker compose run --rm backend alembic upgrade head
docker compose up -d backend frontend
```

All three images run as UID/GID 10001. The MCP transport binds loopback by
default and opts into all-interface binding only inside the container network,
with DNS-rebinding host checks enabled.

## LocalStack rehearsal

`compose.localstack.yaml` and `infra/localstack/terraform` provide a separate
AWS-emulation rehearsal path. This is intentionally not the production Terraform
root. It starts LocalStack Pro with `LOCALSTACK_AUTH_TOKEN` supplied from the
shell, points the AWS provider at `http://localhost:4566`, and creates local
VPC networking, Secrets Manager, IAM, and CloudWatch Logs by default. ECR and
ECS are optional flags for a LocalStack license tier that includes those
services.

The rehearsal catches provider/resource wiring mistakes without touching a real
AWS account. It does not prove ALB/RDS/ElastiCache parity and does not remove
the saved-plan approval checkpoint below.

Current LocalStack license coverage allows the default supported subset to
apply: VPC/subnet/security group, IAM, Secrets Manager, and CloudWatch Logs.
ECR and ECS returned LocalStack 501 license errors during testing, so they are
optional `enable_emulated_ecr` / `enable_emulated_ecs` flags.

```bash
export LOCALSTACK_AUTH_TOKEN=replace-with-rotated-token
scripts/localstack_up.sh
scripts/localstack_terraform.sh init
scripts/localstack_terraform.sh plan
scripts/localstack_terraform.sh apply
scripts/localstack_smoke.sh
```

## Terraform safety model

The root module is `infra/terraform`. It requires Terraform 1.16.x and locks
AWS provider 6.63.0. Remote state uses a separately created, private,
versioned S3 bucket and native S3 lockfile; credentials are environment/profile
inputs, never backend files committed to Git.

`service_desired_count` defaults to zero so tasks do not start before immutable
images and migrations are ready. An apply still creates paid ALB, RDS, and
ElastiCache resources, so zero tasks is not zero cost.

Before any AWS plan/apply, confirm:

1. AWS account and `ap-southeast-1` (or chosen region).
2. Budget email and acceptable monthly ceiling.
3. Narrow public ingress CIDR, ACM/domain plan, and API-key secret ARN.
4. Staging teardown time and production deletion/final-snapshot policy.
5. Credential/profile source and operator identity.
6. Per-call/daily model-spend ceilings appropriate for the approved budget.

## Secrets

- RDS creates and rotates its master password in Secrets Manager. ECS injects
  only the `password` JSON field; the application assembles the URL in memory.
- The required Clutch API key plus optional OpenAI, read-only GitHub, and
  Langfuse values are existing plaintext Secrets Manager ARNs supplied as
  sensitive deployment inputs.
- Secret ARNs may appear in Terraform state; secret values must not.
- Server-side Streamlit receives only the Clutch API key. The browser never
  receives it, and neither frontend layer receives GitHub, model, database, or
  Langfuse credentials.

## Approved deployment sequence

1. Run local quality, security, eval, image-build, Compose, and Terraform gates.
2. Create/version the S3 state bucket and initialize the reviewed backend.
3. Populate ignored tfvars, run a saved plan, and obtain explicit approval.
4. Apply with ECS desired count zero.
5. Push all three multi-platform images with the same immutable Git SHA tag.
6. Run the backend task once with `alembic upgrade head`.
7. Update `image_tag` and desired count to one; review/apply another saved plan.
8. Verify UI/API/MCP health, one synthetic review/interview/progress flow,
   Redis metrics, privacy-safe database/log/trace content, and rollback.
9. Record deployed SHA, eval result, plan summary, smoke evidence, owner, and
   teardown time.

CI currently checks code/evals/security, builds images without publishing, and
validates Terraform. ECR publication and ECS update intentionally remain absent
until the AWS checkpoint is approved.

## Observability and data handling

CloudWatch and Langfuse may capture request ID, endpoint/workflow, source hash,
language, line count, categories, citations, model, tokens, cost, cache status,
tool/retrieval timing, and safe error category. They must never receive raw
code, repository content, prompts, provider payloads, interview answers, or
secret values.

Neon or RDS stores derived review/interview/progress data and hashes. Redis
stores only hashed embedding/retrieval keys and knowledge-base values. No S3
artifact store is provisioned because v1 has no current non-sensitive artifact
requirement.

## Cost and rollback

- Budget alerts default to USD 30/month; this is an alert, not a hard cap.
- Staging uses one task/service, single-AZ small RDS, one Redis node, short log
  retention, and no NAT Gateway once enabled.
- Keep desired count zero until images are published; tear staging down when
  demo availability is unnecessary.
- ECS deployment circuit breakers roll back unhealthy task revisions.
- RDS staging skips final snapshot for cheap teardown; production requires a
  final snapshot and should enable deletion protection.
- Database rollback means restore from a tested snapshot and deploy the prior
  image/migration-compatible revision—not blindly downgrade schema in place.
