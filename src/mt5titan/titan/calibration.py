"""Conservative observational calibration advisor.

This module never changes live weights automatically. It only suggests weights
when enough labeled outcomes exist for every core agent in a market regime.
"""
from __future__ import annotations

from dataclasses import dataclass


DEFAULT_WEIGHTS = {
    "technical": 0.45,
    "news": 0.25,
    "macro": 0.30,
}


@dataclass(frozen=True)
class CalibrationPolicy:
    minimum_samples_per_agent: int = 20
    prior_samples: int = 20
    prior_accuracy: float = 0.50
    max_absolute_shift: float = 0.10


def _shrunk_accuracy(correct: int, calls: int, policy: CalibrationPolicy) -> float:
    return (
        correct + policy.prior_samples * policy.prior_accuracy
    ) / (calls + policy.prior_samples)


def _bounded_weights(
    evidence: dict[str, dict],
    policy: CalibrationPolicy,
) -> dict[str, float]:
    raw = {}
    for agent, default_weight in DEFAULT_WEIGHTS.items():
        row = evidence[agent]
        accuracy = _shrunk_accuracy(
            int(row["correct"]),
            int(row["directional_calls"]),
            policy,
        )
        # Mild multiplicative adjustment around the default weight.
        performance_factor = 0.75 + accuracy * 0.50
        raw[agent] = default_weight * performance_factor

    total = sum(raw.values()) or 1.0
    normalized = {agent: value / total for agent, value in raw.items()}

    bounded = {}
    for agent, default_weight in DEFAULT_WEIGHTS.items():
        low = max(0.05, default_weight - policy.max_absolute_shift)
        high = min(0.80, default_weight + policy.max_absolute_shift)
        bounded[agent] = max(low, min(high, normalized[agent]))

    total = sum(bounded.values()) or 1.0
    return {
        agent: round(value / total, 4)
        for agent, value in bounded.items()
    }


def build_calibration_advice(
    samples_by_regime: dict[str, dict[str, dict]],
    *,
    policy: CalibrationPolicy | None = None,
) -> dict:
    policy = policy or CalibrationPolicy()
    regimes = {}

    for regime, evidence in sorted(samples_by_regime.items()):
        complete = {
            agent: {
                "directional_calls": int((evidence.get(agent) or {}).get("directional_calls", 0)),
                "correct": int((evidence.get(agent) or {}).get("correct", 0)),
            }
            for agent in DEFAULT_WEIGHTS
        }
        for row in complete.values():
            calls = row["directional_calls"]
            row["accuracy_pct"] = (
                round(row["correct"] / calls * 100.0, 2)
                if calls else None
            )

        ready = all(
            row["directional_calls"] >= policy.minimum_samples_per_agent
            for row in complete.values()
        )
        regimes[regime] = {
            "ready": ready,
            "current_weights": dict(DEFAULT_WEIGHTS),
            "suggested_weights": (
                _bounded_weights(complete, policy)
                if ready
                else None
            ),
            "evidence": complete,
        }

    return {
        "automatic_application": False,
        "minimum_samples_per_agent": policy.minimum_samples_per_agent,
        "default_weights": dict(DEFAULT_WEIGHTS),
        "ready_regimes": [
            regime
            for regime, row in regimes.items()
            if row["ready"]
        ],
        "regimes": regimes,
    }
