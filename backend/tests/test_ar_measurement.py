import unittest

import numpy as np

from backend.services.ar_measurement import unproject_to_plane


class ARMeasurementGeometryTests(unittest.TestCase):
    def test_unproject_matches_arcore_camera_pose_convention(self):
        """Image +Y is down, but ARCore camera-pose +Y is up."""
        K = np.array(
            [
                [1000.0, 0.0, 320.0],
                [0.0, 1000.0, 240.0],
                [0.0, 0.0, 1.0],
            ]
        )
        K_inv = np.linalg.inv(K)

        ray_origin = np.array([0.0, 1.0, 0.0])
        # Local camera axes in world space:
        # +X -> world +X, +Y/up -> world +Z, -Z/forward -> world -Y.
        R = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, 1.0, 0.0],
            ]
        )
        n = np.array([0.0, 1.0, 0.0])
        p0 = np.array([0.0, 0.0, 0.0])

        expected_world = np.array([0.10, 0.0, 0.20])
        local = R.T @ (expected_world - ray_origin)
        depth = -local[2]
        pixel_x = 320.0 + 1000.0 * (local[0] / depth)
        pixel_y = 240.0 - 1000.0 * (local[1] / depth)

        actual = unproject_to_plane(pixel_x, pixel_y, K_inv, ray_origin, R, n, p0)

        np.testing.assert_allclose(actual, expected_world, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
