from mt5titan.titan.calibration import CalibrationPolicy, build_calibration_advice


def test_calibration_not_ready_with_small_sample():
    data = {
        "TRENDING": {
            "technical": {"directional_calls": 10, "correct": 7},
            "news": {"directional_calls": 10, "correct": 6},
            "macro": {"directional_calls": 10, "correct": 5},
        }
    }
    advice = build_calibration_advice(data)
    assert advice["regimes"]["TRENDING"]["ready"] is False
    assert advice["regimes"]["TRENDING"]["suggested_weights"] is None
    assert advice["automatic_application"] is False


def test_calibration_ready_with_enough_sample_and_bounded_weights():
    data = {
        "TRENDING": {
            "technical": {"directional_calls": 40, "correct": 32},
            "news": {"directional_calls": 40, "correct": 20},
            "macro": {"directional_calls": 40, "correct": 24},
        }
    }
    advice = build_calibration_advice(
        data,
        policy=CalibrationPolicy(minimum_samples_per_agent=20),
    )
    row = advice["regimes"]["TRENDING"]
    assert row["ready"] is True
    weights = row["suggested_weights"]
    assert round(sum(weights.values()), 4) == 1.0
    assert abs(weights["technical"] - 0.45) <= 0.11
    assert abs(weights["news"] - 0.25) <= 0.11
    assert abs(weights["macro"] - 0.30) <= 0.11
