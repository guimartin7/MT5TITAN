"""Deterministic market intelligence layer."""

from .calendar import EconomicEvent, EventRiskPolicy, classify_event_risk
from .decision import DecisionEngine, DecisionPolicy
from .features import FeatureSet, build_features
from .portfolio import ExposurePolicy, close_correlation, evaluate_portfolio_exposure
from .opportunity import TradeRecommendation, build_trade_recommendation
from .regime import RegimeAssessment, detect_regime
from .score import MarketScore, score_market

__all__ = [
    "DecisionEngine",
    "DecisionPolicy",
    "EconomicEvent",
    "EventRiskPolicy",
    "ExposurePolicy",
    "FeatureSet",
    "TradeRecommendation",
    "TimeframeConfirmation",
    "MarketScore",
    "RegimeAssessment",
    "build_features",
    "build_trade_recommendation",
    "build_timeframe_confirmation",
    "classify_event_risk",
    "close_correlation",
    "detect_regime",
    "evaluate_portfolio_exposure",
    "score_market",
]

from .multitimeframe import TimeframeConfirmation, build_timeframe_confirmation
