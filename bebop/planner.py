"""BEBOP-Gate: 2D/3D Obstacle Representation, Collision Verification & A* Path Planner.

Models 3D physical obstacles (cubes, cylinders, cones, barriers, crates, walls),
calculates exact clearance margins with Shapely geometry, and computes collision-free
spline-smoothed paths with deterministic invalidation checks when obstacles move.
"""

from __future__ import annotations
import heapq
import math
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Dict, Optional, Any
import numpy as np
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import nearest_points


@dataclass
class Obstacle3D:
    id: str
    name: str
    type: str  # "cube", "cylinder", "cone", "barrier", "crate", "wall", "polygon"
    x: float
    y: float  # In simulation, y is horizontal/depth (Z in Three.js) or top-down Y (0 to 18)
    z: float = 0.0  # Height elevation
    width: float = 3.0
    depth: float = 3.0
    height: float = 3.0
    rotation: float = 0.0  # in degrees
    color: str = "#E879A0"
    is_moving: bool = False
    velocity: Tuple[float, float] = (0.0, 0.0)
    polygon_points: Optional[List[Tuple[float, float]]] = None

    def get_footprint_polygon(self, margin: float = 0.0) -> Polygon:
        """Calculate 2D top-down footprint polygon with optional margin expansion."""
        hw = (self.width / 2.0) + margin
        hd = (self.depth / 2.0) + margin
        
        if self.type in ("cone", "cylinder"):
            r = max(hw, hd)
            # 16-point circle approximation
            angles = np.linspace(0, 2 * math.pi, 16, endpoint=False)
            pts = [(self.x + r * math.cos(a), self.y + r * math.sin(a)) for a in angles]
            return Polygon(pts)
        
        # Rectangle rotated by self.rotation
        corners = [
            (-hw, -hd),
            (hw, -hd),
            (hw, hd),
            (-hw, hd),
        ]
        rad = math.radians(self.rotation)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)
        
        world_pts = []
        for cx, cy in corners:
            wx = self.x + (cx * cos_r - cy * sin_r)
            wy = self.y + (cx * sin_r + cy * cos_r)
            world_pts.append((wx, wy))
            
        return Polygon(world_pts)


@dataclass
class PathResult:
    valid: bool
    waypoints: List[Tuple[float, float]]
    length: float
    min_clearance: float
    invalid_segment_idx: Optional[int] = None
    colliding_obstacle_id: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "waypoints": [[round(pt[0], 2), round(pt[1], 2)] for pt in self.waypoints],
            "length": round(self.length, 2),
            "min_clearance": round(self.min_clearance, 2),
            "invalid_segment_idx": self.invalid_segment_idx,
            "colliding_obstacle_id": self.colliding_obstacle_id,
            "reason": self.reason,
        }


