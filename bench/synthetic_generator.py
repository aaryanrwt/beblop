"""BEBOP-Gate: Synthetic scene image generator for reproducible benchmarks.

Generates 40 OpenCV-rendered test images with ground-truth ArUco markers,
obstacle blocks, moving objects, and controlled visual corruptions.
"""

from __future__ import annotations
import math
from pathlib import Path
import cv2
import numpy as np


def generate_scene_image(
    scene_id: str,
    gap_px: int,
    object_width_px: int = 60,
    condition: str = "clean",
    width: int = 640,
    height: int = 480,
) -> np.ndarray:
    """Draw a single calibrated tabletop scene image."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 245  # light background

    # Subtle grid lines
    for x in range(0, width, 40):
        cv2.line(img, (x, 0), (x, height), (230, 220, 230), 1)
    for y in range(0, height, 40):
        cv2.line(img, (0, y), (width, y), (230, 220, 230), 1)

    # 1. ArUco Marker (50mm scale)
    if "marker_hidden" not in condition:
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker_size = 80  # 80 px = 50 mm -> 0.625 mm/px
        marker_img = cv2.aruco.generateImageMarker(aruco_dict, 0, marker_size)
        marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)
        
        # Position in top-right
        mx, my = width - 110, 30
        img[my:my+marker_size, mx:mx+marker_size] = marker_bgr

    # 2. Obstacles forming the gap
    obs_y1, obs_y2 = 120, 360
    obs1_x1, obs1_x2 = 60, 220
    obs2_x1 = obs1_x2 + gap_px
    obs2_x2 = min(width - 60, obs2_x1 + 160)

    # Left obstacle (Dark purple)
    cv2.rectangle(img, (obs1_x1, obs_y1), (obs1_x2, obs_y2), (80, 40, 90), -1)
    cv2.rectangle(img, (obs1_x1, obs_y1), (obs1_x2, obs_y2), (140, 80, 160), 2)

    # Right obstacle
    cv2.rectangle(img, (obs2_x1, obs_y1), (obs2_x2, obs_y2), (80, 40, 90), -1)
    cv2.rectangle(img, (obs2_x1, obs_y1), (obs2_x2, obs_y2), (140, 80, 160), 2)

    # 3. Moving Object (Yellow/gold block)
    obj_x = 120
    obj_y = 380
    cv2.rectangle(img, (obj_x, obj_y), (obj_x + object_width_px, obj_y + object_width_px), (40, 140, 220), -1)
    cv2.rectangle(img, (obj_x, obj_y), (obj_x + object_width_px, obj_y + object_width_px), (20, 100, 180), 2)

    # 4. Corruptions
    if "hand_occluded" in condition or "edge_occluded" in condition:
        # Draw flesh-toned occluding oval over right edge of left obstacle
        cv2.ellipse(img, (obs1_x2, 240), (35, 60), 20, 0, 360, (140, 160, 220), -1)
        cv2.ellipse(img, (obs1_x2, 240), (35, 60), 20, 0, 360, (100, 120, 180), 2)

    if "distractor" in condition:
        # Draw lookalike block nearby
        cv2.rectangle(img, (400, 380), (460, 440), (45, 135, 215), -1)

    if "motion_blur" in condition:
        img = cv2.GaussianBlur(img, (15, 15), 5)

    if "low_light" in condition:
        img = (img * 0.35).astype(np.uint8)

    return img


def build_all_scenes(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 40 scenes
    configs = [
        # Clear Pass (gap = 120px vs object 60px -> +60px clearance)
        ("s{:03d}", 120, "clean"),
        ("s{:03d}", 120, "motion_blur"),
        ("s{:03d}", 120, "low_light"),
        ("s{:03d}", 120, "distractor"),
        # Marginal (gap = 70px vs object 60px -> +10px clearance)
        ("s{:03d}", 70, "clean"),
        ("s{:03d}", 70, "hand_occluded"),
        ("s{:03d}", 70, "motion_blur"),
        ("s{:03d}", 70, "low_light"),
        # Clear Fail (gap = 40px vs object 60px -> -20px collision)
        ("s{:03d}", 40, "clean"),
        ("s{:03d}", 40, "hand_occluded"),
        ("s{:03d}", 40, "low_light"),
        # Unanswerable cases (deciding edge hidden or marker missing)
        ("s{:03d}", 70, "marker_hidden"),
        ("s{:03d}", 70, "edge_occluded"),
    ]

    count = 1
    for fmt, gap, cond in configs * 4:  # Repeat to generate 40 scenes
        if count > 40:
            break
        s_id = fmt.format(count)
        img = generate_scene_image(s_id, gap_px=gap, condition=cond)
        out_path = output_dir / f"{s_id}_{cond}.png"
        cv2.imwrite(str(out_path), img)
        count += 1

    print(f"Generated {count - 1} synthetic scene images in {output_dir}")


if __name__ == "__main__":
    scenes_dir = Path(__file__).resolve().parent / "scenes"
    build_all_scenes(scenes_dir)
