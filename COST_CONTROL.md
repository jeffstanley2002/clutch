# Cost Control

Clutch targets a low student-budget deployment. Cost is a measured system
quality alongside accuracy and latency, not a cleanup task after launch.

## Guardrails

- Prefer the model, but expose deterministic/static, template, and rule-based
  fallbacks with literal provenance labels when no model key is configured.
- Bound submitted source, selected chunks, retrieved principles, output tokens,
  retries, and interview history before every model call.
- Retry invalid structured output once, then use the applicable labeled
  fallback.
- Cache embeddings and retrieval results only; never cache raw code, review
  evidence, interview answers, or full responses.
- Record model name, input/output tokens, estimated cost, latency, cache status,
  and fallback mode for each agent run.
- Reserve a conservative UTF-8-byte token bound before every completion or
  embedding request. Default per-call and UTC-daily ceilings are $0.10 and
  $1.00; Redis makes the daily reservation atomic across replicas.
- Reconcile successful reservations with reported token usage. If usage or the
  counter is unavailable, retain the conservative reservation; never allow a
  paid call when the pre-call counter is unavailable.
- Keep manual live-model evaluation on its own in-memory budget: at most $0.50
  per run and $0.10 per request by default. A missing key produces a zero-cost
  unavailable report; fallback or incomplete execution fails the command.

## Deployment Defaults

- Use Neon production, one free Render backend instance, and Streamlit
  Community Cloud for the first public demo. Redis remains optional.
- Prefer scheduled scale-down or teardown when the demo is not in use.
- Set AWS Budgets alerts before provisioning paid resources.
- Keep Terraform as the infrastructure source of truth and estimate the monthly
  total before apply.
- Redis is opt-in. A local correctness smoke measured ~111 ms cold versus
  ~8.6 ms after a retrieval-cache hit; gather a representative benchmark before
  treating that as a general latency or cost result.

## Required Comparisons

Use the same golden eval set when comparing:

- deterministic fallback versus the OpenAI path;
- vector-only versus hybrid retrieval;
- cold versus cached requests;
- candidate model configurations.

Report finding accuracy, citation faithfulness, latency, tokens, and estimated
cost per review together so cheaper behavior is not mistaken for better
behavior when quality regresses.

Run the capped comparison manually with:

```bash
python -m clutch.evals.live_model --compact
```

## Deployment Breakpoint

Before creating AWS resources, stop for confirmation of account, region,
credentials, acceptable monthly budget, ingress/TLS choices, and teardown
expectations. The Terraform module defaults ECS desired count to zero but still
models paid ALB, RDS, and ElastiCache resources. It has not been applied.

Deployment API-key auth and per-call/daily model spend ceilings are implemented
and tested locally. The capped `gpt-5.4-mini` baseline cost $0.028781 total and
$0.004797 per review; production corpus embeddings cost $0.00015972 and the
retrieval query batch cost $0.00001746. AWS remains blocked on the explicit
provisioning checkpoint; Render/Streamlit deployment is the remaining public
launch step.
