"""Build Clutch's versioned, source-traceable 120-item knowledge corpus."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

CORPUS_PATH = Path(__file__).parents[1] / "src/clutch/knowledge_base/corpus.json"
CORPUS_VERSION = "2026-09-09.v1"
CATEGORIES = (
    "maintainability",
    "readability",
    "correctness",
    "testing",
    "design",
    "security",
)

SOURCE_FAMILIES = {
    "docs.python.org": "python_docs",
    "peps.python.org": "python_pep",
    "cheatsheetseries.owasp.org": "owasp_cheat_sheet",
    "docs.pytest.org": "pytest_docs",
    "google.github.io": "google_engineering_practices",
}

GOOGLE_REVIEW = "https://google.github.io/eng-practices/review/reviewer/looking-for.html"
SMALL_CLS = "https://google.github.io/eng-practices/review/developer/small-cls.html"
CL_DESCRIPTIONS = (
    "https://google.github.io/eng-practices/review/developer/cl-descriptions.html"
)

REFERENCE_REPLACEMENTS: dict[str, tuple[str, str]] = {
    "seed.clean_code.explicit_incomplete_work": (
        "Google Engineering Practices — Comments",
        f"{GOOGLE_REVIEW}#comments",
    ),
    "seed.clean_code.small_reviewable_units": (
        "Google Engineering Practices — Why Write Small CLs?",
        f"{SMALL_CLS}#small-cls",
    ),
    "seed.clean_code.single_source_of_behavior": (
        "Google Engineering Practices — Design",
        f"{GOOGLE_REVIEW}#design",
    ),
    "seed.clean_code.externalized_configuration": (
        "Python os — os.environ",
        "https://docs.python.org/3/library/os.html#os.environ",
    ),
    "seed.clean_code.compatible_public_versions": (
        "Python warnings — Updating code for new dependency versions",
        "https://docs.python.org/3/library/warnings.html#updating-code-for-new-versions-of-dependencies",
    ),
    "seed.clean_code.executable_entry_points": (
        "Python __main__ — Idiomatic Usage",
        "https://docs.python.org/3/library/__main__.html#idiomatic-usage",
    ),
}

ITEM_PATCHES: dict[str, dict[str, object]] = {
    "seed.clean_code.externalized_configuration": {
        "title": "Read deployment configuration through explicit interfaces",
        "summary": "Process environment mappings provide deployment-specific configuration without embedding those values in program source.",
        "guidance": "Centralize reads, validate required values at startup, and inject dependencies where tests need controlled configuration.",
        "tags": ["configuration", "environment", "deployment", "startup"],
    },
    "seed.rubric.maintainable_change_scope": {
        "tags": ["rubric", "maintainability", "scope", "todo", "fixme", "incomplete"],
    },
    "seed.clean_code.allowlist_validation": {
        "tags": ["validation", "allowlist", "input", "boundary", "security", "sql", "identifier"],
    },
    "seed.rubric.security_trust_boundary": {
        "tags": ["rubric", "security", "trust", "boundary", "sql", "query", "untrusted", "parameter", "binding"],
    },
}

URL_OVERRIDES = {
    "https://docs.python.org/3/howto/logging.html": (
        "https://docs.python.org/3/howto/logging.html#logging-basic-tutorial"
    ),
    "https://docs.python.org/3/library/contextlib.html": (
        "https://docs.python.org/3/library/contextlib.html#utilities"
    ),
    "https://peps.python.org/pep-0257/": (
        "https://peps.python.org/pep-0257/#what-is-a-docstring"
    ),
    "https://docs.python.org/3/library/unittest.html": (
        "https://docs.python.org/3/library/unittest.html#basic-example"
    ),
    "https://docs.python.org/3/library/warnings.html": (
        "https://docs.python.org/3/library/warnings.html#warning-categories"
    ),
    "https://peps.python.org/pep-0484/": (
        "https://peps.python.org/pep-0484/#abstract"
    ),
    "https://peps.python.org/pep-0498/": (
        "https://peps.python.org/pep-0498/#abstract"
    ),
    "https://peps.python.org/pep-0020/": (
        "https://peps.python.org/pep-0020/#the-zen-of-python"
    ),
    "https://docs.python.org/3/library/decimal.html": (
        "https://docs.python.org/3/library/decimal.html#decimal-objects"
    ),
    "https://docs.python.org/3/library/copy.html": (
        "https://docs.python.org/3/library/copy.html#module-copy"
    ),
    "https://docs.python.org/3/library/dataclasses.html": (
        "https://docs.python.org/3/library/dataclasses.html#module-dataclasses"
    ),
    "https://docs.python.org/3/library/enum.html": (
        "https://docs.python.org/3/library/enum.html#module-enum"
    ),
    "https://docs.python.org/3/library/abc.html": (
        "https://docs.python.org/3/library/abc.html#module-abc"
    ),
    "https://docs.python.org/3/library/secrets.html": (
        "https://docs.python.org/3/library/secrets.html#module-secrets"
    ),
    "https://docs.python.org/3/library/itertools.html": (
        "https://docs.python.org/3/library/itertools.html#itertools-recipes"
    ),
    "https://docs.python.org/3/library/collections.abc.html": (
        "https://docs.python.org/3/library/collections.abc.html#collections-abstract-base-classes"
    ),
    "https://docs.pytest.org/en/stable/how-to/parametrize.html": (
        "https://docs.pytest.org/en/stable/how-to/parametrize.html#pytest-mark-parametrize-parametrizing-test-functions"
    ),
    "https://docs.pytest.org/en/stable/how-to/parametrize.html#parametrizing-test-functions": (
        "https://docs.pytest.org/en/stable/how-to/parametrize.html#pytest-mark-parametrize-parametrizing-test-functions"
    ),
    "https://docs.pytest.org/en/stable/how-to/tmp_path.html": (
        "https://docs.pytest.org/en/stable/how-to/tmp_path.html#the-tmp-path-fixture"
    ),
    "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html": (
        "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html#primary-defenses"
    ),
    "https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html": (
        "https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html#allowlist-vs-denylist"
    ),
    "https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html": (
        "https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#password-hashing-algorithms"
    ),
    "https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html": (
        "https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html#application-layer"
    ),
    "https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html": (
        "https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html#file-upload-protection"
    ),
    "https://docs.python.org/3/library/unittest.html#testing-for-exceptions-warnings-and-log-messages": (
        "https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertRaises"
    ),
}

NEW_ITEMS: list[dict[str, object]] = [
    {
        "id": "seed.clean_code.informative_change_context",
        "title": "Record why a change exists",
        "category": "maintainability",
        "summary": "Change descriptions should preserve the problem, rationale, and relevant tradeoffs for future maintainers.",
        "guidance": "Ask whether someone reading history later could understand why the implementation and its constraints were chosen.",
        "tags": ["history", "rationale", "tradeoff", "change", "maintenance"],
        "item_type": "reference",
        "roles": ["general", "backend", "platform"],
        "seniority_levels": ["intern", "junior", "mid"],
        "citation": {"title": "Google Engineering Practices — Body is Informative", "url": f"{CL_DESCRIPTIONS}#informative"},
    },
    {
        "id": "seed.clean_code.focused_change_scope",
        "title": "Keep changes focused and independently reviewable",
        "category": "maintainability",
        "summary": "A self-contained change that addresses one concern is easier to understand, test, merge, and reverse.",
        "guidance": "Prefer a sequence of working increments whose implications can each be reviewed without hidden follow-up work.",
        "tags": ["scope", "change", "review", "rollback", "increment"],
        "item_type": "reference",
        "roles": ["general"],
        "seniority_levels": ["intern", "junior", "mid"],
        "citation": {"title": "Google Engineering Practices — What is Small?", "url": f"{SMALL_CLS}#what-is-small"},
    },
    {
        "id": "seed.clean_code.reviewable_names",
        "title": "Choose names that communicate behavior",
        "category": "readability",
        "summary": "A useful name communicates what an item does without becoming difficult to scan.",
        "guidance": "Evaluate names in their calling context and prefer domain meaning over implementation shorthand.",
        "tags": ["name", "naming", "domain", "readability", "handoff"],
        "item_type": "reference",
        "roles": ["general"],
        "seniority_levels": ["intern", "junior", "mid"],
        "citation": {"title": "Google Engineering Practices — Naming", "url": f"{GOOGLE_REVIEW}#naming"},
    },
    {
        "id": "seed.clean_code.comments_explain_why",
        "title": "Use comments for reasoning the code cannot express",
        "category": "readability",
        "summary": "Comments are most useful when they explain intent or constraints rather than narrating straightforward operations.",
        "guidance": "Simplify unclear code first, then keep comments that preserve decisions, caveats, or non-obvious algorithms.",
        "tags": ["comment", "why", "intent", "constraint", "readability"],
        "item_type": "reference",
        "roles": ["general"],
        "seniority_levels": ["intern", "junior", "mid"],
        "citation": {"title": "Google Engineering Practices — Comments", "url": f"{GOOGLE_REVIEW}#comments"},
    },
    {
        "id": "seed.clean_code.review_user_edge_cases",
        "title": "Review functionality from the user's boundary",
        "category": "correctness",
        "summary": "Correctness review should test intended behavior against user impact, edge cases, and concurrency risks.",
        "guidance": "State the observable contract and search for inputs or interleavings that violate it before accepting the happy path.",
        "tags": ["edge", "user", "contract", "concurrency", "correctness"],
        "item_type": "reference",
        "roles": ["general", "backend"],
        "seniority_levels": ["intern", "junior", "mid"],
        "citation": {"title": "Google Engineering Practices — Functionality", "url": f"{GOOGLE_REVIEW}#functionality"},
    },
    {
        "id": "seed.clean_code.bounded_async_timeout",
        "title": "Bound asynchronous waiting",
        "category": "correctness",
        "summary": "A timeout makes an asynchronous wait's cancellation and failure boundary explicit.",
        "guidance": "Choose a timeout at the owning boundary and handle timeout or cancellation without leaving partial work behind.",
        "tags": ["async", "timeout", "cancel", "failure", "boundary"],
        "item_type": "reference",
        "roles": ["backend", "platform"],
        "seniority_levels": ["junior", "mid"],
        "citation": {"title": "Python asyncio — Timeouts", "url": "https://docs.python.org/3/library/asyncio-task.html#timeouts"},
    },
    {
        "id": "seed.clean_code.pytest_exception_context",
        "title": "Assert the relevant exception contract",
        "category": "testing",
        "summary": "Exception tests should assert the expected exception type and, when meaningful, the relevant error context.",
        "guidance": "Keep the raising operation narrow so an unrelated earlier failure cannot make the test pass accidentally.",
        "tags": ["pytest", "raises", "exception", "contract", "assertion"],
        "item_type": "reference",
        "roles": ["general", "backend"],
        "seniority_levels": ["intern", "junior", "mid"],
        "citation": {"title": "pytest — Assertions about expected exceptions", "url": "https://docs.pytest.org/en/stable/how-to/assert.html#assertions-about-expected-exceptions"},
    },
    {
        "id": "seed.clean_code.mock_interaction_contract",
        "title": "Assert only meaningful collaborator interactions",
        "category": "testing",
        "summary": "Mock assertions can verify a collaborator boundary when the interaction itself is part of the behavior contract.",
        "guidance": "Avoid mirroring implementation detail; assert calls only where their arguments or count are observable obligations.",
        "tags": ["mock", "call", "contract", "interaction", "test-double"],
        "item_type": "reference",
        "roles": ["general", "backend"],
        "seniority_levels": ["intern", "junior", "mid"],
        "citation": {"title": "Python unittest.mock — assert_called_once_with", "url": "https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock.assert_called_once_with"},
    },
    {
        "id": "seed.clean_code.avoid_speculative_generality",
        "title": "Avoid complexity for hypothetical requirements",
        "category": "design",
        "summary": "Generalization without a present requirement increases reading and modification cost before its value is known.",
        "guidance": "Solve the current requirement with the smallest coherent design and name the evidence that would justify extension.",
        "tags": ["complexity", "over-engineering", "generality", "requirement", "design"],
        "item_type": "reference",
        "roles": ["general", "backend", "platform"],
        "seniority_levels": ["intern", "junior", "mid", "senior"],
        "citation": {"title": "Google Engineering Practices — Complexity", "url": f"{GOOGLE_REVIEW}#complexity"},
    },
    {
        "id": "seed.clean_code.review_system_context",
        "title": "Evaluate a change in its system context",
        "category": "design",
        "summary": "A locally plausible change can still weaken the surrounding module or system through accumulated complexity.",
        "guidance": "Review the whole owner, neighboring behavior, and system-level code health rather than only the changed lines.",
        "tags": ["context", "system", "cohesion", "complexity", "design"],
        "item_type": "reference",
        "roles": ["general", "backend", "platform"],
        "seniority_levels": ["junior", "mid", "senior"],
        "citation": {"title": "Google Engineering Practices — Context", "url": f"{GOOGLE_REVIEW}#context"},
    },
    {
        "id": "seed.clean_code.secret_lifecycle_controls",
        "title": "Control the complete secret lifecycle",
        "category": "security",
        "summary": "Secrets need controlled creation, storage, distribution, rotation, revocation, and expiration.",
        "guidance": "Trace which identities can access a secret, where it can leak, and how compromise can be contained without source changes.",
        "tags": ["secret", "credential", "rotation", "revocation", "lifecycle"],
        "item_type": "reference",
        "roles": ["backend", "platform"],
        "seniority_levels": ["intern", "junior", "mid"],
        "citation": {"title": "OWASP Secrets Management Cheat Sheet — Introduction", "url": "https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html#1-introduction"},
    },
    {
        "id": "seed.clean_code.authentication_error_boundaries",
        "title": "Keep authentication failures non-enumerating",
        "category": "security",
        "summary": "Authentication errors should not reveal whether a specific account, secret, or factor was valid.",
        "guidance": "Use consistent public errors while retaining privacy-safe internal diagnostics for operators.",
        "tags": ["authentication", "error", "enumeration", "identity", "boundary"],
        "item_type": "reference",
        "roles": ["backend", "platform"],
        "seniority_levels": ["intern", "junior", "mid"],
        "citation": {"title": "OWASP Authentication Cheat Sheet — Authentication Responses", "url": "https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#authentication-responses"},
    },
    {
        "id": "seed.question.maintainability_history",
        "title": "Explain the maintenance history",
        "category": "maintainability",
        "summary": "Ask what a future maintainer must learn from the change record that code alone cannot show.",
        "guidance": "Require a concrete rationale, constraint, and known limitation rather than a generic description.",
        "tags": ["question", "history", "rationale", "maintainability"],
        "item_type": "question_bank",
        "roles": ["general"],
        "seniority_levels": ["intern", "junior"],
        "derive_from": "seed.clean_code.informative_change_context",
    },
    {
        "id": "seed.question.maintainability_split",
        "title": "Split the change safely",
        "category": "maintainability",
        "summary": "Ask how to divide the work into reviewable increments without leaving the system broken between steps.",
        "guidance": "Look for coherent boundaries, related tests, dependency order, and rollback safety.",
        "tags": ["question", "scope", "increment", "rollback", "maintainability"],
        "item_type": "question_bank",
        "roles": ["general"],
        "seniority_levels": ["intern", "junior"],
        "derive_from": "seed.clean_code.focused_change_scope",
    },
    {
        "id": "seed.question.readability_name_context",
        "title": "Defend a name in calling context",
        "category": "readability",
        "summary": "Ask the candidate to compare a proposed name at its declaration and at representative call sites.",
        "guidance": "A strong answer connects the name to domain behavior and scanning cost.",
        "tags": ["question", "naming", "context", "readability"],
        "item_type": "question_bank",
        "roles": ["general"],
        "seniority_levels": ["intern", "junior"],
        "derive_from": "seed.clean_code.reviewable_names",
    },
    {
        "id": "seed.question.readability_comment_why",
        "title": "Separate useful intent from narration",
        "category": "readability",
        "summary": "Ask which comment should be removed, converted into clearer code, or retained as design rationale.",
        "guidance": "Require the candidate to explain what information cannot be expressed by names and structure alone.",
        "tags": ["question", "comment", "intent", "readability"],
        "item_type": "question_bank",
        "roles": ["general"],
        "seniority_levels": ["intern", "junior"],
        "derive_from": "seed.clean_code.comments_explain_why",
    },
    {
        "id": "seed.question.correctness_user_boundary",
        "title": "Find a user-visible counterexample",
        "category": "correctness",
        "summary": "Ask for an input or interleaving that violates the claimed behavior at a user-observable boundary.",
        "guidance": "A strong answer states the invariant, counterexample, and a test that would expose it.",
        "tags": ["question", "edge", "counterexample", "contract", "correctness"],
        "item_type": "question_bank",
        "roles": ["general", "backend"],
        "seniority_levels": ["intern", "junior"],
        "derive_from": "seed.clean_code.review_user_edge_cases",
    },
    {
        "id": "seed.question.testing_false_positive",
        "title": "Show that a test can fail for the right reason",
        "category": "testing",
        "summary": "Ask how the candidate would prove a test detects the intended regression instead of passing accidentally.",
        "guidance": "Look for mutation of the relevant behavior, narrow assertions, and control of unrelated failure paths.",
        "tags": ["question", "test", "false-positive", "assertion", "testing"],
        "item_type": "question_bank",
        "roles": ["general", "backend"],
        "seniority_levels": ["intern", "junior"],
        "derive_from": "seed.clean_code.pytest_exception_context",
    },
    {
        "id": "seed.question.design_current_requirement",
        "title": "Remove speculative flexibility",
        "category": "design",
        "summary": "Ask which abstraction can be removed until a concrete second requirement exists.",
        "guidance": "A strong answer distinguishes current variation from hypothetical future variation and preserves a clean extension seam.",
        "tags": ["question", "complexity", "abstraction", "requirement", "design"],
        "item_type": "question_bank",
        "roles": ["general", "backend"],
        "seniority_levels": ["intern", "junior"],
        "derive_from": "seed.clean_code.avoid_speculative_generality",
    },
    {
        "id": "seed.question.security_generic_error",
        "title": "Design a safe authentication failure",
        "category": "security",
        "summary": "Ask what the caller and operator should each learn when authentication fails.",
        "guidance": "Require non-enumerating public feedback plus bounded internal diagnostics with no secret material.",
        "tags": ["question", "authentication", "enumeration", "error", "security"],
        "item_type": "question_bank",
        "roles": ["backend", "platform"],
        "seniority_levels": ["intern", "junior"],
        "derive_from": "seed.clean_code.authentication_error_boundaries",
    },
]


def _content_hash(item: dict[str, object]) -> str:
    claim = f"{item['summary']}\n{item['guidance']}"
    return hashlib.sha256(claim.encode("utf-8")).hexdigest()


def _source_family(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc == "docs.python.org" and "/unittest" in parsed.path:
        return "unittest_docs"
    return SOURCE_FAMILIES[parsed.netloc]


def _anchor(url: str) -> str:
    fragment = urlparse(url).fragment
    if not fragment:
        raise ValueError(f"source URL is missing an exact section anchor: {url}")
    return f"#{fragment}"


def _enrich_reference(item: dict[str, object]) -> None:
    citation = item["citation"]
    assert isinstance(citation, dict)
    replacement = REFERENCE_REPLACEMENTS.get(str(item["id"]))
    if replacement is not None:
        citation["title"], citation["url"] = replacement
    url = URL_OVERRIDES.get(str(citation.get("url")), citation.get("url"))
    if not isinstance(url, str):
        raise ValueError(f"reference has no authoritative URL: {item['id']}")
    citation["url"] = url
    citation["source_id"] = item["id"]
    item["source_family"] = _source_family(url)
    item["section_locator"] = _anchor(url)
    item["derived_from_ids"] = []


def _enrich_derived(
    item: dict[str, object],
    *,
    references_by_category: dict[str, list[dict[str, object]]],
    category_offsets: dict[str, int],
) -> None:
    category = str(item["category"])
    explicit_source = item.pop("derive_from", None)
    if explicit_source is None:
        references = references_by_category[category]
        explicit_source = references[category_offsets[category] % len(references)]["id"]
        category_offsets[category] += 1
    source = next(
        reference
        for reference in references_by_category[category]
        if reference["id"] == explicit_source
    )
    source_citation = source["citation"]
    assert isinstance(source_citation, dict)
    item["citation"] = {
        "source_id": item["id"],
        "title": source_citation["title"],
        "url": source_citation["url"],
    }
    item["source_family"] = source["source_family"]
    item["section_locator"] = source["section_locator"]
    item["derived_from_ids"] = [explicit_source]


def build() -> list[dict[str, object]]:
    raw_items = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw_items, list) or not all(
        isinstance(item, dict) for item in raw_items
    ):
        raise ValueError("knowledge corpus must be a list of objects")
    items = cast(list[dict[str, object]], raw_items)
    if len(items) not in {100, 120}:
        raise ValueError("expected the original 100-item or generated 120-item corpus")
    items = [item for item in items if item["id"] not in {x["id"] for x in NEW_ITEMS}]
    items.extend(NEW_ITEMS)
    for item in items:
        item.update(ITEM_PATCHES.get(str(item["id"]), {}))

    references_by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in items:
        if item["item_type"] == "reference":
            _enrich_reference(item)
            references_by_category[str(item["category"])].append(item)

    offsets: dict[str, int] = defaultdict(int)
    for item in items:
        if item["item_type"] != "reference":
            _enrich_derived(
                item,
                references_by_category=references_by_category,
                category_offsets=offsets,
            )
        item["corpus_version"] = CORPUS_VERSION
        item["content_sha256"] = _content_hash(item)

    type_counts = Counter(str(item["item_type"]) for item in items)
    category_counts = Counter(str(item["category"]) for item in items)
    if type_counts != {"reference": 72, "rubric": 18, "question_bank": 30}:
        raise ValueError(f"unexpected item-type balance: {type_counts}")
    if category_counts != {category: 20 for category in CATEGORIES}:
        raise ValueError(f"unexpected category balance: {category_counts}")
    return items


def main() -> None:
    CORPUS_PATH.write_text(
        json.dumps(build(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
