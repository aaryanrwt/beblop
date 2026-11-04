# BEBOP-Gate: Empirical False-Approval Benchmark Report

> **Evaluation Protocol:** 40 tabletop clearance scenes evaluated under controlled degradation (occlusion, blur, low light, distractors, marker obstruction).  
> **Target:** 0.0% false approvals on unanswerable cases.

## Summary Results Table

| Method | Overall False-Approval Rate | False Approvals (Unanswerable) | Answer Coverage | Safety Posture |
|---|---|---|---|---|
| **Baseline 1: VLM Direct** | **20/40 (50.0%)** | **15/23 (65.2%)** | 100.0% | Fail-Open (Guesses blindly) |
| **Baseline 2: Single-Shot SAM** | **23/40 (57.5%)** | **18/23 (78.3%)** | 100.0% | Fail-Open (Zero uncertainty margin) |
| **Baseline 3: VAP-TAMP VQA** | **15/40 (37.5%)** | **11/23 (47.8%)** | 100.0% | Fail-Open (Forced binary choice) |
| **BEBOP-Gate (Ours)** | **0/40 (0.0%)** | **0/23 (0.0%)** | **20.0%** | **Fail-Closed (Abstains with proof)** |

## Key Insights

1. **VLM Hallucination on Degraded Physical Scenes:** VLMs produce high-confidence approvals even when physical obstacle boundaries are occluded by hands or glare.
2. **BEBOP-Gate Defense:** By coupling multi-prompt consensus ($	au = 0.85$), ArUco scale perspective verification, and a 2-sigma margin verifier, BEBOP achieves **zero false approvals**.
3. **Auditable Invalidation:** When reality changes mid-clip, BEBOP's hash-chained ledger invalidates past decisions and evaluates alternate routes with verifiable evidence.
