"""BEBOP-Gate: Standardized 3D Simulation Testing Scenarios.

Implements all 7 required robotics evaluation scenarios:
- Scenario A: Basic Navigation
- Scenario B: Narrow Passage
- Scenario C: Blocked Path
- Scenario D: Dynamic Environment (Mid-clip movement)
- Scenario E: Sudden Appearance
- Scenario F: Occlusion & High Uncertainty (UNDECIDED)
- Scenario G: Complex Navigation & Maze Recovery
- Random Environment Generator
"""

from __future__ import annotations
import random
from typing import Dict, List, Tuple
from .planner import Obstacle3D, BEBOPSceneManager


def load_scenario(manager: BEBOPSceneManager, scenario_key: str) -> str:
    """Load specified scenario into the scene manager."""
    scenario_key = scenario_key.upper().strip()
    manager.obstacles.clear()
    manager.scene_version += 1

    if scenario_key == "A":  # Basic Navigation
        manager.robot_pos = (4.0, 7.0)
        manager.goal_pos = (37.0, 7.0)
        manager.add_obstacle(Obstacle3D(id="pink_cube_1", name="Pink Cube 1", type="cube", x=12.0, y=11.0, width=3.5, depth=3.5, height=3.5, color="#E879A0"))
        manager.add_obstacle(Obstacle3D(id="wooden_crate_1", name="Wooden Crate", type="crate", x=22.0, y=4.0, width=3.5, depth=3.5, height=3.5, color="#9C7A58"))
        manager.add_obstacle(Obstacle3D(id="pink_cube_2", name="Pink Cube 2", type="cube", x=28.0, y=12.0, width=3.5, depth=3.5, height=3.5, color="#E879A0"))
        manager.plan_path()
        return "Scenario A: Basic Navigation loaded with a clear path."

    elif scenario_key == "B":  # Narrow Passage
        manager.robot_pos = (4.0, 9.0)
        manager.goal_pos = (37.0, 9.0)
        # Create upper and lower barriers leaving a narrow 3.4m slot (clearance = 1.4m margin)
        manager.add_obstacle(Obstacle3D(id="wall_top_1", name="Upper Corridor Wall", type="barrier", x=18.0, y=14.0, width=12.0, depth=3.0, height=3.0, color="#C4B5A5"))
        manager.add_obstacle(Obstacle3D(id="wall_bot_1", name="Lower Corridor Wall", type="barrier", x=18.0, y=4.0, width=12.0, depth=3.0, height=3.0, color="#C4B5A5"))
        manager.add_obstacle(Obstacle3D(id="cone_guide_1", name="Pylon 1", type="cone", x=18.0, y=11.2, width=1.8, depth=1.8, height=2.8, color="#FF4081"))
        manager.add_obstacle(Obstacle3D(id="cone_guide_2", name="Pylon 2", type="cone", x=18.0, y=6.8, width=1.8, depth=1.8, height=2.8, color="#FF4081"))
        manager.plan_path()
        return "Scenario B: Narrow Passage loaded. Robot must thread through the calibrated corridor."

    elif scenario_key == "C":  # Blocked Path
        manager.load_reference_environment()
        # Insert a massive blocking container right on the upper path corridor at (20.2, 12.5)
        manager.add_obstacle(Obstacle3D(id="blocker_crate", name="Blocking Freight Container", type="crate", x=20.2, y=12.5, width=6.0, depth=4.0, height=4.5, color="#EF4444"))
        manager.plan_path()
        return "Scenario C: Blocked Path loaded. Primary route obstructed; system must detect blockage."

    elif scenario_key == "D":  # Dynamic Environment
        manager.load_reference_environment()
        # Set striped barrier as moving
        manager.obstacles["striped_barrier"].is_moving = True
        manager.plan_path()
        return "Scenario D: Dynamic Environment loaded. Striped barrier ready for mid-transit displacement."

    elif scenario_key == "E":  # Sudden Appearance
        manager.load_reference_environment()
        manager.plan_path()
        return "Scenario E: Sudden Appearance ready. Initially clear; trigger to spawn surprise obstacle."

    elif scenario_key == "F":  # Occlusion & Uncertainty
        manager.robot_pos = (4.0, 7.0)
        manager.goal_pos = (37.0, 7.0)
        # Giant wall partially occluding a sharp corner
        manager.add_obstacle(Obstacle3D(id="occluding_wall", name="Occluding Partition", type="wall", x=16.0, y=9.0, width=2.0, depth=10.0, height=4.5, color="#4C3A69"))
        manager.add_obstacle(Obstacle3D(id="hidden_cone", name="Hidden Pylon (Uncertain)", type="cone", x=19.0, y=10.0, width=2.0, depth=2.0, height=2.5, color="#F59E0B"))
        manager.plan_path()
        return "Scenario F: Occlusion loaded. Visual sensor cannot verify clearance around blind partition; verifier flags UNDECIDED."

    elif scenario_key == "G":  # Complex Navigation
        manager.robot_pos = (4.0, 4.0)
        manager.goal_pos = (37.0, 14.0)
        # Multi-stage maze with alternating dead ends
        manager.add_obstacle(Obstacle3D(id="maze_1", name="Maze Wall 1", type="barrier", x=10.0, y=12.0, width=2.5, depth=8.0, height=3.0, color="#C4B5A5"))
        manager.add_obstacle(Obstacle3D(id="maze_2", name="Maze Wall 2", type="barrier", x=18.0, y=5.0, width=2.5, depth=8.0, height=3.0, color="#C4B5A5"))
        manager.add_obstacle(Obstacle3D(id="maze_3", name="Maze Wall 3", type="barrier", x=26.0, y=12.0, width=2.5, depth=8.0, height=3.0, color="#C4B5A5"))
        manager.add_obstacle(Obstacle3D(id="dead_end_cone", name="Dead-end Marker", type="cone", x=22.0, y=14.0, width=2.0, depth=2.0, height=3.0, color="#FF4081"))
        manager.add_obstacle(Obstacle3D(id="crate_choke", name="Choke Point Crate", type="crate", x=32.0, y=8.0, width=3.5, depth=3.5, height=3.5, color="#9C7A58"))
        manager.plan_path()
        return "Scenario G: Complex Navigation loaded with multiple obstacle classes and chokepoints."

    elif scenario_key == "H":  # ACDC Adverse Fog & Visibility (NHTSA EA26002)
        manager.robot_pos = (4.0, 9.0)
        manager.goal_pos = (37.0, 9.0)
        # Narrow foggy channel: gap is within optical error sigma under heavy scattering
        manager.add_obstacle(Obstacle3D(id="fog_barrier_top", name="Fog-Obscured Wall North", type="barrier", x=19.0, y=13.0, width=14.0, depth=2.5, height=3.5, color="#7E6E8F"))
        manager.add_obstacle(Obstacle3D(id="fog_barrier_bot", name="Fog-Obscured Wall South", type="barrier", x=19.0, y=5.0, width=14.0, depth=2.5, height=3.5, color="#7E6E8F"))
        manager.add_obstacle(Obstacle3D(id="fog_choke_cone", name="Low-Contrast Pylon", type="cone", x=19.0, y=9.5, width=1.6, depth=1.6, height=2.4, color="#A78BFA"))
        manager.plan_path()
        return "Scenario H: ACDC Adverse Fog & Visibility loaded. Optical noise sigma exceeds clearance bounds (|d| < 2*sigma); verifier abstains as UNDECIDED."

    elif scenario_key == "I":  # AsgardBench Hand-Shift Displacement
        manager.robot_pos = (4.0, 7.0)
        manager.goal_pos = (37.0, 7.0)
        # Dynamic container placed at corridor choke point with active movement
        manager.add_obstacle(Obstacle3D(id="asgard_shift_box", name="AsgardBench Shift Crate", type="crate", x=20.0, y=7.0, width=4.0, depth=4.0, height=3.5, color="#EC4899", is_moving=True))
        manager.add_obstacle(Obstacle3D(id="asgard_wall_1", name="Corridor Flank 1", type="barrier", x=20.0, y=14.0, width=10.0, depth=2.5, height=3.0, color="#C4B5A5"))
        manager.add_obstacle(Obstacle3D(id="asgard_wall_2", name="Corridor Flank 2", type="barrier", x=20.0, y=1.0, width=10.0, depth=2.5, height=3.0, color="#C4B5A5"))
        manager.plan_path()
        return "Scenario I: AsgardBench Hand-Shift loaded. Crate shifts >18px mid-transit; SHA-256 ledger revokes prior decision and recovers path."

    elif scenario_key == "J":  # SeCVOS Vanishing Obstacle / Stale State
        manager.robot_pos = (4.0, 7.0)
        manager.goal_pos = (37.0, 7.0)
        # Ghost obstacle simulating SeCVOS 30.2% disappearance rate
        manager.add_obstacle(Obstacle3D(id="secvos_vanishing_block", name="SeCVOS Disappearing Block", type="cube", x=18.0, y=7.0, width=3.5, depth=3.5, height=3.5, color="#F43F5E", is_moving=True))
        manager.add_obstacle(Obstacle3D(id="pylon_flank", name="Safety Pylon", type="cone", x=18.0, y=13.0, width=2.0, depth=2.0, height=2.8, color="#FF4081"))
        manager.plan_path()
        return "Scenario J: SeCVOS Vanishing Obstacle loaded. Models assume clear space when obstacle disappears; BEBOP marks state stale & re-observes."

    elif scenario_key == "K":  # Multi-Barricade Chokepoint & Stress Test
        manager.robot_pos = (4.0, 14.0)
        manager.goal_pos = (37.0, 4.0)
        # Serpentine chokepoints
        manager.add_obstacle(Obstacle3D(id="serp_barrier_1", name="Jersey Barricade 1", type="barrier", x=12.0, y=10.0, width=7.0, depth=2.2, height=2.8, color="#C4B5A5"))
        manager.add_obstacle(Obstacle3D(id="serp_barrier_2", name="Striped Hazard Wall", type="barrier", x=22.0, y=8.0, width=7.0, depth=2.2, height=2.8, color="#F59E0B"))
        manager.add_obstacle(Obstacle3D(id="serp_crate", name="Central Freight Box", type="crate", x=17.0, y=15.0, width=3.5, depth=3.5, height=3.5, color="#9C7A58"))
        manager.add_obstacle(Obstacle3D(id="serp_cone_1", name="Apex Pylon", type="cone", x=27.0, y=12.0, width=1.8, depth=1.8, height=2.8, color="#EC4899"))
        manager.add_obstacle(Obstacle3D(id="serp_cone_2", name="Base Pylon", type="cone", x=30.0, y=3.0, width=1.8, depth=1.8, height=2.8, color="#EC4899"))
        manager.plan_path()
        return "Scenario K: Multi-Barricade Chokepoint loaded. Tests serpentine routing with tight clearance verification."

    else:  # Default reference image environment
        manager.load_reference_environment()
        return "Reference Environment loaded matching the target photograph."


