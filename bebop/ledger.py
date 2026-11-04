"""BEBOP-Gate: State-tracking assumption ledger and invalidation engine.

Maintains a tamper-evident, SHA-256 hash-chained record of all physical assumptions,
evidence frames, and dependent decisions. Detects when reality changes mid-clip and
immediately invalidates stale approvals.
"""

from __future__ import annotations
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import numpy as np


def compute_mask_fingerprint(mask: np.ndarray) -> Dict[str, Any]:
    """Calculate centroid, area, and spatial hash of a binary mask."""
    if mask is None or not np.any(mask):
        return {"centroid": [0, 0], "area": 0, "mask_hash": "EMPTY"}
    
    y_indices, x_indices = np.where(mask > 0)
    area = int(len(x_indices))
    cx = float(np.mean(x_indices)) if area > 0 else 0.0
    cy = float(np.mean(y_indices)) if area > 0 else 0.0
    
    # Fast spatial downsampled hash
    downsampled = mask[::8, ::8]
    mask_bytes = (downsampled > 0).astype(np.uint8).tobytes()
    m_hash = hashlib.sha256(mask_bytes).hexdigest()[:16]
    
    return {
        "centroid": [round(cx, 1), round(cy, 1)],
        "area": area,
        "mask_hash": m_hash,
    }


def compute_mask_iou(mask1: np.ndarray, mask2: np.ndarray) -> float:
    """Calculate Intersection over Union (IoU) between two masks."""
    if mask1 is None or mask2 is None:
        return 0.0
    m1 = mask1 > 0
    m2 = mask2 > 0
    intersection = np.logical_and(m1, m2).sum()
    union = np.logical_or(m1, m2).sum()
    if union == 0:
        return 1.0 if intersection == 0 else 0.0
    return float(intersection / union)


@dataclass
class EvidenceItem:
    frame: str
    mask_ref: str
    prompt: str


@dataclass
class Assumption:
    id: str
    text: str
    status: str  # "valid", "invalid", "unknown"
    evidence: List[EvidenceItem] = field(default_factory=list)
    inputs_fingerprint: Dict[str, Any] = field(default_factory=dict)
    invalidation_reason: Optional[str] = None


@dataclass
class Decision:
    id: str
    route: str
    depends_on: List[str]
    verdict: str
    status: str = "ACTIVE"  # "ACTIVE", "INVALIDATED"
    invalidation_timestamp: Optional[float] = None


