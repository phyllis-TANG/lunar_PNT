"""Coordinate and rigid-transform helpers for unreal-mvp-interface-v1.

The Unreal adapter must provide an actor rotation matrix.  This module deliberately
does not interpret Unreal Euler angles because their engine/plugin convention still
requires an in-engine test.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

C_NU = np.array([[0., 1., 0.], [1., 0., 0.], [0., 0., 1.]])
C_BF = np.diag([1., -1., 1.])
C_OC_FRU = np.array([[0., 1., 0.], [0., 0., -1.], [1., 0., 0.]])


def _v3(value) -> np.ndarray:
    a = np.asarray(value, dtype=float)
    if a.shape != (3,) or not np.all(np.isfinite(a)):
        raise ValueError("expected a finite 3-vector")
    return a


def validate_rotation(rotation, atol: float = 1e-9) -> np.ndarray:
    r = np.asarray(rotation, dtype=float)
    if r.shape != (3, 3) or not np.all(np.isfinite(r)):
        raise ValueError("rotation must be a finite 3x3 matrix")
    if not np.allclose(r.T @ r, np.eye(3), atol=atol) or not np.isclose(np.linalg.det(r), 1., atol=atol):
        raise ValueError("rotation must be orthogonal with determinant +1")
    return r


def unreal_position_cm_to_enu_m(position_u_cm) -> np.ndarray:
    return C_NU @ _v3(position_u_cm) / 100.


def enu_position_m_to_unreal_cm(position_n_m) -> np.ndarray:
    return C_NU @ _v3(position_n_m) * 100.


def actor_fru_to_body_flu(vector_fru) -> np.ndarray:
    return C_BF @ _v3(vector_fru)


def unreal_actor_rotation_to_enu_body(rotation_u_fru) -> np.ndarray:
    r_uf = validate_rotation(rotation_u_fru)
    return validate_rotation(C_NU @ r_uf @ C_BF)


def matrix_to_quaternion_wxyz(rotation) -> np.ndarray:
    r = validate_rotation(rotation)
    w = np.sqrt(max(0., 1. + np.trace(r))) / 2.
    x = np.copysign(np.sqrt(max(0., 1. + r[0, 0] - r[1, 1] - r[2, 2])) / 2., r[2, 1] - r[1, 2])
    y = np.copysign(np.sqrt(max(0., 1. - r[0, 0] + r[1, 1] - r[2, 2])) / 2., r[0, 2] - r[2, 0])
    z = np.copysign(np.sqrt(max(0., 1. - r[0, 0] - r[1, 1] + r[2, 2])) / 2., r[1, 0] - r[0, 1])
    q = np.array([w, x, y, z]); q /= np.linalg.norm(q)
    return q if q[0] >= 0 else -q


def quaternion_wxyz_to_matrix(quaternion) -> np.ndarray:
    q = np.asarray(quaternion, dtype=float)
    if q.shape != (4,) or not np.all(np.isfinite(q)) or np.linalg.norm(q) < 1e-12:
        raise ValueError("quaternion must be finite and nonzero")
    w, x, y, z = q / np.linalg.norm(q)
    return validate_rotation(np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
    ]))


@dataclass(frozen=True)
class Transform:
    rotation: np.ndarray
    translation: np.ndarray

    def __post_init__(self):
        object.__setattr__(self, "rotation", validate_rotation(self.rotation).copy())
        object.__setattr__(self, "translation", _v3(self.translation).copy())

    def apply(self, point): return self.rotation @ _v3(point) + self.translation
    def inverse(self):
        r = self.rotation.T
        return Transform(r, -r @ self.translation)
    def compose(self, child: "Transform"):
        return Transform(self.rotation @ child.rotation, self.apply(child.translation))


def antenna_position(position_n_b, rotation_n_b, lever_arm_b_a) -> np.ndarray:
    return Transform(rotation_n_b, position_n_b).apply(lever_arm_b_a)


def sensor_pose(body_pose: Transform, body_to_sensor: Transform) -> Transform:
    return body_pose.compose(body_to_sensor)