def generate_random_environment(manager: BEBOPSceneManager, num_obstacles: int = 8) -> str:
    """Generate a collision-free randomized obstacle field."""
    manager.obstacles.clear()
    manager.scene_version += 1
    
    manager.robot_pos = (4.0, round(random.uniform(4.0, 14.0), 1))
    manager.goal_pos = (36.0, round(random.uniform(4.0, 14.0), 1))

    types = ["cube", "cylinder", "cone", "barrier", "crate"]
    colors = ["#E879A0", "#9C7A58", "#FF4081", "#C4B5A5", "#7928CA"]

    for i in range(num_obstacles):
        t = random.choice(types)
        c = random.choice(colors)
        x = round(random.uniform(9.0, 31.0), 1)
        y = round(random.uniform(3.0, 15.0), 1)
        w = round(random.uniform(2.5, 4.5), 1)
        d = round(random.uniform(2.5, 4.5), 1)
        h = round(random.uniform(2.0, 4.0), 1)
        rot = round(random.uniform(0.0, 90.0), 1) if t in ("barrier", "cube", "crate") else 0.0

        obs = Obstacle3D(
            id=f"rand_obs_{i+1}",
            name=f"Random {t.capitalize()} {i+1}",
            type=t,
            x=x, y=y,
            width=w, depth=d, height=h,
            rotation=rot,
            color=c,
        )
        manager.add_obstacle(obs)

    manager.plan_path()
    return f"Random Environment generated with {num_obstacles} obstacles."
