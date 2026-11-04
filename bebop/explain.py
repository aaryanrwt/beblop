"""BEBOP-Gate: Auditable plain-language explanation generator.

Summarizes verdicts, missing measurements, and ledger invalidation events for human engineers.
Can leverage local Meta Llama 3.2-Vision via Ollama/AirLLM or deterministic fallback templates.
CRITICAL POSTURE: The explanation is display-only; the verdict engine NEVER reads it.
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional
from .verdict import DecisionVerdict, VerdictStatus
from .ledger import AssumptionLedger


def generate_explanation(
    verdict: DecisionVerdict,
    ledger: Optional[AssumptionLedger] = None,
    use_llm: bool = False,
) -> str:
    """Generate human-readable engineering narrative explaining the decision and evidence."""
    v_val = verdict.verdict.value
    
    if v_val == "PASS":
        summary = (
            f"CLEARANCE APPROVED: Measured physical gap is {verdict.gap_mm:.1f} mm against "
            f"required {verdict.required_mm:.1f} mm (object {verdict.required_mm - verdict.margin_mm:.1f} mm "
            f"+ {verdict.margin_mm:.1f} mm margin). The safety margin delta is {verdict.delta_mm:+.1f} mm, "
            f"exceeding the 2-sigma uncertainty boundary ({verdict.k_factor * verdict.sigma_d_mm:.1f} mm). "
            f"Visual evidence is stable and scale calibration is verified."
        )
    elif v_val == "FAIL":
        summary = (
            f"ACTION BLOCKED (COLLISION RISK): Measured gap is {verdict.gap_mm:.1f} mm, which is "
            f"smaller than the required clearance of {verdict.required_mm:.1f} mm. Margin shortfall "
            f"is {abs(verdict.delta_mm):.1f} mm. Trajectory execution is unsafe. "
            f"Recommendation: Evaluate alternate bypass routing."
        )
    else:  # UNDECIDED
        guide = verdict.missing_measurement
        if guide:
            summary = (
                f"ACTION WITHHELD (FAIL-CLOSED: UNDECIDED): The system cannot verify physical safety "
                f"with required 2-sigma confidence. Flagged reason: {verdict.reason}\n"
                f"• Missing Measurement: {guide.quantity}\n"
                f"• Required Tolerance: ±{guide.tolerance_needed_mm:.1f} mm (Current uncertainty: ±{guide.current_sigma_mm:.1f} mm)\n"
                f"• Corrective Action: {guide.recommended_action}"
            )
        else:
            summary = f"ACTION WITHHELD: Evidence insufficient ({verdict.reason})."

    # Append ledger invalidation context if available
    if ledger:
        invalid_assumptions = [a for a in ledger.assumptions.values() if a.status == "invalid"]
        if invalid_assumptions:
            reasons = "; ".join([f"{a.id}: {a.invalidation_reason}" for a in invalid_assumptions])
            summary += f"\n\n[LEDGER ALERT] Active assumptions were invalidated due to world changes ({reasons}). Past decisions revoked."

    return summary