class BEBOPSceneManager:
    """Manages 3D robotics scene state, versioning, path planning, and verification."""

    def __init__(
        self,
        bounds: Tuple[float, float, float, float] = (0.0, 40.0, 0.0, 18.0),
        robot_radius: float = 0.45,
        safety_margin: float = 0.35,
    ):
        self.min_x, self.max_x, self.min_y, self.max_y = bounds
        self.robot_radius = robot_radius
        self.safety_margin = safety_margin
        self.scene_version: int = 1
        self.robot_pos: Tuple[float, float] = (4.0, 7.0)
        self.goal_pos: Tuple[float, float] = (37.0, 6.5)
        self.obstacles: Dict[str, Obstacle3D] = {}
        self.previous_obstacles: Dict[str, Obstacle3D] = {}
        self.current_plan: Optional[PathResult] = None
        self.active_assumptions: List[Dict[str, Any]] = []

    def load_reference_environment(self):
        """Recreate the exact scene from the supplied reference image."""
        self.obstacles.clear()
        self.robot_pos = (4.0, 7.0)
        self.goal_pos = (37.0, 6.5)
        
        # 1. Pink cube 1 (top left)
        self.add_obstacle(Obstacle3D(
            id="pink_cube_1", name="Pink Cube 1", type="cube",
            x=10.0, y=10.5, width=3.6, depth=3.6, height=3.6, color="#E879A0"
        ))
        # 2. Concrete barrier (bottom left, diagonal striped jersey barrier)
        self.add_obstacle(Obstacle3D(
            id="concrete_barrier", name="Concrete Barrier", type="barrier",
            x=10.8, y=4.5, width=6.8, depth=1.8, height=2.2, rotation=0.0, color="#C4B5A5"
        ))
        # 3. Traffic cone 1 (top center)
        self.add_obstacle(Obstacle3D(
            id="traffic_cone_1", name="Traffic Cone 1", type="cone",
            x=17.5, y=14.0, width=2.6, depth=2.6, height=3.2, color="#FF4081"
        ))
        # 4. Striped barrier (center, diagonal hazard stripes)
        self.add_obstacle(Obstacle3D(
            id="striped_barrier", name="Striped Barrier", type="striped_barrier",
            x=20.2, y=9.8, width=7.6, depth=3.2, height=2.6, rotation=0.0, color="#2D283E"
        ))
        # 5. Pink cube 2 (bottom center)
        self.add_obstacle(Obstacle3D(
            id="pink_cube_2", name="Pink Cube 2", type="cube",
            x=20.0, y=5.2, width=3.8, depth=3.8, height=3.8, color="#E879A0"
        ))
        # 6. Wooden crate (top right)
        self.add_obstacle(Obstacle3D(
            id="wooden_crate", name="Wooden Crate", type="crate",
            x=27.0, y=13.8, width=3.4, depth=3.4, height=3.4, color="#9C7A58"
        ))
        # 7. Traffic cone 2 (bottom right center)
        self.add_obstacle(Obstacle3D(
            id="traffic_cone_2", name="Traffic Cone 2", type="cone",
            x=27.5, y=4.5, width=2.6, depth=2.6, height=3.2, color="#FF4081"
        ))
        # 8. Pink cube 3 (right side near goal)
        self.add_obstacle(Obstacle3D(
            id="pink_cube_3", name="Pink Cube 3", type="cube",
            x=31.8, y=9.5, width=4.0, depth=4.0, height=4.0, color="#E879A0"
        ))
        
        self.scene_version = 1
        self.previous_obstacles = {k: Obstacle3D(**asdict(v)) for k, v in self.obstacles.items()}
        return self.plan_path()

    def add_obstacle(self, obs: Obstacle3D) -> None:
        self.obstacles[obs.id] = obs

    def update_obstacle_pos(self, obs_id: str, new_x: float, new_y: float, new_rot: float = 0.0) -> Dict[str, Any]:
        """Update obstacle position and perform change detection."""
        if obs_id not in self.obstacles:
            return {"changed": False, "error": f"Obstacle {obs_id} not found"}
        
        old_obs = self.obstacles[obs_id]
        dx = new_x - old_obs.x
        dy = new_y - old_obs.y
        displacement = math.sqrt(dx**2 + dy**2)
        
        old_obs.x = new_x
        old_obs.y = new_y
        old_obs.rotation = new_rot
        self.scene_version += 1

        # Check if displacement affects existing plan
        invalidation = self.check_plan_invalidation()
        return {
            "changed": True,
            "obstacle_id": obs_id,
            "displacement": round(displacement, 2),
            "scene_version": self.scene_version,
            "invalidation": invalidation,
        }

    def check_plan_invalidation(self) -> Dict[str, Any]:
        """STEP 5 & 6: Compare scene with plan, identify earliest invalidated assumption."""
        if not self.current_plan or not self.current_plan.valid:
            return {"plan_affected": False, "reason": "No active valid plan"}

        pts = self.current_plan.waypoints
        if len(pts) < 2:
            return {"plan_affected": False}

        required_clearance = self.robot_radius + self.safety_margin

        for i in range(len(pts) - 1):
            segment = LineString([pts[i], pts[i+1]])
            for obs_id, obs in self.obstacles.items():
                poly = obs.get_footprint_polygon(margin=0.0)
                dist = segment.distance(poly)
                if dist < required_clearance:
                    return {
                        "plan_affected": True,
                        "colliding_obstacle_id": obs_id,
                        "invalid_segment_idx": i,
                        "collision_point": (round((pts[i][0] + pts[i+1][0])/2, 2), round((pts[i][1] + pts[i+1][1])/2, 2)),
                        "measured_clearance": round(dist, 2),
                        "required_clearance": round(required_clearance, 2),
                        "invalidated_assumption": f"Assumption A{i+1}: Segment {i}->{i+1} maintains >= {required_clearance:.1f}m clearance from {obs.name}",
                    }

        return {"plan_affected": False}

    def plan_path(self, resolution: float = 0.4) -> PathResult:
        """STEP 3: Plan collision-free trajectory using A* on an inflated obstacle grid."""
        req_clearance = self.robot_radius + self.safety_margin
        
        # Grid dimensions
        cols = int((self.max_x - self.min_x) / resolution)
        rows = int((self.max_y - self.min_y) / resolution)

        start_c = int((self.robot_pos[0] - self.min_x) / resolution)
        start_r = int((self.robot_pos[1] - self.min_y) / resolution)
        goal_c = int((self.goal_pos[0] - self.min_x) / resolution)
        goal_r = int((self.goal_pos[1] - self.min_y) / resolution)

        # Build occupancy grid with inflated obstacles
        grid = np.zeros((rows, cols), dtype=bool)
        polys = [obs.get_footprint_polygon(margin=req_clearance) for obs in self.obstacles.values()]

        for r in range(rows):
            y = self.min_y + (r + 0.5) * resolution
            for c in range(cols):
                x = self.min_x + (c + 0.5) * resolution
                pt = Point(x, y)
                for p in polys:
                    if p.contains(pt):
                        grid[r, c] = True
                        break

        # A* Search
        def heuristic(r, c):
            dx = (c - goal_c) * resolution
            dy = (r - goal_r) * resolution
            return math.sqrt(dx**2 + dy**2)

        open_set = []
        heapq.heappush(open_set, (heuristic(start_r, start_c), 0, start_r, start_c))
        came_from = {}
        cost_so_far = {(start_r, start_c): 0}

        # 8-connected grid moves
        moves = [
            (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
            (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)
        ]

        found = False
        while open_set:
            _, cur_cost, r, c = heapq.heappop(open_set)

            if abs(r - goal_r) <= 1 and abs(c - goal_c) <= 1:
                goal_r, goal_c = r, c
                found = True
                break

            for dr, dc, move_cost in moves:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and not grid[nr, nc]:
                    new_cost = cur_cost + move_cost * resolution
                    if (nr, nc) not in cost_so_far or new_cost < cost_so_far[(nr, nc)]:
                        cost_so_far[(nr, nc)] = new_cost
                        priority = new_cost + heuristic(nr, nc)
                        heapq.heappush(open_set, (priority, new_cost, nr, nc))
                        came_from[(nr, nc)] = (r, c)

        if not found:
            res = PathResult(
                valid=False, waypoints=[], length=0.0, min_clearance=0.0,
                reason="No collision-free path found: all corridors blocked."
            )
            self.current_plan = res
            return res

        # Reconstruct path
        path_grid = []
        curr = (goal_r, goal_c)
        while curr in came_from:
            path_grid.append(curr)
            curr = came_from[curr]
        path_grid.append((start_r, start_c))
        path_grid.reverse()

        # Convert to world coordinates
        raw_waypoints = [(self.min_x + c * resolution, self.min_y + r * resolution) for r, c in path_grid]
        raw_waypoints[0] = self.robot_pos
        raw_waypoints[-1] = self.goal_pos

        # Subsample and smooth waypoints
        step = max(1, len(raw_waypoints) // 12)
        sparse = raw_waypoints[::step]
        if sparse[-1] != self.goal_pos:
            sparse.append(self.goal_pos)

        # Spline / Catmull-Rom interpolation for smooth curves
        smooth_waypoints = self._smooth_waypoints(sparse)

        # Calculate actual minimum clearance and length
        min_clearance = 999.0
        path_geom = LineString(smooth_waypoints)
        for obs in self.obstacles.values():
            poly = obs.get_footprint_polygon(margin=0.0)
            d = path_geom.distance(poly)
            if d < min_clearance:
                min_clearance = d

        length = float(path_geom.length)
        res = PathResult(
            valid=True,
            waypoints=smooth_waypoints,
            length=length,
            min_clearance=min_clearance,
            reason=f"Path planned successfully. Minimum clearance: {min_clearance:.2f}m."
        )
        self.current_plan = res
        return res

    def _smooth_waypoints(self, pts: List[Tuple[float, float]], points_per_segment: int = 4) -> List[Tuple[float, float]]:
        """Generate smooth Catmull-Rom spline waypoints."""
        if len(pts) <= 2:
            return pts
        
        smoothed = [pts[0]]
        for i in range(len(pts) - 1):
            p0 = pts[max(0, i - 1)]
            p1 = pts[i]
            p2 = pts[i + 1]
            p3 = pts[min(len(pts) - 1, i + 2)]

            for t_step in range(1, points_per_segment + 1):
                t = t_step / points_per_segment
                t2 = t * t
                t3 = t2 * t

                # Catmull-Rom spline formula
                x = 0.5 * (
                    (2 * p1[0]) +
                    (-p0[0] + p2[0]) * t +
                    (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                    (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
                )
                y = 0.5 * (
                    (2 * p1[1]) +
                    (-p0[1] + p2[1]) * t +
                    (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                    (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
                )
                smoothed.append((round(x, 2), round(y, 2)))

        return smoothed

    def export_scene_state(self) -> Dict[str, Any]:
        """Export complete structured scene representation."""
        return {
            "scene_version": self.scene_version,
            "bounds": [self.min_x, self.max_x, self.min_y, self.max_y],
            "robot_pos": list(self.robot_pos),
            "goal_pos": list(self.goal_pos),
            "robot_radius": self.robot_radius,
            "safety_margin": self.safety_margin,
            "obstacle_count": len(self.obstacles),
            "obstacles": {k: asdict(v) for k, v in self.obstacles.items()},
            "current_plan": self.current_plan.to_dict() if self.current_plan else None,
        }
