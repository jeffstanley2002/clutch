# Scripts memory

- Python quality/security/eval tools remain the backend gates. Next.js adds a
  separate frontend job in `.github/workflows/ci.yml`.
- `hosted_smoke.sh` checks the Vercel frontend at `/` (not the retired Streamlit
  health route), then exercises the existing backend with the deployment key.
  It performs real paid model calls when run against a configured backend;
  do not treat it as a zero-cost local validation command.
- Hosted authenticated browser validation is separate: see
  `docs/vercel-deployment.md`. The smoke script does not verify Stytch login.
