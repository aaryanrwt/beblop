"""BEBOP-Gate: Full-Stack Robotics Simulation & Testing Lab API Server.

Integrates the 3D interactive testing environment directly with the actual BEBOP
deterministic verifier, hash-chained assumption ledger, and A* path planner.
"""

from __future__ import annotations
import http.server
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Dict, Any

from .planner import BEBOPSceneManager, Obstacle3D
from .scenarios import load_scenario, generate_random_environment
from .ledger import AssumptionLedger, compute_mask_fingerprint
from .verdict import compute_verdict, check_alternate_route, DecisionVerdict, VerdictStatus
from .measure import MeasurementResult
from .explain import generate_explanation


class BEBOPServerState:
    """Singleton server state maintaining the live scene manager and ledger."""

    def __init__(self):
        self.scene_mgr = BEBOPSceneManager()
        self.scene_mgr.load_reference_environment()
        self.ledger = AssumptionLedger("bebop_3d_lab_session")
        self.event_log: list[Dict[str, Any]] = []
        self.record_log_event("SYSTEM_INIT", "BEBOP 3D Testing Lab initialized with reference environment.")
        self._sync_ledger_with_plan()

    def record_log_event(self, event_type: str, details: str):
        now_str = time.strftime("%H:%M:%S")
        entry = {"time": now_str, "type": event_type, "details": details}
        self.event_log.insert(0, entry)
        if len(self.event_log) > 50:
            self.event_log.pop()

    def _sync_ledger_with_plan(self):
        """Register active assumptions for the current path in the hash-chained ledger."""
        plan = self.scene_mgr.current_plan
        if not plan or not plan.valid:
            return
        
        # Record waypoint clearances
        for i in range(min(5, len(plan.waypoints) - 1)):
            p1 = plan.waypoints[i]
            p2 = plan.waypoints[i + 1]
            a_id = f"A{i+1}"
            text = f"Clearance segment {i}->{i+1} maintains >= 1.4m margin from obstacles"
            fp = {"segment": [p1, p2], "min_clearance": plan.min_clearance}
            self.ledger.record_assumption(a_id, text, f"t{self.scene_mgr.scene_version}", fp)

        self.ledger.record_decision("D1", "route_primary", [f"A{i+1}" for i in range(min(5, len(plan.waypoints) - 1))], "PASS")


# Global state instance
STATE = BEBOPServerState()
APP_DIR = Path(__file__).resolve().parent.parent / "app"


class BEBOPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Handles both REST API calls for BEBOP and serves 3D web assets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, data: Dict[str, Any], status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _parse_post_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)
        return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/scene":
            state = STATE.scene_mgr.export_scene_state()
            state["event_log"] = STATE.event_log
            state["ledger_summary"] = STATE.ledger.export_summary()
            self._send_json(state)

        elif path == "/api/ledger":
            self._send_json(STATE.ledger.export_summary())

        elif path == "/api/events":
            self._send_json({"events": STATE.event_log})

        elif path in ("/", "/problem-solution", "/simulation", "/demo", "/problem", "/solution"):
            self.path = "/index.html"
            super().do_GET()

        else:
            # Fallback to static files in app/
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        payload = self._parse_post_json()

        if path == "/api/scene/reset":
            t0 = time.time()
            plan = STATE.scene_mgr.load_reference_environment()
            STATE._sync_ledger_with_plan()
            STATE.record_log_event("RESET_ENV", "Environment reset to reference photograph.")
            resp = STATE.scene_mgr.export_scene_state()
            resp["message"] = "Environment reset to reference photograph."
            resp["processing_time_ms"] = round((time.time() - t0) * 1000, 1)
            self._send_json(resp)

        elif path == "/api/scene/scenario":
            t0 = time.time()
            scenario_key = payload.get("scenario", "A")
            if scenario_key == "RANDOM":
                msg = generate_random_environment(STATE.scene_mgr)
            else:
                msg = load_scenario(STATE.scene_mgr, scenario_key)
            STATE._sync_ledger_with_plan()
            STATE.record_log_event("LOAD_SCENARIO", f"Loaded Scenario {scenario_key}: {msg}")
            resp = STATE.scene_mgr.export_scene_state()
            resp["message"] = msg
            resp["scenario"] = scenario_key
            if scenario_key == "H":
                rob_w = STATE.scene_mgr.robot_radius * 2000.0
                meas = MeasurementResult(
                    gap_mm=rob_w + 10.0,
                    sigma_gap=14.5,
                    object_width_mm=rob_w,
                    sigma_width=2.5,
                    n_samples=5,
                    scale_mm_per_px=1.2,
                )
                verdict = compute_verdict(meas, margin_mm=5.0, k=2.0)
                resp["verdict"] = verdict.to_dict()
                resp["adverse_env"] = "fog"
                STATE.record_log_event("ACDC_FOG_DETECTED", "Optical noise sigma=14.5mm > clearance. Fail-closed verifier abstains as UNDECIDED.")
            elif scenario_key == "I":
                resp["adverse_env"] = "asgard_shift"
                STATE.record_log_event("ASGARD_BENCH_INIT", "Dynamic container armed for mid-transit shift (>18px centroid drift threshold).")
            elif scenario_key == "J":
                resp["adverse_env"] = "secvos_vanishing"
                STATE.record_log_event("SECVOS_STALE_INIT", "Vanishing block armed. Testing stale perception revocation without collision.")
            elif scenario_key == "K":
                resp["adverse_env"] = "rain"
                STATE.record_log_event("RAIN_STRESS_INIT", "Serpentine multi-barricade corridor loaded under simulated adverse rain conditions.")
            resp["processing_time_ms"] = round((time.time() - t0) * 1000, 1)
            self._send_json(resp)

        elif path == "/api/obstacle/move":
            t0 = time.time()
            obs_id = payload.get("id")
            new_x = float(payload.get("x", 0.0))
            new_y = float(payload.get("y", 0.0))
            new_rot = float(payload.get("rotation", 0.0))

            old_plan = STATE.scene_mgr.current_plan
            res = STATE.scene_mgr.update_obstacle_pos(obs_id, new_x, new_y, new_rot)
            
            invalidation = res.get("invalidation", {})
            plan_affected = invalidation.get("plan_affected", False)

            if plan_affected:
                # STEP 5 & 6: Invalidate ledger
                failed_assump = invalidation.get("invalidated_assumption", "Assumption violated")
                STATE.record_log_event("OBSTACLE_MOVED", f"{obs_id} shifted to ({new_x:.1f}, {new_y:.1f}).")
                STATE.record_log_event("ASSUMPTION_INVALIDATED", failed_assump)
                
                # Invalidate in ledger
                for a in STATE.ledger.assumptions.values():
                    a.status = "invalid"
                    a.invalidation_reason = f"Obstacle {obs_id} collided with path corridor."
                for d in STATE.ledger.decisions.values():
                    d.status = "INVALIDATED"
                
                # STEP 7: Re-plan / Recover
                STATE.record_log_event("REPLAN_INITIATED", "BEBOP generating recovered route avoiding obstacle.")
                new_plan = STATE.scene_mgr.plan_path()
                
                # STEP 8: Deterministic Verification
                meas = MeasurementResult(
                    gap_mm=new_plan.min_clearance * 1000.0 if new_plan.valid else 0.0,
                    sigma_gap=4.2,
                    object_width_mm=STATE.scene_mgr.robot_radius * 2000.0,
                    sigma_width=2.5,
                    n_samples=15,
                    scale_mm_per_px=0.5
                )
                verdict = compute_verdict(meas, margin_mm=STATE.scene_mgr.safety_margin * 1000.0, k=2.0)
                STATE.record_log_event("VERIFIED", f"Recovered route verified: {verdict.verdict.value} (Min clearance: {new_plan.min_clearance:.2f}m).")
                
                STATE.ledger.record_decision("D2", "route_recovered", ["A_recov"], verdict.verdict.value)
                
                resp = STATE.scene_mgr.export_scene_state()
                resp["invalidation"] = invalidation
                resp["previous_plan"] = old_plan.to_dict() if old_plan else None
                resp["verdict"] = verdict.to_dict()
                resp["processing_time_ms"] = round((time.time() - t0) * 1000, 1)
                self._send_json(resp)
            else:
                resp = STATE.scene_mgr.export_scene_state()
                resp["invalidation"] = {"plan_affected": False}
                resp["processing_time_ms"] = round((time.time() - t0) * 1000, 1)
                self._send_json(resp)

        elif path == "/api/obstacle/add":
            t0 = time.time()
            obs_type = payload.get("type", "cube")
            x = float(payload.get("x", 20.0))
            y = float(payload.get("y", 10.0))
            w = float(payload.get("width", 3.0))
            d = float(payload.get("depth", 3.0))
            h = float(payload.get("height", 3.0))
            color = payload.get("color", "#E879A0")
            
            new_id = f"user_{obs_type}_{int(time.time())}"
            obs = Obstacle3D(id=new_id, name=f"User {obs_type.capitalize()}", type=obs_type, x=x, y=y, width=w, depth=d, height=h, color=color)
            STATE.scene_mgr.add_obstacle(obs)
            STATE.scene_mgr.scene_version += 1
            STATE.record_log_event("OBSTACLE_ADDED", f"Added {obs_type} at ({x:.1f}, {y:.1f}).")
            
            # Check if affects path
            inval = STATE.scene_mgr.check_plan_invalidation()
            if inval.get("plan_affected", False):
                STATE.record_log_event("ASSUMPTION_INVALIDATED", "New obstacle intersected planned path.")
                STATE.scene_mgr.plan_path()
            
            resp = STATE.scene_mgr.export_scene_state()
            resp["processing_time_ms"] = round((time.time() - t0) * 1000, 1)
            self._send_json(resp)

        elif path == "/api/obstacle/delete":
            t0 = time.time()
            obs_id = payload.get("id")
            if obs_id in STATE.scene_mgr.obstacles:
                del STATE.scene_mgr.obstacles[obs_id]
                STATE.scene_mgr.scene_version += 1
                STATE.record_log_event("OBSTACLE_DELETED", f"Removed obstacle {obs_id}.")
                STATE.scene_mgr.plan_path()
            resp = STATE.scene_mgr.export_scene_state()
            resp["processing_time_ms"] = round((time.time() - t0) * 1000, 1)
            self._send_json(resp)

        elif path == "/api/plan":
            t0 = time.time()
            plan = STATE.scene_mgr.plan_path()
            STATE._sync_ledger_with_plan()
            STATE.record_log_event("PLAN_COMPUTED", f"Path generated with {len(plan.waypoints)} waypoints.")
            resp = STATE.scene_mgr.export_scene_state()
            resp["processing_time_ms"] = round((time.time() - t0) * 1000, 1)
            self._send_json(resp)

        elif path == "/api/verify":
            t0 = time.time()
            plan = STATE.scene_mgr.current_plan
            is_valid = plan.valid if plan else False
            min_clearance = plan.min_clearance if plan else 0.0
            
            # Corridor width available for passage
            corridor_width_mm = (min_clearance + STATE.scene_mgr.robot_radius) * 2000.0 if is_valid else 0.0
            robot_width_mm = STATE.scene_mgr.robot_radius * 2000.0
            margin_mm = STATE.scene_mgr.safety_margin * 1000.0

            meas = MeasurementResult(
                gap_mm=corridor_width_mm,
                sigma_gap=4.2,
                object_width_mm=robot_width_mm,
                sigma_width=2.5,
                n_samples=15,
                scale_mm_per_px=0.5
            )
            verdict = compute_verdict(meas, margin_mm=margin_mm, k=2.0)
            explanation = generate_explanation(verdict, STATE.ledger)
            STATE.record_log_event("VERIFY_RUN", f"Deterministic verification result: {verdict.verdict.value}")
            self._send_json({
                "verdict": verdict.to_dict(),
                "explanation": explanation,
                "processing_time_ms": round((time.time() - t0) * 1000, 1)
            })

        else:
            self.send_error(404, "Endpoint not found")


def run_server(port: int = 8501):
    print("=" * 70)
    print("  [BEBOP] 3D Robotics Simulation & Testing Lab API Server")
    print(f"  Serving at: http://127.0.0.1:{port}")
    print("=" * 70)
    server = http.server.ThreadingHTTPServer(("", port), BEBOPRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8501
    run_server(port)
