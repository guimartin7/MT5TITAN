"""Final execution authorization policy."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionLimits:
    max_daily_loss: float = 30.0
    max_entries: int = 3


@dataclass(frozen=True)
class ExecutionPolicyState:
    broker_clean: bool
    journal_ready: bool
    permit_valid: bool
    broker_daily_net_pnl: float
    broker_entries_today: int


def evaluate_execution_policy(state: ExecutionPolicyState, limits: ExecutionLimits | None = None) -> dict:
    limits = limits or ExecutionLimits()
    blockers: list[str] = []

    if not state.broker_clean:
        blockers.append("broker_not_clean")
    if not state.journal_ready:
        blockers.append("execution_journal_blocked")
    if not state.permit_valid:
        blockers.append("execution_permit_invalid")
    if state.broker_daily_net_pnl <= -limits.max_daily_loss:
        blockers.append("broker_daily_loss_limit")
    if state.broker_entries_today >= limits.max_entries:
        blockers.append("broker_daily_entry_limit")

    return {
        "allowed": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "broker_daily_net_pnl": state.broker_daily_net_pnl,
        "broker_entries_today": state.broker_entries_today,
        "max_daily_loss": limits.max_daily_loss,
        "max_entries": limits.max_entries,
    }
