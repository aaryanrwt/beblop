# BEBOP-Gate: 2-Minute Demo Video Script

> **Target Duration:** 2 minutes (120 seconds)  
> **Visual Focus:** Screen recording of `http://127.0.0.1:8501` interactive studio + live benchmark console.

---

### [0:00 - 0:25] The Problem: Why Autonomous Planners Crash
- **Visual:** Open with headline graphic: **WHEN REALITY CHANGES**.
- **Voiceover:**  
  *"In robotics and perception-driven AI, when a Vision-Language Model looks at a scene and says 'go', how do you know it's safe? NHTSA's recent investigation into Tesla FSD (EA26002) centers on systems failing to detect degraded visibility. Preprints like VAP-TAMP show that VLMs fail under occlusion, glare, and movement — and worse, they guess with high confidence. Asking an LLM 'will this collide?' is not safety engineering."*

---

### [0:25 - 0:50] The Solution: BEBOP-Gate Core Philosophy
- **Visual:** Switch to **BEBOP Interactive Studio** (`run_demo.py`).
- **Voiceover:**  
  *"Meet BEBOP-Gate. Our principle is simple: The model proposes, the measurement decides. BEBOP is a fail-closed verifier that sits between the AI's plan and physical execution. It uses Meta's vision models to propose masks, but code calculates millimeter clearance with 2-sigma confidence bounds. Any missing marker, perspective distortion, or edge occlusion forces a fail-closed UNDECIDED verdict with the exact missing measurement."*

---

### [0:50 - 1:25] Live Demo: When Reality Changes
- **Visual:** 
  1. Click **Scenario 1 (Clear Pass)**: Show Green `PASS` (+27.0 mm clearance).
  2. Click **Scenario 2 (When Reality Changes)**: Scrub from $t_0 \to t_1$. Show obstacle shift 32px $\to$ instant red `FAIL` and `ASSUMPTION_INVALIDATED` in the ledger $\to$ scrub to $t_2$ showing green recovered alternate route $R_2$.
  3. Click **Scenario 3 (Hand Occlusion)**: Show Amber `UNDECIDED` and highlight the **Missing Measurement Advisory Card**: *"Required tolerance: ±3.2 mm. Unoccluded top-down view required."*
- **Voiceover:**  
  *"Watch what happens when reality changes mid-clip. In frame t0, the passage is clear, verified by assumption A1 in our SHA-256 hash-chained ledger. In frame t1, an obstacle shifts by 32 pixels. BEBOP immediately detects the contour drift, revokes approval, halts motion, and verifies alternate route R2. When a hand occludes the edge, BEBOP doesn't guess like a VLM — it abstains with an explicit tolerance target: ±3.2 millimeters."*

---

### [1:25 - 1:45] The Proof: 40-Scene Head-to-Head Benchmark
- **Visual:** Scroll down to the **Measured Benchmark Table** in the UI or show terminal `python bench/run_bench.py`.
- **Voiceover:**  
  *"We benchmarked BEBOP head-to-head across 40 real and synthetic scenes against three baselines: Direct VLM prompting, Single-shot SAM, and a VAP-TAMP majority vote. On unanswerable stress cases, competing VLMs suffered a 50% to 65% false-approval rate — guessing yes when clearance was impossible. BEBOP-Gate achieved zero false approvals. 0.0%."*

---

### [1:45 - 2:00] Wrap-Up & Meta Stack
- **Visual:** Show Architecture diagram & GitHub repo.
- **Voiceover:**  
  *"Built for the Meta Global AI Developer Hackathon using Meta SAM 3.1 and local Meta Llama 3.2-Vision with AirLLM streaming for edge deployment. BEBOP is fully auditable, open-source, and verifiable. Because when reality changes, evidence must decide."*
