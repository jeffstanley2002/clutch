# LocalStack Memory

## Current state

- `compose.localstack.yaml` starts `localstack/localstack-pro:latest` on
  loopback ports 4566 and 4510-4559, with `PERSISTENCE=1` by default.
- The auth token is never stored in the repo; export `LOCALSTACK_AUTH_TOKEN`
  before starting the container, or put it in ignored `.env.localstack`, and
  rotate it if it has been exposed.
- `terraform/` is a separate LocalStack-only control-plane harness. It points
  AWS provider endpoints at `http://localhost:4566`, uses dummy AWS
  credentials, and creates Secrets Manager secret versions, IAM roles/policies,
  a tiny VPC/network scaffold, and CloudWatch log groups by default.
  ECR/ECS are optional flags because this LocalStack license rejected both
  services with 501 license errors.
- Helper scripts:
  - `scripts/localstack_up.sh`
  - `scripts/localstack_terraform.sh`
  - `scripts/localstack_smoke.sh`
  - `scripts/localstack_env.sh`
- Last verified on 2026-09-09: LocalStack reported Pro edition, activated
  license, and healthy status. Terraform init/fmt/validate/plan/apply succeeded
  for the default supported subset. AWS CLI smoke listed emulated VPCs,
  `/ecs/clutch-localstack/*` log groups, and
  `clutch-localstack/clutch-api-key`.

## Decisions

- Keep this separate from `infra/terraform`; the production AWS module still
  owns ALB/RDS/Redis/Budgets/VPC and the paid-resource checkpoint.
- Default to no ECR/ECS resources on this license. If an upgraded LocalStack
  license enables those APIs, set `enable_emulated_ecr=true` and
  `enable_emulated_ecs=true`.
- When ECR is enabled, LocalStack ECR uses mutable, force-delete repositories so
  repeated local test runs are cheap to reset and do not model production
  immutability.

## Known gaps

- Terraform is not installed on the current PATH; Homebrew installation was
  blocked by an outdated Xcode requirement. The Terraform script now falls back
  to `hashicorp/terraform:1.16.1` through Docker, and that image runs
  successfully.
- AWS CLI is installed on the current PATH. LocalStack CLI Homebrew installation
  is also blocked by the outdated Xcode requirement, so use Compose plus AWS CLI.
- Running actual emulated ECS tasks requires a LocalStack license with ECS/ECR
  coverage.
