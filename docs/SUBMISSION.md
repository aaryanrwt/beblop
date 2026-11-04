# Meta Global AI Developer Hackathon 2026: Official Submission

## Project Name: BEBOP-Gate
**Tagline:** When Reality Changes: Fail-Closed Physical Clearance Verifier & Auditable State Ledger for Embodied AI  
**Track:** Indie Track · *Push the Frontier*  
**Built With:** Meta SAM 3.1, Meta Llama 3.2-Vision (Local / Ollama), AirLLM, Python, OpenCV, Shapely.

---

### Inspiration
Perception-driven robotics planners increasingly rely on Vision-Language Models to navigate and interact with the physical world. However, recent regulatory investigations (such as NHTSA's EA26002 analysis of automated driving systems failing to detect degraded visibility) and 2026 robotics preprints (VAP-TAMP, AsgardBench) demonstrate that foundation models fail under visual occlusion, glare, and dynamic mid-motion changes — worse, they exhibit uncalibrated confidence, guessing that a tight clearance is safe when it is not.

### What It Does
BEBOP-Gate sits between an AI planner's suggestions and physical motor execution:
1. **The Model Proposes, the Measurement Decides:** Meta vision models propose candidate object masks, but pure deterministic code measures the physical clearance gap in millimetres using an ArUco scale reference.
2. **Tri-State Fail-Closed Verifier:** Rather than forcing a binary yes/no, BEBOP returns `PASS` only when the margin exceeds 2-sigma ($\Delta > 2\sigma_d$), `FAIL` when a collision is certain, and `UNDECIDED` when evidence is ambiguous.
3. **Structured Missing Measurement Guidance:** When `UNDECIDED`, BEBOP outputs the exact required numeric tolerance ($\sigma_{\text{target}} = \frac{|d|}{k}$) and corrective action (e.g. *"Capture unoccluded, square-on top-down camera view"*).
4. **State-Tracking Invalidation Ledger:** A tamper-evident, SHA-256 hash-chained ledger tracks all physical assumptions $A_n$. If an obstacle shifts mid-clip or visibility drops, dependent decisions $D_n$ are instantly revoked, halting motion and evaluating alternate bypass routes $R_2$.

### How We Built It
- **Perception:** Meta SAM 3.1 via Model API, backed by local Meta Llama 3.2-Vision (Ollama) and AirLLM layer-by-layer streaming for memory-efficient edge inference on consumer GPUs (RTX 4050 6GB). Pluggable OpenCV fallback ensures zero-dependency reproducibility.
- **Decision Core:** Pure, unit-tested Python functions calculating Shapely polygon Euclidean distance, ArUco corner perspective distortion, and 2-sigma uncertainty propagation.
- **UI:** Interactive studio matching the retro-futuristic engineering design mockup (`run_demo.py`), featuring frame scrubbers, live canvas rendering, and real-time ledger audits.

### Empirical Results (The False-Approval Defense)
Evaluated across a benchmark of 40 scenes (with 23 unanswerable stress cases including edge occlusion, low light, and marker displacement):
- **Baseline 1 (VLM Direct):** 50.0% false-approval rate (65.2% on unanswerable scenes).
- **Baseline 2 (Single-Shot SAM):** 57.5% false-approval rate (78.3% on unanswerable scenes).
- **Baseline 3 (VAP-TAMP VQA):** 37.5% false-approval rate (47.8% on unanswerable scenes).
- **BEBOP-Gate (Ours):** **0.0% false-approval rate** across all unanswerable scenes with 77.5% valid coverage.

### What's Next for BEBOP
Extending the 2D tabletop clearance verifier into full 3D bounding frustums with multi-camera consensus and integrating directly with ROS 2 Nav2 costmap controllers.
