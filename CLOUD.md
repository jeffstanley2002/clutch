# Cloud Plan

## Purpose

This document covers deployment and infrastructure only. Product requirements
live in `PRD.md`; system architecture lives in `ARCHITECTURE.md`.

## Target Cloud Shape

Clutch deploys to AWS using containers and managed data services:

- ECS/Fargate for the Streamlit UI container.
- ECS/Fargate for the FastAPI backend container.
- RDS PostgreSQL with pgvector for app data and embeddings.
- ElastiCache Redis for caching once caching is introduced.
- AWS Secrets Manager or SSM Parameter Store for secrets.
- S3 for non-sensitive generated artifacts if needed.
- CloudWatch for container logs and metrics.
- GitHub Actions for CI/CD.

The agent service should initially ship inside the FastAPI backend container.
Split it into a separate worker only if latency, scaling, or operational
evidence makes that worthwhile.

## Local Development

The first local setup should stay light:

- Run Streamlit locally.
- Run FastAPI locally.
- Use local environment variables from `.env`.
- Add Docker Compose when PostgreSQL, pgvector, or Redis become necessary.

Cloud dependencies should not block the first pasted-code review demo.

## Environments

### Local

- Developer machine.
- `.env` for local secrets.
- Local or containerized services.
- Test data only.

### Staging

- ECS service using staging secrets and staging database.
- Runs after CI passes.
- Used for deployment smoke tests and eval sanity checks.

### Production

- ECS service using production secrets and production database.
- Deployed only after tests and eval gates pass.
- No raw uploaded code stored in logs or traces.

## Secrets

Required secrets will eventually include:

- `OPENAI_API_KEY`.
- Tracing provider keys for Langfuse or Arize Phoenix.
- Database connection URL.
- Redis connection URL.
- GitHub token for read-only repository or PR fetches, if needed.

Rules:

- Never commit secrets.
- Keep `.env.example` with variable names but no secret values.
- Use AWS Secrets Manager or SSM Parameter Store in deployed environments.
- Scope GitHub credentials to read-only access.

## CI/CD

GitHub Actions should eventually run:

- Formatting check.
- Linting.
- Type checks.
- Unit tests.
- API integration tests.
- Retrieval tests.
- Prompt-regression tests.
- Prompt-injection guardrail tests.
- Agent eval suite.
- Docker build.

Deployment should be gated by tests and eval thresholds once the eval harness
exists.

## Deployment Flow

1. Merge or push to the deployment branch.
2. GitHub Actions runs checks and eval gates.
3. Build Docker images for Streamlit and FastAPI.
4. Push images to Amazon ECR.
5. Update ECS services.
6. Run health checks and a minimal smoke test.
7. Record deployment metadata in release notes or CI logs.

## Observability

Cloud logs and traces should capture:

- Request id.
- Endpoint.
- Latency.
- Error category.
- Model name.
- Token usage.
- Estimated cost.
- Tool-call timing.
- Retrieval document ids.

They should not capture raw uploaded code, private repository contents, or
secrets.

## Cost Controls

- Keep ECS service sizes small for v1.
- Use one PostgreSQL instance until usage justifies more.
- Introduce Redis only after a measured need.
- Track model cost per request.
- Cache embeddings and repeated retrieval once retrieval is active.
- Prefer staging resources that can be paused or scaled down.

## Open Decisions

- Choose Langfuse or Arize Phoenix for first tracing implementation.
- Decide whether the Streamlit UI and FastAPI backend share one domain or use
  separate service URLs.
- Decide initial RDS size and backup retention when deployment begins.
- Decide whether to use Terraform, AWS CDK, or manual setup for the first AWS
  deployment.
