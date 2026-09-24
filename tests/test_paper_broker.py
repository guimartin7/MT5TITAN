from mt5titan.domain import Decision, DecisionAction, MarketSnapshot, RiskDecision
from mt5titan.execution.paper import PaperBroker


def snapshot(bid=100.0, ask=101.0, timestamp=1):
    return MarketSnapshot("TEST", "M5", timestamp, bid, ask)


def decision(action=DecisionAction.BUY):
    return Decision("d1", "TEST", action, 0.8, 0.7)


def test_risk_block_never_opens_position():
    broker = PaperBroker()
    event = broker.execute(decision(), RiskDecision(False, ("blocked",)), snapshot())
    assert event["action"] == "RISK_BLOCK"
    assert broker.account.position is None


def test_buy_and_close_realizes_pnl():
    broker = PaperBroker()
    opened = broker.execute(decision(), RiskDecision(True), snapshot(), units=2)
    assert opened["action"] == "PAPER_BUY"
    closed = broker.close(snapshot(bid=105.0, ask=106.0, timestamp=2))
    assert closed["pnl"] == 8.0
    assert broker.account.position is None


def test_same_direction_does_not_stack_position():
    broker = PaperBroker()
    broker.execute(decision(), RiskDecision(True), snapshot())
    event = broker.execute(decision(), RiskDecision(True), snapshot(timestamp=2))
    assert event["action"] == "ALREADY_POSITIONED"
