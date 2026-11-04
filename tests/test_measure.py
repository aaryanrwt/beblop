"""Unit tests for BEBOP metric measurement and perspective tilt detection."""

import cv2
import numpy as np
import pytest
from bebop.measure import (
    detect_aruco_marker,
    mask_to_polygon,
    compute_gap_distance_px,
    compute_object_width_px,
    measure_scene,
)


def test_square_aruco_marker_detection():
    # Synthetic image with an ArUco marker drawn
    img = np.ones((300, 300, 3), dtype=np.uint8) * 255
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, 0, 100)
    img[50:150, 50:150] = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

    det = detect_aruco_marker(img, marker_size_mm=50.0)
    assert det.found is True
    assert det.scale_mm_per_px > 0
    assert "PERSPECTIVE_TILT_EXCEEDED" not in det.flags
    assert det.tilt_deg < 10.0


def test_measure_scene_clearance():
    # Create two obstacle masks with a known 80px gap
    obs1 = np.zeros((200, 300), dtype=np.uint8)
    obs1[50:150, 20:80] = 255  # ends at x=80

    obs2 = np.zeros((200, 300), dtype=np.uint8)
    obs2[50:150, 160:220] = 255  # starts at x=160 -> gap is 80 px

    # Object mask of width 50px
    obj = np.zeros((200, 300), dtype=np.uint8)
    obj[50:100, 50:100] = 255  # 50x50

    # Scale 0.5 mm/px -> gap = 40 mm (80px * 0.5), width = 25 mm (50px * 0.5)
    res = measure_scene([obs1, obs2], obj, scale_mm_per_px=0.5)
    assert abs(res.gap_mm - 40.0) < 1.0
    assert abs(res.object_width_mm - 25.0) < 2.0
    assert res.sigma_gap > 0
    assert res.sigma_width > 0
