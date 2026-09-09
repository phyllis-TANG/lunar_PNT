import math, unittest
import numpy as np
from tools.unreal_coordinates import (C_OC_FRU, Transform, antenna_position, actor_fru_to_body_flu,
    matrix_to_quaternion_wxyz, quaternion_wxyz_to_matrix, unreal_actor_rotation_to_enu_body,
    unreal_position_cm_to_enu_m, sensor_pose)

class CoordinateTest(unittest.TestCase):
    def test_units_axes_and_identity_actor_direction(self):
        np.testing.assert_allclose(unreal_position_cm_to_enu_m([100,200,300]),[2,1,3])
        np.testing.assert_allclose(actor_fru_to_body_flu([1,2,3]),[1,-2,3])
        expected=np.array([[0,-1,0],[1,0,0],[0,0,1]],float)
        np.testing.assert_allclose(unreal_actor_rotation_to_enu_body(np.eye(3)),expected)
        np.testing.assert_allclose(expected[:,0],[0,1,0])  # vehicle forward is North, not ENU identity

    def test_matrix_inputs_for_signed_quarter_turns_and_combined_pose(self):
        cases=[
          (np.array([[0,-1,0],[1,0,0],[0,0,1.]]), np.eye(3)),
          (np.array([[0,1,0],[-1,0,0],[0,0,1.]]), np.array([[-1,0,0],[0,-1,0],[0,0,1.]])),
          (np.array([[1,0,0],[0,0,-1],[0,1,0.]]), np.array([[0,0,-1],[1,0,0],[0,-1,0.]])),
          (np.array([[1,0,0],[0,0,1],[0,-1,0.]]), np.array([[0,0,1],[1,0,0],[0,1,0.]])),
          (np.array([[0,0,1],[0,1,0],[-1,0,0.]]), np.array([[0,-1,0],[0,0,1],[-1,0,0.]])),
          (np.array([[0,0,-1],[0,1,0],[1,0,0.]]), np.array([[0,-1,0],[0,0,-1],[1,0,0.]])),
          (np.array([[0,0,1],[1,0,0],[0,1,0.]]), np.array([[1,0,0],[0,0,1],[0,-1,0.]])),
        ]
        for source,expected in cases: np.testing.assert_allclose(unreal_actor_rotation_to_enu_body(source),expected,atol=1e-12)

    def test_quaternion_transform_inverse_sensor_and_lever_arm(self):
        r=np.array([[0,-1,0],[1,0,0],[0,0,1.]],float)
        np.testing.assert_allclose(quaternion_wxyz_to_matrix(matrix_to_quaternion_wxyz(r)),r,atol=1e-12)
        t=Transform(r,[2,3,4]); p=np.array([1,2,3.]); np.testing.assert_allclose(t.inverse().apply(t.apply(p)),p)
        np.testing.assert_allclose(antenna_position([2,3,4],r,[1,0,2]),[2,4,6])
        camera=sensor_pose(t,Transform(np.eye(3),[.8,.155,.7])); np.testing.assert_allclose(camera.translation,[1.845,3.8,4.7])
        left=np.array([.8,.155,.7]); right=np.array([.8,-.155,.7]); self.assertAlmostEqual(np.linalg.norm(left-right),.310)
        np.testing.assert_allclose(C_OC_FRU @ np.array([1.,0.,0.]),[0,0,1])  # camera forward is optical +z

    def test_improper_matrix_cannot_be_quaternion(self):
        with self.assertRaises(ValueError): matrix_to_quaternion_wxyz(np.diag([1,1,-1]))

    def test_half_turn_mixed_axis_preserves_relative_signs(self):
        rotation=np.array([[0.,-1.,0.],[-1.,0.,0.],[0.,0.,-1.]])
        quaternion=matrix_to_quaternion_wxyz(rotation)
        np.testing.assert_allclose(
            quaternion_wxyz_to_matrix(quaternion),rotation,atol=1e-12
        )
        self.assertAlmostEqual(quaternion[0],0.)
        self.assertLess(quaternion[1]*quaternion[2],0.)
