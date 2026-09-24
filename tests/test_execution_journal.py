import pytest

from mt5titan.execution.journal import create_intent, empty_journal, intent_id, journal_readiness, transition


def test_intent_is_deterministic_and_idempotent():
    journal = empty_journal()
    first, created = create_intent(journal, "WINV26", 123, 1)
    again, created_again = create_intent(journal, "WINV26", 123, 1)
    assert created and not created_again
    assert first is again
    assert first["id"] == intent_id("WINV26", 123, 1)


def test_second_active_intent_is_blocked():
    journal = empty_journal()
    create_intent(journal, "WINV26", 123, 1)
    with pytest.raises(RuntimeError):
        create_intent(journal, "WINV26", 124, -1)


def test_unknown_state_blocks_readiness():
    journal = empty_journal()
    item, _ = create_intent(journal, "WINV26", 123, 1)
    transition(item, "PREFLIGHT_APPROVED")
    transition(item, "SENT")
    transition(item, "UNKNOWN")
    result = journal_readiness(journal)
    assert not result["ready"]
    assert result["blockers"] == ["unknown_execution_outcome"]
