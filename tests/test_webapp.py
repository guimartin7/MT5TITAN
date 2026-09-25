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


def test_decision_outcome_api_round_trip():
    analysis_id = store.save_analysis(
        {
            "symbol": "OUTCOMETEST",
            "timeframe": "M5",
            "source": "demo",
            "reference_price": 100.0,
            "regime": {"value": "TRENDING"},
            "market_score": {"total": 80.0},
            "decision": {
                "id": "outcome-buy",
                "action": "BUY",
                "confidence": 0.8,
                "score": 0.7,
            },
            "risk": {"allowed": True},
            "ai": {"enabled": False},
        },
        datetime.now(timezone.utc).isoformat(),
    )

    response = client.post(
        "/api/outcomes",
        json={"analysis_id": analysis_id, "exit_price": 103.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "WIN"
    assert body["market_direction"] == "BUY"
    assert body["directional_return_pct"] == 3.0

    stats = client.get("/api/outcomes/stats")
    assert stats.status_code == 200
    assert stats.json()["evaluated"] >= 1


def test_hold_outcome_is_not_counted_as_directional_trade():
    analysis_id = store.save_analysis(
        {
            "symbol": "HOLDTEST",
            "timeframe": "M5",
            "source": "demo",
            "reference_price": 100.0,
            "regime": {"value": "RANGING"},
            "market_score": {"total": 40.0},
            "decision": {
                "id": "hold-decision",
                "action": "HOLD",
                "confidence": 0.0,
                "score": 0.0,
            },
            "risk": {"allowed": False},
            "ai": {"enabled": False},
        },
        datetime.now(timezone.utc).isoformat(),
    )

    response = client.post(
        "/api/outcomes",
        json={"analysis_id": analysis_id, "exit_price": 105.0},
    )
    assert response.status_code == 200
    assert response.json()["result"] == "HOLD"


def test_demo_watchlist_seed():
    response = client.post("/api/watchlist/demo-seed")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 5
    assert all(item["source"] == "demo" for item in items)


def test_scanner_ranks_seeded_watchlist(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    client.post("/api/watchlist/demo-seed")

    before = len(store.recent_analyses(200))
    response = client.post(
        "/api/scanner",
        json={
            "deep_ai": False,
            "ai_top_n": 3,
            "use_context": False,
            "candle_count": 140,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "QUANT_SCAN"
    assert len(body["ranked"]) >= 5
    scores = [item["recommendation"]["opportunity_score"] for item in body["ranked"]]
    assert scores == sorted(scores, reverse=True)
    assert all(item["deep_ai"] is False for item in body["ranked"])
    after = len(store.recent_analyses(200))
    assert after == before


def test_deep_ai_scanner_requires_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    client.post("/api/watchlist/demo-seed")
    response = client.post(
        "/api/scanner",
        json={"deep_ai": True, "ai_top_n": 3, "candle_count": 140},
    )
    assert response.status_code == 503


def test_dashboard_contains_scanner_and_history_containers():
    html = client.get("/").text
    for element_id in (
        'scannerResults',
        'watchlist',
        'paperTrades',
        'analysisHistory',
        'outcomeStats',
    ):
        assert f'id="{element_id}"' in html


def test_diagnostics_endpoint(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    body = response.json()
    assert body["app"]["status"] == "ok"
    assert body["quant"]["status"] == "ok"
    assert body["ai"]["status"] == "not_configured"
    assert body["avalon"]["connected"] is False


def test_dashboard_surfaces_analysis_errors():
    html = client.get("/").text
    assert "Erro na análise:" in html
    assert "Analisando mercado" in html


def test_real_market_source_requires_key(monkeypatch):
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)
    from mt5titan.webapp import main as webmain
    webmain.twelve_market.api_key = None
    response = client.get(
        "/api/market/candles?symbol=EURUSD&timeframe=M5&source=twelve&count=40"
    )
    assert response.status_code == 503
    assert "TWELVE_DATA_API_KEY" in response.json()["detail"]


def test_health_reports_real_market_configuration(monkeypatch):
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "configured")
    body = client.get("/api/health").json()
    assert body["market_data"]["twelve_configured"] is True


def test_dashboard_handles_non_json_errors():
    html = client.get("/").text
    assert "const raw = await response.text()" in html
    assert "Resposta inválida da API" in html


def test_ai_quota_failure_falls_back_to_quant(monkeypatch):
    from mt5titan.webapp import main as webmain

    class QuotaProvider:
        def structured_decision(self, **kwargs):
            raise RuntimeError(
                "OpenAI request failed (RateLimitError): insufficient_quota "
                "credit_balance_exhausted"
            )

    monkeypatch.setenv("OPENAI_API_KEY", "configured")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr(webmain, "OpenAIProvider", lambda: QuotaProvider())

    market = client.get(
        "/api/market/candles?symbol=QUOTATEST&timeframe=M5&source=demo&count=80"
    ).json()
    response = client.post(
        "/api/analyze",
        json={
            "symbol": "QUOTATEST",
            "timeframe": "M5",
            "source": "demo",
            "use_ai": True,
            "candles": market["candles"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["action"] in {"BUY", "SELL", "HOLD"}
    assert body["ai"]["requested"] is True
    assert body["ai"]["available"] is False
    assert body["ai"]["fallback"] == "quant_only"
    assert body["ai"]["reason"] == "OPENAI_CREDITS_EXHAUSTED"


def test_external_context_is_attached_to_analysis(monkeypatch):
    from mt5titan.webapp import main as webmain

    class FakeNews:
        def context(self, **kwargs):
            return {
                "provider": "gdelt",
                "available": True,
                "risk_level": "MEDIUM",
                "high_impact_hits": 1,
                "articles": [{"title": "Fed rate headline", "domain": "example.com"}],
            }

    class FakeMacro:
        def context(self):
            return {
                "provider": "fred",
                "available": True,
                "series": {
                    "fed_funds": {
                        "available": True,
                        "value": 4.25,
                        "change": 0.0,
                        "date": "2026-09-24",
                    }
                },
            }

    monkeypatch.setattr(webmain, "gdelt_news", FakeNews())
    monkeypatch.setattr(webmain, "fred_macro", FakeMacro())

    market = client.get(
        "/api/market/candles?symbol=CONTEXTTEST&timeframe=M5&source=demo&count=80"
    ).json()
    response = client.post(
        "/api/analyze",
        json={
            "symbol": "CONTEXTTEST",
            "timeframe": "M5",
            "source": "demo",
            "use_ai": False,
            "use_external_context": True,
            "candles": market["candles"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["external_context"]["requested"] is True
    assert body["external_context"]["news"]["available"] is True
    assert body["external_context"]["macro"]["available"] is True


def test_context_endpoint_degrades_gracefully(monkeypatch):
    from mt5titan.webapp import main as webmain

    class BrokenNews:
        def context(self, **kwargs):
            raise RuntimeError("news unavailable")

    class NoMacro:
        def context(self):
            return {
                "provider": "fred",
                "available": False,
                "reason": "FRED_API_KEY_NOT_CONFIGURED",
                "series": {},
            }

    monkeypatch.setattr(webmain, "gdelt_news", BrokenNews())
    monkeypatch.setattr(webmain, "fred_macro", NoMacro())

    response = client.get("/api/context?symbol=BTCUSD")
    assert response.status_code == 200
    body = response.json()
    assert body["news"]["available"] is False
    assert body["macro"]["available"] is False


def test_scanner_enriches_top_candidates_with_context(monkeypatch):
    from mt5titan.webapp import main as webmain

    class FakeNews:
        def context(self, **kwargs):
            symbol = kwargs["symbol"]
            return {
                "provider": "gdelt",
                "available": True,
                "risk_level": "HIGH" if symbol == "EURUSD" else "LOW",
                "high_impact_hits": 4 if symbol == "EURUSD" else 0,
                "articles": [],
            }

    class FakeMacro:
        def context(self):
            return {
                "provider": "fred",
                "available": True,
                "series": {
                    "vix": {
                        "available": True,
                        "value": 18.0,
                        "change": 0.0,
                        "date": "2026-09-24",
                    }
                },
            }

    monkeypatch.setattr(webmain, "gdelt_news", FakeNews())
    monkeypatch.setattr(webmain, "fred_macro", FakeMacro())
    client.post("/api/watchlist/demo-seed")

    response = client.post(
        "/api/scanner",
        json={
            "deep_ai": False,
            "use_context": True,
            "context_top_n": 5,
            "candle_count": 140,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "QUANT_CONTEXT_SCAN"
    assert any(item.get("context_enriched") for item in body["ranked"])
    enriched = [item for item in body["ranked"] if item.get("context_enriched")]
    assert all("external_context" in item for item in enriched)
    assert all("context_penalty_pct" in item["recommendation"] for item in enriched)



def _approved_analysis_for_risk(symbol: str, decision_id: str):
    return store.save_analysis(
        {
            "symbol": symbol,
            "timeframe": "M5",
            "source": "demo",
            "market_timestamp": 1_700_000_000,
            "reference_price": 100.0,
            "features": {},
            "regime": {"value": "TRENDING"},
            "market_score": {"total": 80.0},
            "decision": {
                "id": decision_id,
                "action": "BUY",
                "confidence": 0.8,
                "score": 0.7,
            },
            "risk": {"allowed": True},
            "ai": {"enabled": False},
        },
        datetime.now(timezone.utc).isoformat(),
    )


def test_execution_risk_blocks_duplicate_symbol_exposure():
    client.post("/api/paper/reset")
    first_id = _approved_analysis_for_risk("RISKPAIR", "risk-first")
    first = client.post(
        "/api/paper/order",
        json={
            "analysis_id": first_id,
            "symbol": "RISKPAIR",
            "side": "BUY",
            "stake": 10,
            "price": 100,
        },
    )
    assert first.status_code == 200
    assert first.json()["analysis_id"] == first_id
    assert first.json()["risk_recheck"]["allowed"] is True

    second_id = _approved_analysis_for_risk("RISKPAIR", "risk-second")
    blocked = client.post(
        "/api/paper/order",
        json={
            "analysis_id": second_id,
            "symbol": "RISKPAIR",
            "side": "BUY",
            "stake": 10,
            "price": 100,
        },
    )

    assert blocked.status_code == 422
    assert "conflicting_exposure" in blocked.json()["detail"]


def test_execution_risk_blocks_excessive_stake():
    client.post("/api/paper/reset")
    analysis_id = _approved_analysis_for_risk("STAKEPAIR", "risk-stake")

    blocked = client.post(
        "/api/paper/order",
        json={
            "analysis_id": analysis_id,
            "symbol": "STAKEPAIR",
            "side": "BUY",
            "stake": 2000,
            "price": 100,
        },
    )

    assert blocked.status_code == 422
    assert "stake_above_limit" in blocked.json()["detail"]


def test_execution_risk_blocks_after_daily_loss_limit():
    client.post("/api/paper/reset")
    first_id = _approved_analysis_for_risk("LOSSPAIR", "risk-loss")
    opened = client.post(
        "/api/paper/order",
        json={
            "analysis_id": first_id,
            "symbol": "LOSSPAIR",
            "side": "BUY",
            "stake": 100,
            "price": 100,
        },
    )
    assert opened.status_code == 200

    settled = client.post(
        "/api/paper/settle",
        json={
            "trade_id": opened.json()["trade_id"],
            "exit_price": 99,
            "payout_ratio": 0.82,
        },
    )
    assert settled.status_code == 200

    next_id = _approved_analysis_for_risk("OTHERPAIR", "risk-after-loss")
    blocked = client.post(
        "/api/paper/order",
        json={
            "analysis_id": next_id,
            "symbol": "OTHERPAIR",
            "side": "BUY",
            "stake": 10,
            "price": 100,
        },
    )

    assert blocked.status_code == 422
    assert "daily_loss_limit" in blocked.json()["detail"]


def test_risk_status_endpoint_exposes_limits_and_state():
    client.post("/api/paper/reset")
    body = client.get("/api/risk/status?symbol=EURUSD").json()
    assert body["limits"]["max_open_trades"] == 3
    assert body["limits"]["max_stake_pct"] == 10.0
    assert body["state"]["open_trades"] == 0
