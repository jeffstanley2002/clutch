"""Fail-closed per-call and daily spend reservations for paid model APIs."""

from __future__ import annotations

import asyncio
import math
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError

MICRO_USD = 1_000_000
DEFAULT_REQUEST_LIMIT_USD = 0.10
DEFAULT_DAILY_LIMIT_USD = 1.00


class ModelBudgetExceeded(RuntimeError):
    """Raised before a provider call that would exceed a configured ceiling."""


class ModelBudgetUnavailable(RuntimeError):
    """Raised when the shared budget counter cannot fail closed safely."""


class ModelPricingUnknown(ValueError):
    """Raised when a paid model has no configured price."""


class SpendMetrics(BaseModel):
    """Safe model-spend state exposed for operations and debugging."""

    day_utc: str
    reserved_usd: float = Field(..., ge=0.0)
    daily_limit_usd: float = Field(..., gt=0.0)
    per_request_limit_usd: float = Field(..., gt=0.0)


@dataclass(frozen=True)
class SpendReservation:
    amount_microusd: int
    day_utc: str


class SpendGuard(Protocol):
    async def reserve(self, estimated_cost_usd: float) -> SpendReservation: ...

    async def reconcile(
        self,
        reservation: SpendReservation,
        actual_cost_usd: float,
    ) -> None: ...

    async def metrics(self) -> SpendMetrics: ...

    async def aclose(self) -> None: ...


class InMemorySpendGuard:
    """Process-local limiter for tests and local runs without Redis."""

    def __init__(
        self,
        *,
        per_request_limit_usd: float = DEFAULT_REQUEST_LIMIT_USD,
        daily_limit_usd: float = DEFAULT_DAILY_LIMIT_USD,
    ) -> None:
        _validate_limits(per_request_limit_usd, daily_limit_usd)
        self._per_request_microusd = _to_microusd(per_request_limit_usd)
        self._daily_microusd = _to_microusd(daily_limit_usd)
        self._totals: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def reserve(self, estimated_cost_usd: float) -> SpendReservation:
        amount = _to_microusd(estimated_cost_usd)
        day = _day_utc()
        if amount > self._per_request_microusd:
            raise ModelBudgetExceeded("estimated model call exceeds per-request limit")
        async with self._lock:
            current = self._totals.get(day, 0)
            if current + amount > self._daily_microusd:
                raise ModelBudgetExceeded("daily model-spend limit reached")
            self._totals[day] = current + amount
        return SpendReservation(amount_microusd=amount, day_utc=day)

    async def reconcile(
        self,
        reservation: SpendReservation,
        actual_cost_usd: float,
    ) -> None:
        actual = _to_microusd(actual_cost_usd)
        async with self._lock:
            current = self._totals.get(reservation.day_utc, 0)
            self._totals[reservation.day_utc] = max(
                0,
                current + actual - reservation.amount_microusd,
            )

    async def metrics(self) -> SpendMetrics:
        day = _day_utc()
        return SpendMetrics(
            day_utc=day,
            reserved_usd=self._totals.get(day, 0) / MICRO_USD,
            daily_limit_usd=self._daily_microusd / MICRO_USD,
            per_request_limit_usd=self._per_request_microusd / MICRO_USD,
        )

    async def aclose(self) -> None:
        return None


class RedisSpendGuard:
    """Cross-process daily limiter backed by an atomic Redis reservation."""

    _RESERVE_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
local daily_limit = tonumber(ARGV[2])
if current + amount > daily_limit then
  return -1
