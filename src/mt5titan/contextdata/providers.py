"""Free/official external context sources."""
from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen


HIGH_IMPACT_TERMS = (
    "federal reserve",
    "fed rate",
    "interest rate",
    "inflation",
    "cpi",
    "jobs report",
    "payroll",
    "central bank",
    "ecb",
    "boe",
    "boj",
    "sanction",
    "war",
    "hack",
    "bank failure",
    "liquidation",
    "etf",
)


def _symbol_query(symbol: str) -> str:
    symbol = symbol.upper().replace("/", "")
    mapping = {
        "BTCUSD": '(bitcoin OR BTC OR cryptocurrency)',
        "ETHUSD": '(ethereum OR ETH OR cryptocurrency)',
        "EURUSD": '(euro OR EUR OR ECB OR "Federal Reserve")',
        "GBPUSD": '(pound OR sterling OR GBP OR BOE OR "Bank of England")',
        "USDJPY": '(yen OR JPY OR BOJ OR "Bank of Japan" OR "Federal Reserve")',
        "XAUUSD": '(gold OR bullion OR "Federal Reserve" OR inflation)',
    }
    return mapping.get(symbol, f'"{symbol}"')


class GdeltNewsProvider:
    name = "gdelt"

    def __init__(self, opener=None):
        self._opener = opener or urlopen

    def context(self, *, symbol: str, max_records: int = 12, timespan: str = "24h") -> dict:
        max_records = max(1, min(int(max_records), 50))
        query = urlencode({
            "query": _symbol_query(symbol),
            "mode": "artlist",
            "maxrecords": max_records,
            "timespan": timespan,
            "format": "json",
            "sort": "HybridRel",
        })
        url = f"https://api.gdeltproject.org/api/v2/doc/doc?{query}"

        try:
            with self._opener(url, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise RuntimeError(f"GDELT request failed: {error}") from error

        articles = payload.get("articles") or []
        normalized = []
        impact_hits = 0
        for article in articles[:max_records]:
            title = str(article.get("title") or "").strip()
            lowered = title.lower()
            matched = [term for term in HIGH_IMPACT_TERMS if term in lowered]
            impact_hits += len(matched)
            normalized.append({
                "title": title,
                "domain": article.get("domain"),
                "source_country": article.get("sourcecountry"),
                "seen_date": article.get("seendate"),
                "url": article.get("url"),
                "impact_terms": matched,
            })

        article_count = len(normalized)
        risk_level = (
            "HIGH" if impact_hits >= 4
            else "MEDIUM" if impact_hits >= 1
            else "LOW"
        )
        return {
            "provider": self.name,
            "available": True,
            "query": _symbol_query(symbol),
            "article_count": article_count,
            "high_impact_hits": impact_hits,
            "risk_level": risk_level,
            "articles": normalized,
        }


class FredMacroProvider:
    name = "fred"

    SERIES = {
        "fed_funds": "DFF",
        "treasury_10y": "DGS10",
        "vix": "VIXCLS",
        "broad_dollar": "DTWEXBGS",
    }

    def __init__(self, api_key: str | None = None, opener=None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        self._opener = opener or urlopen

    def _observations(self, series_id: str, limit: int = 2) -> list[dict]:
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY is required for macro context")
        query = urlencode({
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        })
        url = f"https://api.stlouisfed.org/fred/series/observations?{query}"
        try:
            with self._opener(url, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise RuntimeError(f"FRED request failed: {error}") from error
        if payload.get("error_code"):
            raise RuntimeError(f"FRED error: {payload.get('error_message', payload['error_code'])}")
        return [
            row for row in payload.get("observations", [])
            if str(row.get("value")) not in {"", "."}
        ]

    def context(self) -> dict:
        if not self.api_key:
            return {
                "provider": self.name,
                "available": False,
                "reason": "FRED_API_KEY_NOT_CONFIGURED",
                "series": {},
            }

        series = {}
        for name, series_id in self.SERIES.items():
            try:
                rows = self._observations(series_id, 4)
                if not rows:
                    series[name] = {"series_id": series_id, "available": False}
                    continue
                latest = rows[0]
                previous = rows[1] if len(rows) > 1 else None
                latest_value = float(latest["value"])
                previous_value = float(previous["value"]) if previous else None
                series[name] = {
                    "series_id": series_id,
                    "available": True,
                    "date": latest["date"],
                    "value": latest_value,
                    "previous": previous_value,
                    "change": (
                        round(latest_value - previous_value, 6)
                        if previous_value is not None else None
                    ),
                }
            except RuntimeError as error:
                series[name] = {
                    "series_id": series_id,
                    "available": False,
                    "reason": str(error),
                }

        return {
            "provider": self.name,
            "available": any(row.get("available") for row in series.values()),
            "series": series,
        }
