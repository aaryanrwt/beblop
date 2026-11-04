"""Unit tests for BEBOP state invalidation ledger and hash-chain audit integrity."""

import numpy as np
import pytest
from bebop.ledger import AssumptionLedger, compute_mask_fingerprint


def test_ledger_hash_chain_integrity():
    ledger = AssumptionLedger("scene_test_01")
    dummy_mask = np.zeros((100, 100), dtype=np.uint8)
    dummy_mask[20:50, 20:50] = 255
    fp = compute_mask_fingerprint(dummy_mask)

    ledger.record_assumption("A1", "gap >= object_width + margin", "f001", {"blocker": fp})
    ledger.record_decision("D1", "R1", ["A1"], "PASS")

    assert ledger.verify_integrity() is True
    assert len(ledger.entries) == 2
    assert ledger.head_hash != "GENESIS"


def test_invalidation_when_reality_changes():
    ledger = AssumptionLedger("scene_test_02")
    
    # Initial frame f001: obstacle at (35, 35)
    mask_initial = np.zeros((100, 100), dtype=np.uint8)
    mask_initial[20:50, 20:50] = 255
    fp_initial = compute_mask_fingerprint(mask_initial)

    ledger.record_assumption("A1", "clearance > 120mm", "f001", {"obstacle": fp_initial})
    ledger.record_decision("D1", "route_north", ["A1"], "PASS")

    assert ledger.decisions["D1"].status == "ACTIVE"

    # Frame f002: no change
    invalidated = ledger.update_frame(
        "f002",
        {"obstacle": mask_initial},
        {"obstacle": mask_initial},
    )
    assert len(invalidated) == 0
    assert ledger.decisions["D1"].status == "ACTIVE"
    assert ledger.assumptions["A1"].status == "valid"

    # Frame f003: obstacle shifted by 30 pixels!
    mask_shifted = np.zeros((100, 100), dtype=np.uint8)
    mask_shifted[50:80, 50:80] = 255

    invalidated = ledger.update_frame(
        "f003",
        {"obstacle": mask_shifted},
        {"obstacle": mask_initial},
    )

    assert "D1" in invalidated
    assert ledger.decisions["D1"].status == "INVALIDATED"
    assert ledger.assumptions["A1"].status == "invalid"
    assert "shifted" in ledger.assumptions["A1"].invalidation_reason
    assert ledger.verify_integrity() is True
