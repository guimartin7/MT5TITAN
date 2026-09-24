"""Persisted agent-opinion replay for reproducible research."""
import json
from pathlib import Path

from .models import AgentOpinion, AgentVerdict


def opinion_to_dict(opinion: AgentOpinion) -> dict:
    opinion.validate()
    return {
        "agent": opinion.agent,
        "verdict": opinion.verdict.value,
        "confidence": opinion.confidence,
        "score": opinion.score,
        "reason_codes": list(opinion.reason_codes),
        "risk_flags": list(opinion.risk_flags),
    }


def opinion_from_dict(payload: dict) -> AgentOpinion:
    opinion = AgentOpinion(
        agent=str(payload["agent"]),
        verdict=AgentVerdict(str(payload["verdict"])),
        confidence=float(payload["confidence"]),
        score=float(payload["score"]),
        reason_codes=tuple(str(x) for x in payload.get("reason_codes", [])),
        risk_flags=tuple(str(x) for x in payload.get("risk_flags", [])),
    )
    opinion.validate()
    return opinion


class OpinionReplayStore:
    def __init__(self, path: Path):
        self.path = path

    def append(self, *, key: str, opinions: list[AgentOpinion], metadata: dict | None = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "key": key,
            "opinions": [opinion_to_dict(op) for op in opinions],
            "metadata": dict(metadata or {}),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        rows: dict[str, dict] = {}
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                rows[str(row["key"])] = {
                    "opinions": [opinion_from_dict(item) for item in row["opinions"]],
                    "metadata": dict(row.get("metadata", {})),
                }
        return rows
