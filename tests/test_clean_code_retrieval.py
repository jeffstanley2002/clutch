from clutch.knowledge_base import retrieve_clean_code_principles
from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES


def test_committed_corpus_has_unique_typed_items_for_phase_two() -> None:
    source_ids = [item.id for item in SEED_CLEAN_CODE_PRINCIPLES]

    assert len(source_ids) == 60
    assert len(source_ids) == len(set(source_ids))
    assert {item.item_type for item in SEED_CLEAN_CODE_PRINCIPLES} == {
        "reference",
        "rubric",
        "question_bank",
    }
    assert all(
        item.citation.source_id == item.id for item in SEED_CLEAN_CODE_PRINCIPLES
    )


def test_retrieve_clean_code_principles_ranks_specific_seed_principle() -> None:
    principles = retrieve_clean_code_principles(
        "mutable default argument list shares state between calls",
        categories={"correctness"},
        limit=1,
    )

    assert len(principles) == 1
    assert principles[0].id == "seed.clean_code.safe_python_defaults"
    assert principles[0].citation.source_id == "seed.clean_code.safe_python_defaults"


def test_retrieve_clean_code_principles_filters_by_category() -> None:
    principles = retrieve_clean_code_principles(
        "large function extraction small reviewable unit",
        categories={"design"},
        limit=1,
    )

    assert [principle.id for principle in principles] == [
        "seed.clean_code.small_reviewable_units"
    ]


def test_issue_terms_outrank_generic_question_metadata() -> None:
    principles = retrieve_clean_code_principles(
        (
            "backend intern rubric question interview multiple functions duplicate "
            "the same implementation shared behavior extraction change points"
        ),
        categories={"design"},
        limit=3,
    )

    assert principles[0].id == "seed.clean_code.single_source_of_behavior"
    assert not {principle.id for principle in principles} & {
        "seed.question.design_data_shape_growth",
        "seed.question.design_ownership_boundary",
    }


def test_retrieve_clean_code_principles_returns_empty_for_zero_limit() -> None:
    principles = retrieve_clean_code_principles("logging debug print", limit=0)

    assert principles == []
