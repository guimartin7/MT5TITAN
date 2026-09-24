from datetime import datetime, timezone

from fastapi.testclient import TestClient

from mt5titan.webapp.main import app, store


client = TestClient(app)


def test_health_and_broker_status():
    assert client.get("/api/health").json()["status"] == "ok"
    brokers = client.get("/api/brokers").json()
    assert brokers["paper"]["execution_enabled"] is True
    assert brokers["avalon"]["execution_enabled"] is False


def test_demo_analysis_end_to_end():
    demo = client.get("/api/demo/candles?count=120").json()
    response = client.post(
        "/api/analyze",
        json={
            "symbol": "DEMO",
            "timeframe": "M5",
            "candles": demo["candles"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["analysis_id"] > 0
    assert body["decision"]["action"] in {"BUY", "SELL", "HOLD"}
    assert body["execution"]["live_enabled"] is False
    assert body["execution"]["paper_enabled"] is True


def test_paper_order_requires_matching_approved_analysis():
    client.post("/api/paper/reset")
    analysis_id = store.save_analysis(
        {
            "symbol": "DEMO",
            "timeframe": "M5",
            "regime": {"value": "TRENDING"},
            "market_score": {"total": 80.0},
            "decision": {
                "id": "approved-buy",
                "action": "BUY",
                "confidence": 0.8,
                "score": 0.7,
            },
            "risk": {"allowed": True},
        },
        datetime.now(timezone.utc).isoformat(),
    )

    before = client.get("/api/paper").json()["balance"]
    response = client.post(
        "/api/paper/order",
        json={
            "analysis_id": analysis_id,
            "symbol": "DEMO",
            "side": "BUY",
            "stake": 10,
            "price": 100,
        },
    )

    assert response.status_code == 200
    assert response.json()["analysis_id"] == analysis_id
    after = client.get("/api/paper").json()["balance"]
    assert after == before - 10


def test_paper_order_rejects_side_that_disagrees_with_analysis():
    analysis_id = store.save_analysis(
        {
            "symbol": "DEMO",
            "timeframe": "M5",
            "regime": {"value": "TRENDING"},
            "market_score": {"total": 80.0},
            "decision": {
                "id": "approved-sell",
                "action": "SELL",
                "confidence": 0.8,
                "score": -0.7,
            },
            "risk": {"allowed": True},
        },
        datetime.now(timezone.utc).isoformat(),
    )
    response = client.post(
        "/api/paper/order",
        json={
            "analysis_id": analysis_id,
            "symbol": "DEMO",
            "side": "BUY",
            "stake": 10,
            "price": 100,
        },
    )
    assert response.status_code == 422
