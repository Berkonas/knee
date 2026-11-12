"""Segment inertial parameters (Winter, 2009, Table 4.1; derived from Dempster, 1955).

mass_frac   : segment mass / body mass
com_frac    : COM distance from the proximal end / segment length
rgyr_frac   : radius of gyration about the COM / segment length
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentParams:
    mass_frac: float
    com_frac: float
    rgyr_frac: float


WINTER = {
    "foot": SegmentParams(0.0145, 0.50, 0.475),       # Winter: lateral malleolus -> MT2 head
    # COM location and radius of gyration from de Leva (1996, male) for heel -> toe tip, which
    # matches MediaPipe's heel/foot_index landmarks; mass fraction kept at Winter's 0.0145 so the
    # whole-body mass fractions still sum to 1.
    "foot_heel_toe": SegmentParams(0.0145, 0.4415, 0.257),
    "shank": SegmentParams(0.0465, 0.433, 0.302),
    "thigh": SegmentParams(0.100, 0.433, 0.323),
    "upper_arm": SegmentParams(0.028, 0.436, 0.322),
    "forearm": SegmentParams(0.016, 0.430, 0.303),
    "hand": SegmentParams(0.006, 0.506, 0.297),
    "forearm_hand": SegmentParams(0.022, 0.682, 0.468),
    "trunk": SegmentParams(0.497, 0.50, 0.0),       # greater trochanter -> glenohumeral joint
    "head_neck": SegmentParams(0.081, 1.0, 0.0),    # lumped at the head landmark
}

G = 9.81  # m/s^2


def segment_mass(name: str, body_mass: float) -> float:
    return WINTER[name].mass_frac * body_mass


def segment_moi(name: str, body_mass: float, length: float) -> float:
    p = WINTER[name]
    return p.mass_frac * body_mass * (p.rgyr_frac * length) ** 2
