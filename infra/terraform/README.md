# Clutch Terraform

This root module models the AWS deployment without creating anything by
default. It provisions an AWS Budget, VPC, public ALB, three ECS/Fargate
services, ECR repositories, private RDS PostgreSQL, private TLS ElastiCache
Redis, Cloud Map service discovery, CloudWatch logs, and least-privilege
security groups.

## Safety breakpoint

Do not run `terraform apply` until the owner confirms the AWS account, region,
budget email and threshold, public ingress range, teardown expectations, and
recurring spend. Terraform is intentionally not installed or applied by the
application setup.

`service_desired_count` defaults to zero. This lets infrastructure and ECR be
reviewed before workloads start, but RDS, ElastiCache, and the ALB still incur
cost if applied.

`clutch_api_key_secret_arn` is mandatory before `service_desired_count` can be
greater than zero. The backend requires that key on every route except health;
server-side Streamlit supplies it on API calls. Redis shares the configured
per-call and UTC-daily paid-model reservations across backend tasks.

## Validation

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

CI runs these checks without AWS credentials and never runs plan or apply.

## Approved deployment sequence

1. Copy `terraform.tfvars.example` to an ignored `terraform.tfvars` and replace
   every placeholder.
2. Create a private S3 state bucket with versioning, then copy
   `backend.hcl.example` to an ignored `backend.hcl`.
3. Run `terraform init -backend-config=backend.hcl` and inspect a saved plan.
4. After explicit approval, apply with `service_desired_count = 0`.
5. Build multi-platform images, push the same immutable Git SHA tag to the
   three output ECR repositories, and run the backend task once with the
   command override `alembic upgrade head`.
6. Set `image_tag` to that SHA and `service_desired_count = 1`; inspect and
   apply a second saved plan.
7. Verify `/health`, `/_stcore/health`, one synthetic review, cache metrics,
   and privacy-safe logs before accepting the deployment.

The backend accepts database components separately so ECS can inject only the
RDS-managed `password` JSON field rather than constructing or storing a full
database URL in Terraform state.
