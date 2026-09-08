import asyncio

import pytest

from clutch.llm.spend import (
    InMemorySpendGuard,
    ModelBudgetExceeded,
    completion_cost_usd,
    conservative_token_estimate,
    embedding_cost_usd,
)


def test_spend_guard_enforces_per_request_and_daily_limits() -> None:
    async def exercise() -> None:
        guard = InMemorySpendGuard(
            per_request_limit_usd=0.05,
            daily_limit_usd=0.08,
        )

        reservation = await guard.reserve(0.04)
        await guard.reconcile(reservation, 0.03)
        second = await guard.reserve(0.05)
        metrics = await guard.metrics()

        assert second.amount_microusd == 50_000
        assert metrics.reserved_usd == 0.08
        with pytest.raises(ModelBudgetExceeded, match="daily"):
            await guard.reserve(0.001)
        with pytest.raises(ModelBudgetExceeded, match="per-request"):
            await InMemorySpendGuard(
                per_request_limit_usd=0.01,
                daily_limit_usd=1.0,
            ).reserve(0.02)

    asyncio.run(exercise())


def test_known_model_prices_and_estimates_are_explicit() -> None:
    assert completion_cost_usd(
        "gpt-5.4-mini",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    ) == 5.25
    assert embedding_cost_usd(
        "text-embedding-3-small",
        input_tokens=1_000_000,
    ) == 0.02
    assert conservative_token_estimate("é") == 2


def test_unknown_model_requires_explicit_prices(monkeypatch) -> None:
    monkeypatch.delenv("CLUTCH_MODEL_INPUT_USD_PER_MILLION", raising=False)
    monkeypatch.delenv("CLUTCH_MODEL_OUTPUT_USD_PER_MILLION", raising=False)

    with pytest.raises(ValueError, match="set both model price"):
        completion_cost_usd(
            "unpriced-model",
            input_tokens=100,
            output_tokens=100,
        )
