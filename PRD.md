# Product Requirements Document

## Product Summary

Clutch is an AI code review and interview prep partner for junior engineers.
It reviews pasted code, a small uploaded repository, or a linked GitHub PR
against interview-grade clean-code expectations, then turns the findings into
realistic follow-up questions and practice interview sessions.

The project is primarily a portfolio piece for Applied AI Engineer internship
and new-grad applications. It is designed to show practical skill in retrieval,
structured LLM outputs, tool use, evals, guardrails, tracing, sandboxing, and
human-in-the-loop product judgment.

## Problem

Junior engineers often get feedback that is either too generic to act on or too
late to help them improve before interviews. Hiring managers and mentors can
spot recurring issues in code quickly, but that judgment is hard to scale into
structured practice: concrete findings, likely interviewer questions, and
progress over time.

Clutch closes that gap by producing:

- Specific code findings tied to clean-code principles.
- Interview follow-up questions derived from those findings.
- A live simulated interview flow.
- A feedback report with recurring issues and improvement tasks.

## Users

Primary user:

- A junior engineer preparing for internships or new-grad interviews.

Secondary users:

- A mentor, peer reviewer, or hiring-manager-style evaluator who wants to give
  structured feedback.
- The project author using this as an AI engineering portfolio artifact.

## Core Workflows

### 1. Pasted Code Review

The user pastes a function or small code snippet into the web UI, chooses
role context such as "backend intern", and submits it for review. The system
returns structured findings with severity, location, explanation, suggested
improvement, and citations to clean-code principles.

This is the first runnable workflow.

### 2. Small Repository or PR Review

The user links a GitHub repository or PR. The system fetches files or diffs
through a scoped MCP server, parses relevant code, and produces structured
findings. The v1 product remains read-only and never comments on or mutates the
source repository.

### 3. Interview Question Generation

The system converts findings into interviewer-style follow-up questions. The
questions should feel realistic: probing design decisions, tradeoffs,
maintainability, testing, and debugging habits.

### 4. Live Interview Simulation

The user answers questions in a multi-turn session. The system tracks the
conversation, adapts follow-ups, and eventually produces a structured feedback
report.

### 5. Progress Tracking

Across sessions, the system summarizes recurring issues, improvements, and
recommended next tasks so users can see whether their code review and interview
answers are improving.

## V1 Features

- Web dashboard with pasted-code input and review output.
- FastAPI backend exposing review and interview endpoints.
- LangGraph agent with tools for static review and clean-code retrieval.
- Tree-sitter based parsing for Python first, with room for more languages.
- Pydantic schemas for all API and LLM boundaries.
- Seeded clean-code/rubric knowledge base.
- Retrieval with citations: PostgreSQL full-text + pgvector hybrid when
  configured, with a no-service local fallback.
- GitHub fetch operations behind one MCP server.
- Follow-up question generation from findings.
- Text-based interview simulation.
- Feedback report and progress snapshot schemas.
- Prompt-injection guardrail tests for untrusted code/comments/README input.
- Privacy-reduced tracing, an eval harness, and CI regression gates before
  deployment.

## Out of Scope for V1

- DSA or LeetCode-specific coaching mode.
- Mutating a user's repository.
- Posting PR comments automatically.
- Voice-mode interviews.
- Multi-agent orchestration.
- Kubernetes, Kafka, Spark, Airflow, Neo4j, multiple vector databases,
  fine-tuning, or RL.
- Full production-grade auth and billing.

## Post-v1 Extension

### DSA / LeetCode Coaching Mode

After the v1 review, question generation, interview simulation, progress
tracking, eval, tracing, and deployment goals are complete, Clutch can add a
DSA coaching mode for coding-interview preparation.

In this mode, users paste a LeetCode-style problem and their attempted
solution. The system guides them toward the solution through hints and
reasoning questions, asks them to consider alternative approaches, gives
time/space complexity feedback, and recommends follow-up problems based on
weak patterns or a target company.

This mode is intentionally post-v1. It should extend the finished interview
readiness coach without becoming required for the initial two-month portfolio
deliverable.

## Functional Requirements

- Users can submit pasted code and receive a structured list of findings.
- Findings must include severity, category, explanation, evidence, suggested
  improvement, and citation fields.
- The backend must validate requests and responses with Pydantic models.
- The agent must ground clean-code advice in the knowledge base when a finding
  claims rubric support.
- The system must generate interview questions from findings.
- The interview flow must persist enough session state to support multi-turn
  follow-ups.
- GitHub operations must go through the MCP boundary for every repository and
  PR review.
- Any future repository-mutating capability must require explicit human
  approval before execution.

## Non-Functional Requirements

- Uploaded or pasted code is treated as untrusted input.
- Raw uploaded code must not be persisted or logged beyond what the current
  session requires.
- Secrets must come from environment variables locally and from managed secrets
  in cloud deployments.
- The system must provide privacy-reduced structured traces for model calls,
  tool calls, latency, token usage, and cost without including raw source,
  prompts, secrets, or interview answers.
- Evals must track retrieval quality, finding quality, citation faithfulness,
  hallucination rate, latency, tokens, and cost.
- The first build increments should be runnable locally without cloud
  dependencies.

### Retention and deletion

- In-memory sessions disappear when the process stops.
- Durable mode retains only derived review/interview/progress records and
  content hashes until the local database/volume or cloud environment is
  explicitly deleted. Raw submitted/repository code and raw interview answers
  are never durable records.
- A self-service profile deletion endpoint and a documented production
  retention window are required before a public account system launches. The
  current local-profile workflow is not presented as an account/data-retention
  product.

## Success Criteria

The project is successful when it can demonstrate:

- Paste or link code, then receive structured, cited findings.
- Generate realistic follow-up questions from those findings.
- Run a text interview turn and produce a structured feedback report.
- Show progress across at least two sessions.
- Demonstrate at least one prompt-injection test that fails safely.
- Show eval metrics and one model comparison table in the README.
- Run through CI and deploy through the prepared Neon → Render → Vercel path; keep the AWS path in `CLOUD.md` as unapplied future
  architecture evidence.

## Assumptions

- Python is the primary language for implementation and the first reviewed
  language.
- The public entry page should appear independently of backend startup. The
  interface supports fast navigation between review, interview, and progress.
- PostgreSQL with pgvector is enough for v1 retrieval and persistence.
- A single well-engineered LangGraph agent is preferable until evals prove a
  need for multi-agent orchestration.
- GitHub integration can start read-only and remain useful.

## Open Questions

- Which non-Python language should be supported second, if any?
- What minimum UI state is needed for progress tracking without creating heavy
  auth requirements too early?

Resolved implementation defaults from the 14-day sprint brief:

- Langfuse is the first tracing platform.
- `gpt-5.4-mini` is the initial OpenAI review model, configurable through
  `OPENAI_MODEL` so eval evidence can justify a change later.
- Deterministic baseline `2026-09-10.v6` uses a 120-item source-traceable corpus,
  15 review cases (including three multi-file repositories, clean negatives,
  and mixed signals), three injection cases, and three interview-to-feedback
  cases. A capped `gpt-5.4-mini` run now supplies real model evidence, but the
  bounded fixtures still do not establish general quality.