class AssumptionLedger:
    """Tamper-evident, hash-chained ledger for robotic clearance decisions."""

    def __init__(self, scene_id: str = "s001"):
        self.scene_id = scene_id
        self.entries: List[Dict[str, Any]] = []
        self.assumptions: Dict[str, Assumption] = {}
        self.decisions: Dict[str, Decision] = {}

    @property
    def head_hash(self) -> str:
        return self.entries[-1]["hash"] if self.entries else "GENESIS"

    def append_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Append an event to the hash chain."""
        entry = {
            "index": len(self.entries),
            "timestamp": round(time.time(), 3),
            "event": event_type,
            "payload": payload,
            "prev_hash": self.head_hash,
        }
        body_str = json.dumps(entry, sort_keys=True)
        entry["hash"] = hashlib.sha256(body_str.encode()).hexdigest()
        self.entries.append(entry)
        return entry

    def record_assumption(
        self,
        assumption_id: str,
        text: str,
        frame: str,
        mask_fingerprint: Dict[str, Any],
        prompt: str = "obstacle",
    ) -> Assumption:
        """Register a new physical assumption backed by visual evidence."""
        assump = Assumption(
            id=assumption_id,
            text=text,
            status="valid",
            evidence=[EvidenceItem(frame=frame, mask_ref=f"mask_{frame}.png", prompt=prompt)],
            inputs_fingerprint=mask_fingerprint,
        )
        self.assumptions[assumption_id] = assump
        self.append_event("ASSUMPTION_RECORDED", {
            "assumption_id": assumption_id,
            "text": text,
            "frame": frame,
            "inputs_fingerprint": mask_fingerprint,
        })
        return assump

    def record_decision(
        self,
        decision_id: str,
        route: str,
        depends_on: List[str],
        verdict: str,
    ) -> Decision:
        """Commit an approved action decision dependent on stated assumptions."""
        dec = Decision(
            id=decision_id,
            route=route,
            depends_on=depends_on,
            verdict=verdict,
            status="ACTIVE",
        )
        self.decisions[decision_id] = dec
        self.append_event("DECISION_COMMITTED", {
            "decision_id": decision_id,
            "route": route,
            "depends_on": depends_on,
            "verdict": verdict,
        })
        return dec

    def update_frame(
        self,
        frame_name: str,
        new_masks: Dict[str, np.ndarray],
        reference_masks: Dict[str, np.ndarray],
        centroid_drift_px_max: float = 18.0,
        min_iou: float = 0.80,
    ) -> List[str]:
        """Evaluate new frame against active assumptions and invalidate if reality changed.
        
        Returns list of newly invalidated decision IDs.
        """
        invalidated_decisions = []

        for a_id, assump in self.assumptions.items():
            if assump.status != "valid":
                continue

            # Check each object in new_masks
            for obj_name, new_mask in new_masks.items():
                ref_mask = reference_masks.get(obj_name)
                if ref_mask is None or new_mask is None:
                    continue

                # 1. IoU check
                iou = compute_mask_iou(new_mask, ref_mask)
                # 2. Centroid drift check
                fp_new = compute_mask_fingerprint(new_mask)
                fp_old = assump.inputs_fingerprint.get(obj_name, compute_mask_fingerprint(ref_mask))
                
                dx = fp_new["centroid"][0] - fp_old["centroid"][0]
                dy = fp_new["centroid"][1] - fp_old["centroid"][1]
                drift = (dx**2 + dy**2) ** 0.5

                if iou < min_iou or drift > centroid_drift_px_max:
                    reason = f"{obj_name} shifted: drift={drift:.1f}px (limit {centroid_drift_px_max}px), IoU={iou:.2f} (min {min_iou})"
                    assump.status = "invalid"
                    assump.invalidation_reason = reason
                    
                    self.append_event("ASSUMPTION_INVALIDATED", {
                        "assumption_id": a_id,
                        "frame": frame_name,
                        "reason": reason,
                        "drift_px": round(drift, 1),
                        "iou": round(iou, 2),
                    })

                    # Invalidate dependent decisions
                    for d_id, dec in self.decisions.items():
                        if a_id in dec.depends_on and dec.status == "ACTIVE":
                            dec.status = "INVALIDATED"
                            dec.invalidation_timestamp = time.time()
                            invalidated_decisions.append(d_id)
                            
                            self.append_event("DECISION_INVALIDATED", {
                                "decision_id": d_id,
                                "failed_assumption": a_id,
                                "frame": frame_name,
                            })

        return invalidated_decisions

    def verify_integrity(self) -> bool:
        """Verify the cryptographic SHA-256 chain of all recorded events."""
        prev = "GENESIS"
        for e in self.entries:
            if e["prev_hash"] != prev:
                return False
            body = {k: e[k] for k in ("index", "timestamp", "event", "payload", "prev_hash")}
            expected_hash = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            if expected_hash != e["hash"]:
                return False
            prev = e["hash"]
        return True

    def export_summary(self) -> Dict[str, Any]:
        """Export serialized representation of ledger state."""
        return {
            "scene_id": self.scene_id,
            "chain_valid": self.verify_integrity(),
            "head_hash": self.head_hash,
            "assumptions": {k: asdict(v) for k, v in self.assumptions.items()},
            "decisions": {k: asdict(v) for k, v in self.decisions.items()},
            "event_count": len(self.entries),
            "events": self.entries,
        }
