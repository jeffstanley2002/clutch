#!/usr/bin/env bash
set -euo pipefail

api_url="${CLUTCH_HOSTED_API_URL:-}"
frontend_url="${CLUTCH_HOSTED_FRONTEND_URL:-}"
api_key="${CLUTCH_API_KEY:-}"

if [[ -z "$api_url" ]]; then
  echo "CLUTCH_HOSTED_API_URL is required." >&2
  exit 1
fi
if [[ -z "$frontend_url" ]]; then
  echo "CLUTCH_HOSTED_FRONTEND_URL is required." >&2
  exit 1
fi
if [[ -z "$api_key" ]]; then
  echo "CLUTCH_API_KEY is required for hosted non-health routes." >&2
  exit 1
fi

smoke_dir="$(mktemp -d "${TMPDIR:-/tmp}/clutch-hosted-smoke.XXXXXX")"
trap 'rm -rf -- "$smoke_dir"' EXIT
auth_header="X-Clutch-API-Key: $api_key"
profile_id="hosted-smoke-profile"

echo "Backend health"
curl --retry 3 --retry-delay 5 -fsS "$api_url/health" >/dev/null
echo "Frontend health"
curl --retry 3 --retry-delay 5 -fsS "$frontend_url/" >/dev/null
echo "Runtime diagnostics"
curl -fsS "$api_url/runtime/cache" -H "$auth_header" >/dev/null
curl -fsS "$api_url/runtime/spend" -H "$auth_header" >/dev/null

echo "AI pasted-code review"
curl -fsS -X POST "$api_url/review" \
  -H "Content-Type: application/json" \
  -H "$auth_header" \
  --data @- >"$smoke_dir/review.json" <<'JSON'
{
  "code": "def add_item(items=[]):\n    print(items)\n    items.append(1)\n    return items\n",
  "language": "python",
  "role_context": "backend intern",
  "session_id": "hosted-smoke"
}
JSON
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["mode"]=="model"; assert d["findings"] and d["questions"]; print("  model findings={} questions={}".format(len(d["findings"]),len(d["questions"])))' "$smoke_dir/review.json"

echo "Public GitHub bounded review"
curl -fsS -X POST "$api_url/review/github" \
  -H "Content-Type: application/json" \
  -H "$auth_header" \
  --data '{"source_url":"https://github.com/pypa/sampleproject","role_context":"backend intern","session_id":"hosted-github-smoke"}' \
  >"$smoke_dir/github.json"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); i=d["ingestion"]; assert i["files_included"]; assert d["review"]["mode"]=="model"; print("  included={} skipped={} truncated={}".format(len(i["files_included"]),i["skipped_file_count"],str(i["truncated"]).lower()))' "$smoke_dir/github.json"

echo "Interview assessment and feedback"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); json.dump({"review_session_id":d["request_id"],"profile_id":sys.argv[3],"role_context":"backend intern","questions":d["questions"]},open(sys.argv[2],"w"))' "$smoke_dir/review.json" "$smoke_dir/turn-request.json" "$profile_id"
curl -fsS -X POST "$api_url/interview/turn" \
  -H "Content-Type: application/json" -H "$auth_header" \
  --data-binary @"$smoke_dir/turn-request.json" >"$smoke_dir/turn.json"

for _ in 1 2 3 4 5; do
  completed="$(python3 -c 'import json,sys; print(str(json.load(open(sys.argv[1]))["completed"]).lower())' "$smoke_dir/turn.json")"
  if [[ "$completed" == "true" ]]; then
    break
  fi
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); json.dump({"interview_session_id":d["interview_session_id"],"answer":"I would explain the risk, choose a bounded fix, test repeated and failure behavior, and monitor the production boundary."},open(sys.argv[2],"w"))' "$smoke_dir/turn.json" "$smoke_dir/turn-request.json"
  curl -fsS -X POST "$api_url/interview/turn" \
    -H "Content-Type: application/json" -H "$auth_header" \
    --data-binary @"$smoke_dir/turn-request.json" >"$smoke_dir/turn.json"
done
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["completed"]; assert d["assessment"]; print("  completed turn={} assessment_origin={}".format(d["turn_number"],d["assessment"]["origin"]))' "$smoke_dir/turn.json"
interview_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["interview_session_id"])' "$smoke_dir/turn.json")"
curl -fsS "$api_url/interview/$interview_id/feedback" \
  -H "$auth_header" >"$smoke_dir/feedback.json"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["aggregation_label"].startswith("Rule-based report aggregation"); print("  feedback_origin={}".format(d["origin"]))' "$smoke_dir/feedback.json"

echo "Progress persistence"
curl -fsS -X POST "$api_url/progress/$profile_id/snapshots" \
  -H "$auth_header" >"$smoke_dir/progress-saved.json"
curl -fsS "$api_url/progress/$profile_id" \
  -H "$auth_header" >"$smoke_dir/progress-read.json"
python3 -c 'import json,sys; saved=json.load(open(sys.argv[1])); read=json.load(open(sys.argv[2])); assert saved["user_id"]==read["user_id"]; assert read["evidence_sessions"]; print("  evidence_sessions={}".format(len(read["evidence_sessions"])))' "$smoke_dir/progress-saved.json" "$smoke_dir/progress-read.json"

echo "Hosted smoke passed. Restart Render, rerun the progress GET, then inspect UI and Langfuse redaction manually."
