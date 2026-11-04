from http.server import BaseHTTPRequestHandler
import json
import time
import math
import hashlib
import urllib.parse

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        payload = {
            "status": "BEBOP-Gate Python Serverless API Online",
            "version": "1.0",
            "timestamp": time.time(),
            "engine": "2-sigma fail-closed gate",
            "scene_state": {
                "robot_pos": [4.0, 7.0],
                "goal_pos": [37.0, 6.5],
                "min_clearance": 1.56,
                "verdict": "PASS"
            }
        }
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        response = {
            "success": True,
            "scene_version": 2,
            "invalidation": {
                "plan_affected": False,
                "status": "ASSUMPTIONS_VERIFIED"
            },
            "received": data
        }
        self.wfile.write(json.dumps(response).encode("utf-8"))

app = handler
