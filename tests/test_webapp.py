from fastapi.testclient import TestClient

from mt5titan.webapp.main import app


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
    assert body["decision"]["action"] in {"BUY", "SELL", "HOLD"}
    assert body["execution"]["live_enabled"] is False
    assert body["execution"]["paper_enabled"] is True


def test_paper_order_is_functional():
    before = client.get("/api/paper").json()["balance"]
    response = client.post(
        "/api/paper/order",
        json={"symbol": "DEMO", "side": "BUY", "stake": 10, "price": 100},
    )
    assert response.status_code == 200
    after = client.get("/api/paper").json()["balance"]
    assert after == before - 10
