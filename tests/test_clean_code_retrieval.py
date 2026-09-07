from clutch.knowledge_base import retrieve_clean_code_principles


def test_retrieve_clean_code_principles_ranks_specific_seed_principle() -> None:
    principles = retrieve_clean_code_principles(
        "mutable default argument list shares state between calls",
        categories={"correctness"},
        limit=1,
    )

    assert len(principles) == 1
    assert principles[0].id == "seed.clean_code.safe_python_defaults"
    assert (
        principles[0].citation.source_id
        == "seed.clean_code.safe_python_defaults"
    )


def test_retrieve_clean_code_principles_filters_by_category() -> None:
    principles = retrieve_clean_code_principles(
        "large function extraction small reviewable unit",
        categories={"design"},
    )

    assert [principle.id for principle in principles] == [
        "seed.clean_code.small_reviewable_units"
    ]


def test_retrieve_clean_code_principles_returns_empty_for_zero_limit() -> None:
    principles = retrieve_clean_code_principles("logging debug print", limit=0)

    assert principles == []
