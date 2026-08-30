"""Metric truy hồi. Binary relevance: một provision_id hoặc đúng hoặc không."""

import math


def recall_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    if not relevant or not retrieved:
        return 0.0
    hit = len(set(retrieved[:k]) & relevant)
    return hit / len(relevant)


def mrr_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    for rank, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    if not relevant or not retrieved:
        return 0.0
    seen: set[int] = set()
    dcg = 0.0
    for rank, item in enumerate(retrieved[:k], start=1):
        if item in relevant and item not in seen:
            seen.add(item)
            dcg += 1.0 / math.log2(rank + 1)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant), k) + 1))
    return dcg / idcg if idcg else 0.0
