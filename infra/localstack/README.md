# LocalStack Deployment Harness

This folder is a local AWS-emulation harness for Clutch. It is deliberately
separate from `infra/terraform`, which remains the reviewed production AWS
module with remote-state and paid-resource safety checkpoints.

The LocalStack harness tests the deployment control plane locally:

- LocalStack Pro starts through `compose.localstack.yaml`.
- Terraform points every AWS provider endpoint at `http://localhost:4566`.
- Dummy AWS credentials are used only for the emulator.
- Secrets Manager values, IAM roles, a tiny VPC/network scaffold, and
  CloudWatch log groups are created in LocalStack by default.
- ECR repositories and ECS task/service descriptors are optional because they
  require a LocalStack license tier that includes ECR/ECS.
- ECS service desired count defaults to zero, so the first smoke test validates
  AWS resource creation without trying to run containers under emulated ECS.

Raw auth tokens never belong in this repository. Export
`LOCALSTACK_AUTH_TOKEN` in the shell that starts LocalStack, then rotate the
token if it has ever been pasted into chat, logs, or source control.
Alternatively, create an ignored `.env.localstack` file with:

```bash
LOCALSTACK_AUTH_TOKEN=replace-with-rotated-token
```

## Commands

```bash
export LOCALSTACK_AUTH_TOKEN="replace-with-rotated-token"
scripts/localstack_up.sh

scripts/localstack_terraform.sh init
scripts/localstack_terraform.sh plan
scripts/localstack_terraform.sh apply
scripts/localstack_smoke.sh
```

To try ECR/ECS on a LocalStack license that supports them:

```bash
scripts/localstack_terraform.sh plan -var=enable_emulated_ecr=true -var=enable_emulated_ecs=true
scripts/localstack_terraform.sh apply
```

Destroy the emulated resources with:

```bash
scripts/localstack_terraform.sh destroy
```

To remove persisted LocalStack emulator state, stop LocalStack and delete the
ignored `infra/localstack/volume/` folder.

## Tooling

Required locally:

- Docker Desktop with Compose v2.
- Terraform 1.16.x, or Docker access so `scripts/localstack_terraform.sh` can
  run `hashicorp/terraform:1.16.1`.

Optional:

- AWS CLI v2 for a richer smoke check. Without it, `localstack_smoke.sh` still
  verifies the LocalStack health endpoint and tells you which AWS CLI commands
  to run once installed.

## Scope

This is not a substitute for reviewing and applying the production AWS plan.
LocalStack is used here to catch Terraform/provider wiring mistakes early and
to practice the deployment flow without touching a real AWS account. The real
AWS plan in `infra/terraform` still needs review before any paid resources are
created.
