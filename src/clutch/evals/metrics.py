"""Small retrieval metrics shared by regression and comparison runners."""

import math


def ratio(numerator: int | float, denominator: int | float) -> float:
    return numerator / denominator if denominator else 0.0


def ndcg_at_k(
    retrieved_grades: list[int],
    all_grades: list[int],
    *,
    k: int,
) -> float:
    """Return normalized discounted cumulative gain for relevance grades 0–3."""

    if k < 1:
        raise ValueError("k must be positive")

    def discounted_gain(grades: list[int]) -> float:
        return sum(
            ((2**grade) - 1) / math.log2(rank + 1)
            for rank, grade in enumerate(grades[:k], start=1)
        )

    ideal_gain = discounted_gain(sorted(all_grades, reverse=True))
    if ideal_gain == 0.0:
        return 1.0 if not any(retrieved_grades) else 0.0
    return discounted_gain(retrieved_grades) / ideal_gain
