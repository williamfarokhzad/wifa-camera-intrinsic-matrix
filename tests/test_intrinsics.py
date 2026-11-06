import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from intrinsics import Camera, CropResize, evaluate

ROOT = Path(__file__).resolve().parents[1]


class IntrinsicsTests(unittest.TestCase):
    def setUp(self):
        self.camera = Camera(640, 480, 800, 820, 315, 238)

    def test_pinhole_principal_point_and_ray_scale(self):
        self.assertEqual(self.camera.project(0, 0, 1), (315, 238))
        self.assertEqual(self.camera.project(0.2, -0.1, 2), (395, 197))
        self.assertEqual(self.camera.project(0.1, -0.05, 1), (395, 197))

    def test_fixed_half_pixel_case(self):
        resized = CropResize(100, 60, 400, 320, 200, 160, "half_pixel").update(self.camera)
        self.assertEqual(resized, Camera(200, 160, 400, 410, 107.25, 88.75))
        self.assertEqual(resized.project(0.1, -0.05, 1), (147.25, 68.25))

    def test_matches_independent_inverse_sampler(self):
        # Start at output pixel centers and map backward per sampler convention.
        # Then recover a 3D ray using the original calibration, without map_pixel().
        for mode, out_w, out_h in itertools.product(
            ("half_pixel", "asymmetric"), (1, 217, 799), (1, 91, 341)
        ):
            with self.subTest(mode=mode, out_w=out_w, out_h=out_h):
                updated = CropResize(41, 39, 511, 315, out_w, out_h, mode).update(self.camera)
                for u, v in ((0, 0), (out_w - 1, out_h - 1), (out_w / 3, out_h / 4)):
                    sx_back, sy_back = 511 / out_w, 315 / out_h
                    shift = 0.5 if mode == "half_pixel" else 0
                    source_u = 41 + (u + shift) * sx_back - shift
                    source_v = 39 + (v + shift) * sy_back - shift
                    z = 2.25
                    x = (source_u - 315) * z / 800
                    y = (source_v - 238) * z / 820
                    got_u, got_v = updated.project(x, y, z)
                    self.assertAlmostEqual(got_u, u, places=10)
                    self.assertAlmostEqual(got_v, v, places=10)

    def test_half_pixel_offset_is_constant(self):
        params = (200, 120, 320, 240, 480, 120)
        a = CropResize(*params, "asymmetric").update(self.camera)
        b = CropResize(*params, "half_pixel").update(self.camera)
        self.assertEqual((a.fx, a.fy), (b.fx, b.fy))
        self.assertEqual((b.cx - a.cx, b.cy - a.cy), (0.25, -0.25))

    def test_crop_only_can_move_principal_point_outside(self):
        c = CropResize(400, 100, 100, 200, 100, 200, "half_pixel").update(self.camera)
        self.assertEqual((c.cx, c.cy), (-85, 138))
        self.assertFalse(c.contains(*c.project(0, 0, 1)))

    def test_pixel_edges_and_offscreen(self):
        self.assertTrue(self.camera.contains(-0.5, 0))
        self.assertFalse(self.camera.contains(639.5, 0))
        self.assertFalse(self.camera.contains(0, 479.5))
        data = json.loads((ROOT / "examples/offscreen.json").read_text())
        result = evaluate(data)
        self.assertEqual(result["after"], (-12.75, 191.25))
        self.assertFalse(result["inside"])
        self.assertAlmostEqual(result["stale_error_px"], math.hypot(87.75, 251.75))

    def test_rejects_invalid_geometry(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            Camera(640, 480, 0, 820, 315, 238)
        with self.assertRaisesRegex(ValueError, "finite"):
            self.camera.project(float("inf"), 0, 1)
        for z in (0, -1):
            with self.assertRaisesRegex(ValueError, "Z must be positive"):
                self.camera.project(0, 0, z)
        with self.assertRaisesRegex(ValueError, "extends past"):
            CropResize(300, 60, 400, 320, 200, 160, "half_pixel").update(self.camera)
        with self.assertRaisesRegex(ValueError, "integer"):
            CropResize(True, 60, 400, 320, 200, 160, "half_pixel")
        with self.assertRaisesRegex(ValueError, "mode"):
            CropResize(0, 0, 640, 480, 640, 480, "align_corners")

    def test_cli_goldens(self):
        cases = {
            "identity": ("output=(395.000, 197.000)", "inside_output=true stale_K_error_px=0.000"),
            "crop-half": ("output=(147.250, 68.250)", "inside_output=true"),
            "anisotropic": ("output=(292.500, 38.500)", "inside_output=true"),
            "offscreen": ("output=(-12.750, 191.250)", "inside_output=false"),
        }
        for name, fragments in cases.items():
            with self.subTest(name=name):
                r = subprocess.run([sys.executable, "intrinsics.py", f"examples/{name}.json"],
                                   cwd=ROOT, check=True, text=True, capture_output=True)
                for fragment in fragments:
                    self.assertIn(fragment, r.stdout)

    def test_cli_invalid_input_has_actionable_message(self):
        case = json.loads((ROOT / "examples/identity.json").read_text())
        case["point_xyz"][2] = -0.1
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "behind.json"
            path.write_text(json.dumps(case), encoding="utf-8")
            r = subprocess.run([sys.executable, "intrinsics.py", str(path)], cwd=ROOT,
                               text=True, capture_output=True, check=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn("Z must be positive in the camera frame", r.stderr)


if __name__ == "__main__":
    unittest.main()