end
local updated = redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
return updated
"""

    def __init__(
        self,
        redis_url: str,
        *,
        per_request_limit_usd: float = DEFAULT_REQUEST_LIMIT_USD,
        daily_limit_usd: float = DEFAULT_DAILY_LIMIT_USD,
    ) -> None:
        _validate_limits(per_request_limit_usd, daily_limit_usd)
        self._per_request_microusd = _to_microusd(per_request_limit_usd)
        self._daily_microusd = _to_microusd(daily_limit_usd)
        self._client: Redis = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            max_connections=10,
        )

    async def reserve(self, estimated_cost_usd: float) -> SpendReservation:
        amount = _to_microusd(estimated_cost_usd)
        day = _day_utc()
        if amount > self._per_request_microusd:
            raise ModelBudgetExceeded("estimated model call exceeds per-request limit")
        try:
            updated = await self._client.eval(
                self._RESERVE_SCRIPT,
                1,
                _redis_key(day),
                amount,
                self._daily_microusd,
                172_800,
            )
        except RedisError as exc:
            raise ModelBudgetUnavailable("model-spend counter unavailable") from exc
        if int(updated) < 0:
            raise ModelBudgetExceeded("daily model-spend limit reached")
        return SpendReservation(amount_microusd=amount, day_utc=day)

    async def reconcile(
        self,
        reservation: SpendReservation,
        actual_cost_usd: float,
    ) -> None:
        actual = _to_microusd(actual_cost_usd)
        delta = actual - reservation.amount_microusd
        if delta == 0:
            return
        try:
            await self._client.incrby(_redis_key(reservation.day_utc), delta)
        except RedisError as exc:
            raise ModelBudgetUnavailable("model-spend counter unavailable") from exc

    async def metrics(self) -> SpendMetrics:
        day = _day_utc()
        try:
            raw_total = await self._client.get(_redis_key(day))
        except RedisError as exc:
            raise ModelBudgetUnavailable("model-spend counter unavailable") from exc
        return SpendMetrics(
            day_utc=day,
            reserved_usd=max(0, int(raw_total or 0)) / MICRO_USD,
            daily_limit_usd=self._daily_microusd / MICRO_USD,
            per_request_limit_usd=self._per_request_microusd / MICRO_USD,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def completion_cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float:
    input_rate, output_rate = _completion_rates(model)
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def embedding_cost_usd(model: str, *, input_tokens: int) -> float:
    configured = os.getenv("CLUTCH_EMBEDDING_USD_PER_MILLION", "").strip()
    if configured:
        rate = _positive_float(configured, "CLUTCH_EMBEDDING_USD_PER_MILLION")
    elif model == "text-embedding-3-small":
        rate = 0.02
    else:
        raise ModelPricingUnknown(
            "set CLUTCH_EMBEDDING_USD_PER_MILLION for the configured model"
        )
    return input_tokens * rate / 1_000_000


def conservative_token_estimate(text: str) -> int:
    """Use UTF-8 bytes as a deliberately conservative pre-call token bound."""

    return max(1, len(text.encode("utf-8")))


_SPEND_GUARD: SpendGuard | None = None


def spend_guard_from_env() -> SpendGuard:
    global _SPEND_GUARD
    if _SPEND_GUARD is not None:
        return _SPEND_GUARD
    load_dotenv()
    per_request = _positive_float(
        os.getenv("CLUTCH_MODEL_PER_REQUEST_USD", str(DEFAULT_REQUEST_LIMIT_USD)),
        "CLUTCH_MODEL_PER_REQUEST_USD",
    )
    daily = _positive_float(
        os.getenv("CLUTCH_MODEL_DAILY_USD", str(DEFAULT_DAILY_LIMIT_USD)),
        "CLUTCH_MODEL_DAILY_USD",
    )
    redis_url = os.getenv("REDIS_URL", "").strip()
    _SPEND_GUARD = (
        RedisSpendGuard(
            redis_url,
            per_request_limit_usd=per_request,
            daily_limit_usd=daily,
        )
        if redis_url
        else InMemorySpendGuard(
            per_request_limit_usd=per_request,
            daily_limit_usd=daily,
        )
    )
    return _SPEND_GUARD


async def spend_metrics_snapshot() -> SpendMetrics:
    return await spend_guard_from_env().metrics()


async def close_spend_guard() -> None:
    global _SPEND_GUARD
    if _SPEND_GUARD is not None:
        await _SPEND_GUARD.aclose()
        _SPEND_GUARD = None


def _completion_rates(model: str) -> tuple[float, float]:
    configured_input = os.getenv("CLUTCH_MODEL_INPUT_USD_PER_MILLION", "").strip()
    configured_output = os.getenv("CLUTCH_MODEL_OUTPUT_USD_PER_MILLION", "").strip()
    if configured_input and configured_output:
        return (
            _positive_float(configured_input, "CLUTCH_MODEL_INPUT_USD_PER_MILLION"),
            _positive_float(
                configured_output,
                "CLUTCH_MODEL_OUTPUT_USD_PER_MILLION",
            ),
        )
    if model == "gpt-5.4-mini" or model.startswith("gpt-5.4-mini-"):
        return 0.75, 4.50
    raise ModelPricingUnknown(
        "set both model price environment variables for the configured model"
    )


def _validate_limits(per_request_usd: float, daily_usd: float) -> None:
    if per_request_usd <= 0 or daily_usd <= 0:
        raise ValueError("model spend limits must be positive")
    if per_request_usd > daily_usd:
        raise ValueError("per-request model spend limit cannot exceed daily limit")


def _positive_float(raw: str, name: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _to_microusd(cost_usd: float) -> int:
    if not math.isfinite(cost_usd) or cost_usd < 0:
        raise ValueError("model cost must be a finite non-negative number")
    return max(0, math.ceil(cost_usd * MICRO_USD))


def _day_utc() -> str:
    return datetime.now(UTC).date().isoformat()


def _redis_key(day: str) -> str:
    return f"clutch:model-spend:v1:{day}"
