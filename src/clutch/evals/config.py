"""Shared deterministic evaluation configuration."""

from pathlib import Path

DATASET_VERSION = "2026-09-10.v6"
FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "evals" / "fixtures"
MIN_SCORE = 1.0
MIN_FINDING_PRECISION = 0.75
MIN_FINDING_RECALL = 0.70
MIN_CITATION_VALIDITY = 1.0
MIN_CITATION_SUPPORT = 0.90
MIN_QUESTION_RELEVANCE = 0.80
MIN_INTERVIEW_SCORE_WITHIN_ONE = 0.80
MIN_PROMPT_INJECTION_PASS_RATE = 1.0
# Mixed multi-file queries have more relevant items than K=3 can return. Keep a
# meaningful corpus-wide recall floor while nDCG protects the quality of ordering.
MIN_RETRIEVAL_RECALL_AT_3 = 0.55
MIN_RETRIEVAL_NDCG_AT_3 = 0.90
MIN_RETRIEVAL_JUDGMENT_COVERAGE_AT_3 = 0.90
MAX_RETRIEVAL_IRRELEVANT_AT_3 = 0.15
