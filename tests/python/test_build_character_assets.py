from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = PROJECT_ROOT / "assets" / "character" / "deepseek-v2"
LAYER_DIR = ASSET_ROOT / "layers"
PSD_PATH = ASSET_ROOT / "source" / "deepseek-v2-layered.psd"
EVIDENCE_DIR = PROJECT_ROOT / "evidence" / "assets"

REQUIRED_LAYERS = (
    "back-hair",
    "tail",
    "torso",
    "head-base",
    "eye-left-white",
    "eye-left-iris",
    "eye-left-upper-lid",
    "eye-right-white",
    "eye-right-iris",
    "eye-right-upper-lid",
    "brow-left",
    "brow-right",
    "mouth-neutral",
    "mouth-smile",
    "mouth-talk",
    "mouth-worried",
    "front-hair",
    "side-hair-left",
    "side-hair-right",
    "hand-front",
    "core",
    "bubbles",
    "sonar",
)

EXPECTED_GROUPS = {
    "back": {"back-hair", "tail"},
    "body": {"torso"},
    "head": {"head-base"},
    "face": {
        "eye-left-white",
        "eye-left-iris",
        "eye-left-upper-lid",
        "eye-right-white",
        "eye-right-iris",
        "eye-right-upper-lid",
        "brow-left",
        "brow-right",
        "mouth-neutral",
        "mouth-smile",
        "mouth-talk",
        "mouth-worried",
    },
    "front": {
        "front-hair",
        "side-hair-left",
        "side-hair-right",
        "hand-front",
    },
    "props": {"core"},
    "effects": {"bubbles", "sonar"},
}

MINIMUM_VISIBLE_PIXELS = {
    "back-hair": 40_000,
    "tail": 60_000,
    "torso": 180_000,
    "head-base": 20_000,
    "eye-left-white": 500,
    "eye-left-iris": 250,
    "eye-left-upper-lid": 80,
    "eye-right-white": 500,
    "eye-right-iris": 250,
    "eye-right-upper-lid": 80,
    "brow-left": 25,
    "brow-right": 25,
    "mouth-neutral": 180,
    "mouth-smile": 80,
    "mouth-talk": 250,
    "mouth-worried": 60,
    "front-hair": 14_000,
    "side-hair-left": 8_000,
    "side-hair-right": 8_000,
    "hand-front": 10_000,
    "core": 6_000,
    "bubbles": 1_000,
    "sonar": 3_000,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


class CharacterAssetBuildTest(unittest.TestCase):
    def test_exports_exact_inventory_as_real_rgba_canvases(self) -> None:
        actual = sorted(path.stem for path in LAYER_DIR.glob("*.png"))
        self.assertEqual(actual, sorted(REQUIRED_LAYERS))

        hashes: set[str] = set()
        for name in REQUIRED_LAYERS:
            path = LAYER_DIR / f"{name}.png"
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA", name)
                self.assertEqual(image.size, (1024, 1536), name)
                pixels = np.asarray(image)
                alpha = pixels[:, :, 3]
                visible = int(np.count_nonzero(alpha))
                self.assertGreaterEqual(
                    visible,
                    MINIMUM_VISIBLE_PIXELS[name],
                    f"{name} 缺少足够的语义像素",
                )
                self.assertLess(visible, 1024 * 1536, name)
                self.assertIsNotNone(image.getchannel("A").getbbox(), name)
                self.assertTrue(
                    np.all(pixels[:, :, :3][alpha == 0] == 0),
                    f"{name} 在全透明区藏有源图 RGB",
                )
            hashes.add(sha256(path))

        self.assertEqual(len(hashes), len(REQUIRED_LAYERS))

    def test_places_key_layers_in_their_semantic_regions(self) -> None:
        expected_bounds = {
            "tail": (500, 540, 920, 1385),
            "head-base": (365, 175, 625, 425),
            "eye-left-white": (410, 250, 500, 345),
            "eye-right-white": (495, 250, 580, 345),
            "mouth-neutral": (455, 325, 540, 395),
            "hand-front": (235, 385, 575, 690),
            "core": (265, 360, 400, 505),
        }
        for name, allowed in expected_bounds.items():
            with Image.open(LAYER_DIR / f"{name}.png") as image:
                box = image.getchannel("A").getbbox()
            self.assertIsNotNone(box, name)
            assert box is not None
            self.assertGreaterEqual(box[0], allowed[0], name)
            self.assertGreaterEqual(box[1], allowed[1], name)
            self.assertLessEqual(box[2], allowed[2], name)
            self.assertLessEqual(box[3], allowed[3], name)

    def test_psd_contains_seven_named_groups_and_every_layer(self) -> None:
        from psd_tools import PSDImage

        psd = PSDImage.open(PSD_PATH)
        self.assertEqual(psd.size, (1024, 1536))
        groups = {group.name: {layer.name for layer in group} for group in psd}
        self.assertEqual(groups, EXPECTED_GROUPS)

    def test_records_machine_readable_partition_and_seam_metrics(self) -> None:
        evidence = json.loads(
            (EVIDENCE_DIR / "layer-stats.json").read_text(encoding="utf-8")
        )
        self.assertEqual(evidence["canvas"], {"width": 1024, "height": 1536})
        self.assertEqual(
            evidence["subjectSha256"],
            "01519D11A7CC15BB23A2EF324CE27B8EDCC01C7DCB9F4BA62855E72E7D385A82",
        )
        self.assertEqual(
            [layer["name"] for layer in evidence["layers"]],
            list(REQUIRED_LAYERS),
        )
        self.assertLessEqual(evidence["neutralComparison"]["meanAbsoluteError"], 1.5)
        self.assertLessEqual(evidence["neutralComparison"]["p95AbsoluteError"], 3)
        self.assertGreaterEqual(
            evidence["neutralComparison"]["subjectCoverageRatio"], 0.999
        )
        for scenario in ("blink", "gaze", "hair", "hand", "tail"):
            metrics = evidence["seamScenarios"][scenario]
            self.assertEqual(metrics["transparentHolePixels"], 0, scenario)
            self.assertEqual(metrics["disconnectedRequiredParts"], 0, scenario)
        for scenario in ("hair", "hand", "tail"):
            metrics = evidence["seamScenarios"][scenario]
            self.assertEqual(metrics["originalPositionGhostPixels"], 0, scenario)

    def test_exports_all_six_full_size_visual_qa_scenarios(self) -> None:
        expected = {
            "neutral.png": (1024, 1536),
            "blink.png": (1024, 1536),
            "gaze-extremes.png": (2048, 1536),
            "hair-offset.png": (1024, 1536),
            "hand-offset.png": (1024, 1536),
            "tail-offset.png": (1024, 1536),
        }
        for name, size in expected.items():
            with Image.open(EVIDENCE_DIR / name) as image:
                self.assertEqual(image.size, size, name)
                self.assertIn(image.mode, ("RGB", "RGBA"), name)

    def test_exports_user_friendly_movable_preview(self) -> None:
        with Image.open(EVIDENCE_DIR / "movable-layer-preview.png") as image:
            self.assertEqual(image.size, (1920, 1080))
            self.assertIn(image.mode, ("RGB", "RGBA"))


if __name__ == "__main__":
    unittest.main()
