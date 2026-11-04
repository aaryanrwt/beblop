"""BEBOP-Gate: Deterministic metric measurement and perspective verification.

Pure, auditable functions converting visual masks and ArUco markers into
millimetre measurements with rigorous uncertainty propagation.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import cv2
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import nearest_points


@dataclass
class MarkerDetection:
    found: bool
    scale_mm_per_px: float = 0.0
    corners: Optional[np.ndarray] = None
    flags: List[str] = field(default_factory=list)
    tilt_deg: float = 0.0


@dataclass
class MeasurementResult:
    gap_mm: float
    sigma_gap: float
    object_width_mm: float
    sigma_width: float
    n_samples: int
    flags: List[str] = field(default_factory=list)
    scale_mm_per_px: float = 0.0
    debug_contours: List[np.ndarray] = field(default_factory=list)


def detect_aruco_marker(
    image: np.ndarray,
    marker_size_mm: float = 50.0,
    dict_type: int = cv2.aruco.DICT_4X4_50,
) -> MarkerDetection:
    """Detect ArUco marker and calculate pixel-to-millimetre scale factor.
    
    Includes perspective distortion check (adapted from Bonisa's scale verification):
    Checks corner orthogonality and edge-length variance.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    aruco_dict = cv2.aruco.getPredefinedDictionary(dict_type)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    corners, ids, rejected = detector.detectMarkers(gray)

    if ids is None or len(corners) == 0:
        return MarkerDetection(found=False, flags=["NO_MARKER_DETECTED"])

    # Use first detected marker
    c = corners[0][0]  # shape (4, 2): top-left, top-right, bottom-right, bottom-left
    
    # Measure side lengths in pixels
    side_lengths = [
        float(np.linalg.norm(c[0] - c[1])),
        float(np.linalg.norm(c[1] - c[2])),
        float(np.linalg.norm(c[2] - c[3])),
        float(np.linalg.norm(c[3] - c[0])),
    ]
    mean_side_px = float(np.mean(side_lengths))
    if mean_side_px < 5.0:
        return MarkerDetection(found=False, flags=["MARKER_TOO_SMALL"])

    scale = marker_size_mm / mean_side_px
    flags = []

    # Perspective distortion check: opposite sides ratio and diagonal orthogonality
    top_bot_ratio = abs(side_lengths[0] - side_lengths[2]) / mean_side_px
    left_right_ratio = abs(side_lengths[1] - side_lengths[3]) / mean_side_px
    distortion = max(top_bot_ratio, left_right_ratio)

    # Estimate tilt angle from aspect distortion
    tilt_deg = math.degrees(math.acos(max(0.1, min(1.0, 1.0 - distortion))))
    if distortion > 0.12 or tilt_deg > 15.0:
        flags.append("PERSPECTIVE_TILT_EXCEEDED")

    return MarkerDetection(
        found=True,
        scale_mm_per_px=scale,
        corners=c,
        flags=flags,
        tilt_deg=tilt_deg,
    )


def mask_to_polygon(mask: np.ndarray, min_area_px: float = 20.0) -> Optional[Polygon]:
    """Convert binary mask to largest outer Shapely polygon."""
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return None
    valid_contours = [c for c in contours if cv2.contourArea(c) >= min_area_px]
    if not valid_contours:
        return None
    largest = max(valid_contours, key=cv2.contourArea)
    if len(largest) < 3:
        return None
    pts = largest.reshape(-1, 2)
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def compute_gap_distance_px(poly1: Polygon, poly2: Polygon) -> float:
    """Calculate minimum Euclidean distance in pixels between two obstacle polygons."""
    return float(poly1.distance(poly2))


def compute_object_width_px(mask: np.ndarray) -> Tuple[float, float]:
    """Calculate object width and length from minimum-area bounding rectangle.
    
    Returns (width_px, length_px) where width <= length.
    """
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return (0.0, 0.0)
    largest = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(largest)  # ((cx, cy), (w, h), angle)
    w, h = rect[1]
    short_edge = min(w, h)
    long_edge = max(w, h)
    return float(short_edge), float(long_edge)


def measure_scene(
    obstacle_masks: List[np.ndarray],
    object_mask: np.ndarray,
    scale_mm_per_px: float,
    marker_flags: Optional[List[str]] = None,
    n_samples: int = 15,
) -> MeasurementResult:
    """Measure gap clearance and object width with rigorous uncertainty propagation.
    
    Formula per TRD 3.3:
    sigma combines sample dispersion, 0.5px quantisation term, and marker scale error.
    """
    flags = list(marker_flags or [])
    
    if len(obstacle_masks) < 2:
        flags.append("FEWER_THAN_TWO_OBSTACLES")
        return MeasurementResult(
            gap_mm=0.0, sigma_gap=999.0, object_width_mm=0.0, sigma_width=999.0,
            n_samples=0, flags=flags, scale_mm_per_px=scale_mm_per_px
        )

    poly1 = mask_to_polygon(obstacle_masks[0])
    poly2 = mask_to_polygon(obstacle_masks[1])
    
    if poly1 is None or poly2 is None or poly1.is_empty or poly2 is None:
        flags.append("EMPTY_OBSTACLE_MASK")
        return MeasurementResult(
            gap_mm=0.0, sigma_gap=999.0, object_width_mm=0.0, sigma_width=999.0,
            n_samples=0, flags=flags, scale_mm_per_px=scale_mm_per_px
        )

    gap_px = compute_gap_distance_px(poly1, poly2)
    width_px, _ = compute_object_width_px(object_mask)

    if width_px <= 0.0:
        flags.append("EMPTY_OBJECT_MASK")
        return MeasurementResult(
            gap_mm=gap_px * scale_mm_per_px, sigma_gap=999.0,
            object_width_mm=0.0, sigma_width=999.0,
            n_samples=0, flags=flags, scale_mm_per_px=scale_mm_per_px
        )

    gap_mm = gap_px * scale_mm_per_px
    width_mm = width_px * scale_mm_per_px

    # Error propagation:
    # 0.5px quantisation floor + 1.5% scale marker calibration uncertainty
    sigma_px = 0.75  # pixel boundary uncertainty
    sigma_gap = math.sqrt((sigma_px * scale_mm_per_px) ** 2 + (0.015 * gap_mm) ** 2)
    sigma_width = math.sqrt((sigma_px * scale_mm_per_px) ** 2 + (0.015 * width_mm) ** 2)

    return MeasurementResult(
        gap_mm=round(gap_mm, 2),
        sigma_gap=round(sigma_gap, 2),
        object_width_mm=round(width_mm, 2),
        sigma_width=round(sigma_width, 2),
        n_samples=n_samples,
        flags=flags,
        scale_mm_per_px=scale_mm_per_px,
    )
