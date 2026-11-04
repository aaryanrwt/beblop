"""BEBOP-Gate: Deterministic tri-state clearance verifier.

Evaluates metric clearance against safety margin with rigorous 2-sigma confidence.
Fail-closed posture: any gate failure or ambiguous clearance returns UNDECIDED
with precise, actionable missing measurement guidance.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from .measure import MeasurementResult


class VerdictStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNDECIDED = "UNDECIDED"


@dataclass
class MissingMeasurementGuide:
    rule: str
    quantity: str
    current_sigma_mm: float
    target_sigma_mm: float
    tolerance_needed_mm: float
    camera_floor_exceeded: bool
    recommended_action: str


@dataclass
class DecisionVerdict:
    verdict: VerdictStatus
    gap_mm: float
    required_mm: float
    margin_mm: float
    delta_mm: float
    sigma_d_mm: float
    k_factor: float
    flags: List[str] = field(default_factory=list)
    missing_measurement: Optional[MissingMeasurementGuide] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "gap_mm": self.gap_mm,
            "required_mm": self.required_mm,
            "margin_mm": self.margin_mm,
            "delta_mm": self.delta_mm,
            "sigma_d_mm": self.sigma_d_mm,
            "k_factor": self.k_factor,
            "flags": self.flags,
            "reason": self.reason,
            "missing_measurement": (
                {
                    "rule": self.missing_measurement.rule,
                    "quantity": self.missing_measurement.quantity,
                    "current_sigma_mm": self.missing_measurement.current_sigma_mm,
                    "target_sigma_mm": self.missing_measurement.target_sigma_mm,
                    "tolerance_needed_mm": self.missing_measurement.tolerance_needed_mm,
                    "camera_floor_exceeded": self.missing_measurement.camera_floor_exceeded,
                    "recommended_action": self.missing_measurement.recommended_action,
                }
                if self.missing_measurement
                else None
            ),
        }


def compute_verdict(
    measurement: MeasurementResult,
    margin_mm: float = 5.0,
    k: float = 2.0,
    iou_stability: float = 1.0,
    tau: float = 0.85,
    camera_noise_floor_mm: float = 1.0,
) -> DecisionVerdict:
    """Evaluate deterministic clearance verdict.
    
    Returns PASS, FAIL, or UNDECIDED. Never guesses.
    """
    flags = list(measurement.flags)
    
    # 1. Stability gates
    if iou_stability < tau:
        flags.append("MASK_IOU_INSTABILITY")
        return DecisionVerdict(
            verdict=VerdictStatus.UNDECIDED,
            gap_mm=measurement.gap_mm,
            required_mm=measurement.object_width_mm + margin_mm,
            margin_mm=margin_mm,
            delta_mm=0.0,
            sigma_d_mm=999.0,
            k_factor=k,
            flags=flags,
            missing_measurement=MissingMeasurementGuide(
                rule="mask_iou_consensus >= tau (0.85)",
                quantity="mask stability across prompt variants",
                current_sigma_mm=round(1.0 - iou_stability, 3),
                target_sigma_mm=round(1.0 - tau, 3),
                tolerance_needed_mm=round(tau - iou_stability, 3),
                camera_floor_exceeded=False,
                recommended_action="Object contours fluctuate across prompt variants. Eliminate occlusion or clean background.",
            ),
            reason=f"Perception unstable: mask IoU ({iou_stability:.2f}) < threshold ({tau:.2f}).",
        )

    # Check for hard sensor / measurement failures
    critical_failure_flags = {
        "NO_MARKER_DETECTED",
        "MARKER_TOO_SMALL",
        "PERSPECTIVE_TILT_EXCEEDED",
        "FEWER_THAN_TWO_OBSTACLES",
        "EMPTY_OBSTACLE_MASK",
        "EMPTY_OBJECT_MASK",
    }
    if any(f in critical_failure_flags for f in flags):
        active_crits = [f for f in flags if f in critical_failure_flags]
        return DecisionVerdict(
            verdict=VerdictStatus.UNDECIDED,
            gap_mm=measurement.gap_mm,
            required_mm=measurement.object_width_mm + margin_mm,
            margin_mm=margin_mm,
            delta_mm=0.0,
            sigma_d_mm=999.0,
            k_factor=k,
            flags=flags,
            missing_measurement=MissingMeasurementGuide(
                rule="Physical scale and obstacle evidence must be intact",
                quantity=", ".join(active_crits),
                current_sigma_mm=999.0,
                target_sigma_mm=1.0,
                tolerance_needed_mm=0.0,
                camera_floor_exceeded=False,
                recommended_action=f"Resolve sensor fault: {active_crits[0]}. Ensure ArUco marker is visible and square-on.",
            ),
            reason=f"Gate failure: {', '.join(active_crits)}.",
        )

    # 2. Clearance calculation
    required = measurement.object_width_mm + margin_mm
    d = measurement.gap_mm - required
    sigma_d = math.sqrt(measurement.sigma_gap**2 + measurement.sigma_width**2)

    # Confidence margin
    threshold = k * sigma_d

    if d > threshold:
        return DecisionVerdict(
            verdict=VerdictStatus.PASS,
            gap_mm=measurement.gap_mm,
            required_mm=required,
            margin_mm=margin_mm,
            delta_mm=round(d, 2),
            sigma_d_mm=round(sigma_d, 2),
            k_factor=k,
            flags=flags,
            reason=f"Clearance confirmed: margin {d:+.1f} mm exceeds {k}*sigma ({threshold:.1f} mm).",
        )
    elif d < -threshold:
        return DecisionVerdict(
            verdict=VerdictStatus.FAIL,
            gap_mm=measurement.gap_mm,
            required_mm=required,
            margin_mm=margin_mm,
            delta_mm=round(d, 2),
            sigma_d_mm=round(sigma_d, 2),
            k_factor=k,
            flags=flags,
            reason=f"Collision certain: shortfall {abs(d):.1f} mm exceeds {k}*sigma ({threshold:.1f} mm).",
        )
    else:
        # Ambiguous clearance: gap is within 2-sigma of threshold
        sigma_target = abs(d) / k if k > 0 else 0.0
        floor_exceeded = abs(d) < camera_noise_floor_mm
        
        quantity = "gap edge" if measurement.sigma_gap >= measurement.sigma_width else "object width"
        action = (
            "Clearance is below camera optical noise floor; manual caliper measurement required."
            if floor_exceeded
            else "Re-observe gap with a higher resolution or closer square-on camera view."
        )

        missing_guide = MissingMeasurementGuide(
            rule="abs(gap - (width + margin)) > k * sigma_d",
            quantity=quantity,
            current_sigma_mm=round(sigma_d, 2),
            target_sigma_mm=round(sigma_target, 2),
            tolerance_needed_mm=round(sigma_target, 2),
            camera_floor_exceeded=floor_exceeded,
            recommended_action=action,
        )

        return DecisionVerdict(
            verdict=VerdictStatus.UNDECIDED,
            gap_mm=measurement.gap_mm,
            required_mm=required,
            margin_mm=margin_mm,
            delta_mm=round(d, 2),
            sigma_d_mm=round(sigma_d, 2),
            k_factor=k,
            flags=flags,
            missing_measurement=missing_guide,
            reason=f"Clearance marginal: |delta| ({abs(d):.1f} mm) is within uncertainty boundary ({threshold:.1f} mm).",
        )


def check_alternate_route(
    alternate_measurement: MeasurementResult,
    primary_verdict: DecisionVerdict,
    route_id: str = "R2",
    margin_mm: float = 5.0,
    k: float = 2.0,
) -> DecisionVerdict:
    """Evaluate alternate bypass route (PRD FR-9) after primary route fails.
    
    Uses identical 2-sigma metric verifier to ensure consistent safety posture.
    """
    alt_verdict = compute_verdict(
        alternate_measurement,
        margin_mm=margin_mm,
        k=k,
    )
    if alt_verdict.verdict == VerdictStatus.PASS:
        alt_verdict.reason = f"Alternate route {route_id} verified SAFE: margin {alt_verdict.delta_mm:+.1f} mm."
    else:
        alt_verdict.reason = f"Alternate route {route_id} rejected: {alt_verdict.reason}"
    return alt_verdict

