from __future__ import annotations

import numpy as np


def rotation_matrix(q) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    if q.shape != (4,) or not np.isfinite(q).all() or np.linalg.norm(q) < 1e-9:
        raise ValueError("invalid wxyz quaternion")
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ])


def quat_multiply(a, b) -> np.ndarray:
    w, x, y, z = a
    v, i, j, k = b
    return np.array([w*v-x*i-y*j-z*k, w*i+x*v+y*k-z*j,
                     w*j-x*k+y*v+z*i, w*k+x*j-y*i+z*v])


def in_base(position_w, quat_w, base_position_w, base_quat_w):
    r = rotation_matrix(base_quat_w)
    q = np.array(base_quat_w, dtype=float)
    q /= np.linalg.norm(q)
    conjugate = q * [1, -1, -1, -1]
    return r.T @ (np.asarray(position_w) - base_position_w), quat_multiply(conjugate, quat_w)


def tcp_from_hand(position, quat, offset):
    return np.asarray(position) + rotation_matrix(quat) @ np.asarray(offset)


def angular_error(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(2 * np.arccos(np.clip(abs(np.dot(a, b)) / (np.linalg.norm(a)*np.linalg.norm(b)), 0, 1)))


def half_extents(quat, size: float) -> np.ndarray:
    return abs(rotation_matrix(quat)) @ np.full(3, size / 2)


def direction(value: float, tolerance: float = 0.006) -> str:
    return "positive" if value > tolerance else "negative" if value < -tolerance else "zero"


def relation(delta) -> dict:
    delta = np.asarray(delta, dtype=float)
    return {
        "delta_m": delta.tolist(),
        "directions": dict(zip(("x", "y", "z"), map(direction, delta))),
        "xy_aligned": bool(np.max(abs(delta[:2])) <= 0.006),
    }
