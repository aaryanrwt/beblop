"""Unit tests for BEBOP deterministic tri-state verdict engine."""

import pytest
from bebop.measure import MeasurementResult
from bebop.verdict import compute_verdict, VerdictStatus


def test_clear_pass():
    # Gap = 150 mm +/- 4 mm, Object = 100 mm +/- 3 mm, Margin = 10 mm
    # Required = 110 mm. Delta = +40 mm. Sigma_d = sqrt(16+9) = 5.0 mm.
    # 2*sigma = 10 mm. Delta (40) > 10 mm -> PASS
    meas = MeasurementResult(
        gap_mm=150.0, sigma_gap=4.0,
        object_width_mm=100.0, sigma_width=3.0,
        n_samples=15, scale_mm_per_px=0.5
    )
    v = compute_verdict(meas, margin_mm=10.0, k=2.0)
    assert v.verdict == VerdictStatus.PASS
    assert v.delta_mm == 40.0
    assert v.missing_measurement is None


def test_clear_fail():
    # Gap = 90 mm +/- 4 mm, Object = 100 mm +/- 3 mm, Margin = 10 mm
    # Required = 110 mm. Delta = -20 mm. Sigma_d = 5.0 mm.
    # 2*sigma = 10 mm. Delta (-20) < -10 mm -> FAIL
    meas = MeasurementResult(
        gap_mm=90.0, sigma_gap=4.0,
        object_width_mm=100.0, sigma_width=3.0,
        n_samples=15, scale_mm_per_px=0.5
    )
    v = compute_verdict(meas, margin_mm=10.0, k=2.0)
    assert v.verdict == VerdictStatus.FAIL
    assert v.delta_mm == -20.0
    assert v.missing_measurement is None


def test_marginal_undecided_with_tolerance_target():
    # Gap = 112 mm +/- 4 mm, Object = 100 mm +/- 3 mm, Margin = 10 mm
    # Required = 110 mm. Delta = +2 mm. Sigma_d = 5.0 mm.
    # 2*sigma = 10 mm. |Delta| (2) <= 10 mm -> UNDECIDED
    meas = MeasurementResult(
        gap_mm=112.0, sigma_gap=4.0,
        object_width_mm=100.0, sigma_width=3.0,
        n_samples=15, scale_mm_per_px=0.5
    )
    v = compute_verdict(meas, margin_mm=10.0, k=2.0)
    assert v.verdict == VerdictStatus.UNDECIDED
    assert v.missing_measurement is not None
    # sigma_target = |d| / k = 2.0 / 2.0 = 1.0 mm
    assert v.missing_measurement.target_sigma_mm == 1.0
    assert "optical noise floor" in v.missing_measurement.recommended_action or "higher resolution" in v.missing_measurement.recommended_action


def test_sensor_fault_undecided():
    meas = MeasurementResult(
        gap_mm=150.0, sigma_gap=4.0,
        object_width_mm=100.0, sigma_width=3.0,
        n_samples=15, flags=["NO_MARKER_DETECTED"], scale_mm_per_px=0.0
    )
    v = compute_verdict(meas, margin_mm=10.0, k=2.0)
    assert v.verdict == VerdictStatus.UNDECIDED
    assert "NO_MARKER_DETECTED" in v.flags
    assert v.missing_measurement is not None


def test_perspective_tilt_gate_undecided():
    meas = MeasurementResult(
        gap_mm=150.0, sigma_gap=4.0,
        object_width_mm=100.0, sigma_width=3.0,
        n_samples=15, flags=["PERSPECTIVE_TILT_EXCEEDED"], scale_mm_per_px=0.5
    )
    v = compute_verdict(meas, margin_mm=10.0, k=2.0)
    assert v.verdict == VerdictStatus.UNDECIDED
    assert "PERSPECTIVE_TILT_EXCEEDED" in v.flags
