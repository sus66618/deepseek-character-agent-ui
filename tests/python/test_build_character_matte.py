from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_character_matte.py"
SPEC = importlib.util.spec_from_file_location("build_character_matte", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"无法加载脚本: {SCRIPT_PATH}")
MATTE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MATTE
SPEC.loader.exec_module(MATTE)


class CharacterMatteTest(unittest.TestCase):
    def test_compose_rgba_preserves_every_source_rgb_value(self) -> None:
        rgb = np.array(
            [
                [[1, 2, 3], [40, 50, 60]],
                [[70, 80, 90], [250, 251, 252]],
            ],
            dtype=np.uint8,
        )
        alpha = np.array([[0, 64], [128, 255]], dtype=np.uint8)

        result = np.asarray(MATTE.compose_rgba(rgb, alpha))

        np.testing.assert_array_equal(result[:, :, :3], rgb)
        np.testing.assert_array_equal(result[:, :, 3], alpha)

    def test_keep_primary_subject_removes_detached_background_components(self) -> None:
        alpha = np.zeros((10, 10), dtype=np.uint8)
        alpha[2:8, 2:8] = 255
        alpha[1, 3:7] = 80
        alpha[9, 9] = 220

        result = MATTE.keep_primary_subject(alpha, threshold=32)

        self.assertEqual(int(result[9, 9]), 0)
        self.assertEqual(int(result[4, 4]), 255)
        self.assertEqual(int(result[1, 4]), 80)

    def test_measure_alpha_reports_a_fully_enclosed_internal_hole(self) -> None:
        alpha = np.zeros((9, 9), dtype=np.uint8)
        alpha[1:8, 1:8] = 255
        alpha[4, 4] = 0

        result = MATTE.measure_alpha(alpha, foreground_threshold=128)

        self.assertEqual(result["internalHoleCount"], 1)
        self.assertEqual(result["internalHolePixels"], 1)

    def test_measure_edge_halo_counts_low_alpha_pale_pixels(self) -> None:
        rgb = np.zeros((5, 5, 3), dtype=np.uint8)
        alpha = np.zeros((5, 5), dtype=np.uint8)
        alpha[1:4, 1:4] = 16
        alpha[2, 2] = 255
        rgb[1:4, 1:4] = 240

        result = MATTE.measure_edge_halo(
            rgb,
            alpha,
            low_alpha_limit=32,
            pale_luma_minimum=210,
            pale_chroma_maximum=25,
        )

        self.assertEqual(result["lowAlphaPalePixelCount"], 8)
        self.assertAlmostEqual(
            result["lowAlphaPaleEquivalentOpaquePixels"],
            8 * 16 / 255,
        )

    def test_remove_ground_reflection_keeps_the_soft_sole_edge_only(self) -> None:
        alpha = np.zeros((10, 5), dtype=np.uint8)
        alpha[2:6, 2] = 255
        alpha[6:9, 2] = 255
        alpha[8, 4] = 100
        guide = alpha.copy()
        guide[6:9, 2] = 80

        result = MATTE.remove_ground_reflection(
            alpha,
            guide_alpha=guide,
            scan_start=2,
            apply_start=5,
            confidence_threshold=220,
            edge_margin=1,
        )

        self.assertEqual(int(result[5, 2]), 255)
        self.assertEqual(int(result[6, 2]), 255)
        self.assertEqual(int(result[7, 2]), 0)
        self.assertEqual(int(result[8, 4]), 0)

    def test_load_verified_source_rejects_a_wrong_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.png"
            Image.new("RGB", (4, 6), (10, 20, 30)).save(path)

            with self.assertRaisesRegex(ValueError, "SHA-256"):
                MATTE.load_verified_source(
                    path,
                    expected_sha256="0" * 64,
                    expected_size=(4, 6),
                )

    def test_load_verified_source_rejects_wrong_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.png"
            Image.new("RGB", (4, 6), (10, 20, 30)).save(path)
            digest = MATTE.sha256_file(path)

            with self.assertRaisesRegex(ValueError, "尺寸"):
                MATTE.load_verified_source(
                    path,
                    expected_sha256=digest,
                    expected_size=(6, 4),
                )


if __name__ == "__main__":
    unittest.main()
