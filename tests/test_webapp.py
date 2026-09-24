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


def test_dashboard_javascript_is_not_escaped():
    response = client.get("/")
    assert response.status_code == 200
    assert "\\nlet lastAnalysisId" not in response.text
    assert "\\n  lastAnalysisId" not in response.text


def test_market_import_and_stored_source():
    demo = client.get("/api/market/candles?symbol=IMPORTTEST&timeframe=M5&source=demo&count=40").json()
    imported = client.post(
        "/api/market/import",
        json={
            "symbol": "IMPORTTEST",
            "timeframe": "M5",
            "candles": demo["candles"],
        },
    )
    assert imported.status_code == 200
    assert imported.json()["imported"] == 40

    stored = client.get(
        "/api/market/candles?symbol=IMPORTTEST&timeframe=M5&source=stored&count=40"
    )
    assert stored.status_code == 200
    assert stored.json()["source"] == "stored"
    assert len(stored.json()["candles"]) == 40


def test_watchlist_api_round_trip():
    client.delete("/api/watchlist?symbol=WATCHTEST&timeframe=M15&source=demo")
    created = client.post(
        "/api/watchlist",
        json={"symbol": "WATCHTEST", "timeframe": "M15", "source": "demo"},
    )
    assert created.status_code == 200

    items = client.get("/api/watchlist").json()["items"]
    assert {"symbol": "WATCHTEST", "timeframe": "M15", "source": "demo"} in items

    removed = client.delete(
        "/api/watchlist?symbol=WATCHTEST&timeframe=M15&source=demo"
    )
    assert removed.status_code == 200


def test_health_reports_ai_configuration_without_secret(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    body = client.get("/api/health").json()
    assert body["ai"]["provider"] == "openai"
    assert body["ai"]["configured"] is False
    assert "api_key" not in str(body).lower()


def test_ai_mode_requires_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    market = client.get(
        "/api/market/candles?symbol=AIMISSING&timeframe=M5&source=demo&count=40"
    ).json()
    response = client.post(
        "/api/analyze",
        json={
            "symbol": "AIMISSING",
            "timeframe": "M5",
            "source": "demo",
            "use_ai": True,
            "candles": market["candles"],
        },
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
