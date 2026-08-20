#!/usr/bin/env python3
"""确定性构建 DeepSeek v2 角色分层、补底、PSD 与视觉验收图。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "assets" / "character" / "deepseek-v2"
ORIGINAL_PATH = ASSET_ROOT / "source" / "original.png"
SUBJECT_PATH = ASSET_ROOT / "source" / "subject-rgba.png"
BLINK_REFERENCE_PATH = ASSET_ROOT / "source" / "face-blink-reference.png"
LAYER_DIR = ASSET_ROOT / "layers"
PSD_PATH = ASSET_ROOT / "source" / "deepseek-v2-layered.psd"
EVIDENCE_DIR = ROOT / "evidence" / "assets"
WIDTH = 1024
HEIGHT = 1536
EXPECTED_ORIGINAL_SHA256 = (
    "24DF7985AE880E21CB5EB7FF6C811631C00CEFC82F9BE4C91D580350C61A79D5"
)
EXPECTED_SUBJECT_SHA256 = (
    "01519D11A7CC15BB23A2EF324CE27B8EDCC01C7DCB9F4BA62855E72E7D385A82"
)
EXPECTED_BLINK_REFERENCE_SHA256 = (
    "C39229B9119E102838354FE7A055CE11B0293C353DF01E5A7E42A7073DC1AC8C"
)

LAYER_NAMES = (
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

GROUPS = {
    "back": ("back-hair", "tail"),
    "body": ("torso",),
    "head": ("head-base",),
    "face": (
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
    ),
    "front": (
        "front-hair",
        "side-hair-left",
        "side-hair-right",
        "hand-front",
    ),
    "props": ("core",),
    "effects": ("bubbles", "sonar"),
}

Z_INDEX = {
    "sonar": 0,
    "back-hair": 10,
    "tail": 20,
    "torso": 30,
    "head-base": 40,
    "eye-left-white": 50,
    "eye-left-iris": 51,
    "eye-left-upper-lid": 52,
    "eye-right-white": 53,
    "eye-right-iris": 54,
    "eye-right-upper-lid": 55,
    "brow-left": 56,
    "brow-right": 57,
    "mouth-neutral": 58,
    "mouth-smile": 59,
    "mouth-talk": 60,
    "mouth-worried": 61,
    "side-hair-left": 70,
    "side-hair-right": 71,
    "front-hair": 72,
    "core": 80,
    "hand-front": 90,
    "bubbles": 100,
}

NEUTRAL_VISIBLE = {
    "sonar",
    "back-hair",
    "tail",
    "torso",
    "head-base",
    "eye-left-white",
    "eye-left-iris",
    "eye-right-white",
    "eye-right-iris",
    "brow-left",
    "brow-right",
    "mouth-neutral",
    "front-hair",
    "side-hair-left",
    "side-hair-right",
    "core",
    "hand-front",
    "bubbles",
}

BLINK_VISIBLE = (
    NEUTRAL_VISIBLE
    - {
        "eye-left-white",
        "eye-left-iris",
        "eye-right-white",
        "eye-right-iris",
    }
    | {"eye-left-upper-lid", "eye-right-upper-lid"}
)

MOUTH_LAYERS = {
    "mouth-neutral",
    "mouth-smile",
    "mouth-talk",
    "mouth-worried",
}

CHARACTER_VISIBLE = NEUTRAL_VISIBLE - {"sonar", "bubbles"}

BUBBLE_ELLIPSES = (
    (839, 107, 858, 127),
    (326, 210, 348, 232),
    (258, 247, 294, 285),
    (98, 347, 136, 387),
    (866, 257, 884, 277),
    (874, 369, 920, 415),
    (169, 411, 190, 433),
    (67, 498, 88, 520),
    (834, 766, 867, 799),
    (571, 1022, 592, 1044),
    (312, 1120, 348, 1157),
)

HAIR_QA_OFFSETS = {
    "back-hair": (4, -2),
    "front-hair": (2, -1),
    "side-hair-left": (6, -3),
    "side-hair-right": (6, -3),
}


def sha256(path: Path) -> str:
    """返回文件的大写 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def draw_mask(
    *,
    polygons: Iterable[Iterable[tuple[int, int]]] = (),
    ellipses: Iterable[tuple[int, int, int, int]] = (),
    rectangles: Iterable[tuple[int, int, int, int]] = (),
) -> np.ndarray:
    """把人工校准的几何区域渲染为布尔蒙版。"""
    canvas = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(canvas)
    for polygon in polygons:
        draw.polygon(tuple(polygon), fill=255)
    for ellipse in ellipses:
        draw.ellipse(ellipse, fill=255)
    for rectangle in rectangles:
        draw.rectangle(rectangle, fill=255)
    return np.asarray(canvas) > 0


def dilate(mask: np.ndarray, pixels: int) -> np.ndarray:
    """向外扩展蒙版，用于给移动层保留隐藏搭接。"""
    size = pixels * 2 + 1
    kernel = np.ones((size, size), dtype=np.uint8)
    return cv2.dilate(mask.astype(np.uint8), kernel, iterations=1).astype(bool)


def erode(mask: np.ndarray, pixels: int) -> np.ndarray:
    """向内收缩蒙版，用于忽略抗锯齿边缘。"""
    size = pixels * 2 + 1
    kernel = np.ones((size, size), dtype=np.uint8)
    return cv2.erode(mask.astype(np.uint8), kernel, iterations=1).astype(bool)


def clean_components(mask: np.ndarray, minimum_area: int = 8) -> np.ndarray:
    """移除不属于语义材料的微小噪点。"""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    cleaned = np.zeros_like(mask, dtype=bool)
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) >= minimum_area:
            cleaned[labels == label] = True
    return cleaned


def mask_alpha(
    mask: np.ndarray,
    source_alpha: np.ndarray | None = None,
    *,
    sigma: float = 0.0,
) -> np.ndarray:
    """把语义蒙版转换为保留源软边的 alpha。"""
    base = mask.astype(np.float32) * 255.0
    if sigma > 0:
        base = cv2.GaussianBlur(base, (0, 0), sigma)
    if source_alpha is not None:
        base = np.minimum(base, source_alpha.astype(np.float32))
    base[base < 1] = 0
    return np.rint(np.clip(base, 0, 255)).astype(np.uint8)


def rgba(rgb: np.ndarray, alpha: np.ndarray) -> Image.Image:
    """组合 RGB 与 alpha 为全画布 RGBA。"""
    clean_rgb = rgb.copy()
    clean_rgb[alpha == 0] = 0
    return Image.fromarray(
        np.dstack((clean_rgb, alpha)).astype(np.uint8),
        mode="RGBA",
    )


def inpaint(rgb: np.ndarray, removal: np.ndarray, radius: int = 7) -> np.ndarray:
    """只在显式遮挡区做局部 Telea 补底。"""
    if not np.any(removal):
        return rgb.copy()
    repaired = cv2.inpaint(
        cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
        removal.astype(np.uint8) * 255,
        radius,
        cv2.INPAINT_TELEA,
    )
    return cv2.cvtColor(repaired, cv2.COLOR_BGR2RGB)


def shift_layer(image: Image.Image, dx: int, dy: int) -> Image.Image:
    """在固定画布内平移单层。"""
    shifted = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shifted.alpha_composite(image, (dx, dy))
    return shifted


def remap_rgba_premultiplied(
    image: Image.Image,
    map_x: np.ndarray,
    map_y: np.ndarray,
) -> Image.Image:
    """在预乘 alpha 空间形变，消除透明边缘的黑白锯齿。"""
    data = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = data[:, :, 3:4] / 255.0
    premultiplied = np.dstack((data[:, :, :3] * alpha, data[:, :, 3]))
    warped = cv2.remap(
        premultiplied,
        map_x.astype(np.float32),
        map_y.astype(np.float32),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    warped_alpha = np.clip(warped[:, :, 3:4], 0, 255)
    warped_rgb = np.clip(
        warped[:, :, :3] / np.maximum(warped_alpha / 255.0, 1e-6),
        0,
        255,
    )
    output = np.dstack((warped_rgb, warped_alpha)).astype(np.uint8)
    output[output[:, :, 3] == 0, :3] = 0
    return Image.fromarray(output, mode="RGBA")


def sway_hair_layer(image: Image.Image, name: str) -> Image.Image:
    """锁住发根，仅让离根较远的发梢平滑摆动。"""
    dx, dy = HAIR_QA_OFFSETS[name]
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    if name == "front-hair":
        progress = np.clip((yy.astype(np.float32) - 188.0) / 150.0, 0.0, 1.0)
    else:
        root_x, root_y, inner, span = {
            "back-hair": (500.0, 236.0, 105.0, 300.0),
            "side-hair-left": (414.0, 256.0, 34.0, 165.0),
            "side-hair-right": (585.0, 250.0, 36.0, 170.0),
        }[name]
        distance = np.hypot(xx.astype(np.float32) - root_x, yy.astype(np.float32) - root_y)
        progress = np.clip((distance - inner) / span, 0.0, 1.0)
    eased = progress * progress * (3.0 - 2.0 * progress)
    map_x = xx.astype(np.float32) - eased * float(dx)
    map_y = yy.astype(np.float32) - eased * float(dy)
    return remap_rgba_premultiplied(image, map_x, map_y)


def bend_tail(image: Image.Image, maximum_dx: float = 8.0) -> Image.Image:
    """让尾根保持连接，位移沿尾身平滑增加。"""
    data = np.asarray(image)
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    progress = np.clip((yy.astype(np.float32) - 980.0) / 400.0, 0.0, 1.0)
    eased = progress * progress * (3.0 - 2.0 * progress)
    map_x = xx.astype(np.float32) - eased * maximum_dx
    map_y = yy.astype(np.float32)
    warped = cv2.remap(
        data,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return Image.fromarray(warped, mode="RGBA")


def alpha_array(image: Image.Image) -> np.ndarray:
    """读取图层 alpha。"""
    return np.asarray(image.getchannel("A"))


def make_feature_masks() -> dict[str, np.ndarray]:
    """返回经 200% 参考图校准的脸部区域。"""
    eye_left = draw_mask(
        polygons=(
            ((423, 295), (435, 279), (456, 267), (477, 273), (491, 290),
             (486, 313), (469, 329), (446, 326), (430, 313)),
        )
    )
    eye_right = draw_mask(
        polygons=(
            ((502, 288), (514, 270), (535, 261), (555, 267), (571, 283),
             (566, 306), (550, 322), (528, 323), (511, 309)),
        )
    )
    return {
        "eye-left": eye_left,
        "eye-right": eye_right,
        "iris-left": draw_mask(ellipses=((445, 276, 484, 327),)),
        "iris-right": draw_mask(ellipses=((520, 269, 560, 323),)),
        "brow-left": draw_mask(
            polygons=(
                ((439, 260), (451, 253), (468, 252), (487, 258),
                 (485, 263), (468, 258), (452, 259), (441, 265)),
            )
        ),
        "brow-right": draw_mask(
            polygons=(
                ((511, 257), (524, 250), (541, 250), (559, 256),
                 (557, 261), (541, 256), (525, 256), (513, 262)),
            )
        ),
        "mouth": draw_mask(
            polygons=(
                ((471, 338), (483, 333), (518, 333), (530, 340),
                 (531, 355), (523, 373), (511, 378), (488, 377),
                 (476, 368), (469, 350)),
            )
        ),
    }


def make_semantic_masks(
    rgb: np.ndarray,
    subject_alpha: np.ndarray,
) -> dict[str, np.ndarray]:
    """把单张主体分为可审计的语义区域。"""
    subject = subject_alpha > 8
    red = rgb[:, :, 0].astype(np.int16)
    green = rgb[:, :, 1].astype(np.int16)
    blue = rgb[:, :, 2].astype(np.int16)
    mean = rgb.mean(axis=2)
    hair_like = (
        ((mean < 185) & (blue - red > 7) & (blue > 100) & (green - red > 1))
        | ((mean >= 185) & (blue - red > 19) & (green - red > 10))
        | ((mean < 132) & (blue - red > 2))
    )

    tail_zone = draw_mask(
        polygons=(
            ((520, 560), (620, 590), (713, 663), (786, 770), (831, 884),
             (846, 1008), (824, 1116), (790, 1162), (850, 1191),
             (907, 1262), (903, 1346), (867, 1391), (823, 1397),
             (778, 1345), (735, 1291), (672, 1260), (620, 1290),
             (594, 1241), (622, 1183), (690, 1134), (733, 1060),
             (748, 964), (717, 850), (650, 733), (565, 651)),
        )
    )

    hand_zone = draw_mask(
        polygons=(
            ((239, 414), (263, 392), (296, 398), (319, 418), (338, 455),
             (340, 497), (324, 525), (334, 552), (355, 590), (377, 622),
             (361, 654), (329, 646), (304, 613), (285, 568), (270, 526),
             (247, 501), (237, 462)),
            ((319, 438), (345, 430), (379, 447), (414, 470), (456, 498),
             (470, 529), (457, 556), (472, 578), (507, 603), (558, 626),
             (550, 658), (512, 672), (468, 652), (432, 621), (404, 587),
             (379, 552), (346, 527), (326, 492)),
        )
    )

    core_zone = draw_mask(ellipses=((267, 362, 395, 501),))
    head_zone = draw_mask(
        polygons=(
            ((495, 178), (548, 191), (585, 224), (607, 271), (605, 344),
             (575, 378), (528, 405), (479, 402), (436, 379), (405, 349),
             (398, 291), (414, 239), (452, 198)),
        )
    )

    body_guard = draw_mask(
        polygons=(
            ((374, 372), (485, 365), (555, 414), (589, 526), (579, 654),
             (510, 730), (404, 726), (323, 666), (296, 549), (313, 435)),
            ((498, 365), (572, 373), (646, 416), (720, 516), (703, 571),
             (647, 626), (559, 623), (519, 552)),
            ((253, 625), (387, 604), (521, 633), (671, 725), (700, 838),
             (647, 979), (486, 998), (331, 972), (219, 883), (213, 779)),
        )
    )
    clothing_guard = draw_mask(
        polygons=(
            ((363, 386), (500, 377), (568, 432), (590, 543), (557, 667),
             (474, 728), (374, 690), (305, 612), (285, 493), (317, 420)),
            ((244, 624), (388, 605), (535, 647), (684, 746), (691, 837),
             (631, 929), (500, 980), (336, 967), (215, 879), (214, 770)),
        )
    )
    tail_overlay_guard = draw_mask(
        polygons=(
            ((492, 559), (583, 575), (656, 638), (709, 735), (700, 836),
             (650, 846), (575, 790), (508, 700)),
        )
    )

    hair_zone = draw_mask(
        polygons=(
            ((360, 55), (640, 55), (676, 205), (744, 245), (835, 326),
             (919, 443), (935, 575), (885, 681), (788, 727), (675, 708),
             (586, 647), (495, 604), (418, 668), (302, 721), (185, 691),
             (112, 612), (108, 476), (163, 363), (256, 307), (336, 246)),
        )
    )
    exclusive_hair = draw_mask(
        polygons=(
            ((359, 65), (646, 55), (654, 229), (591, 260), (546, 240),
             (505, 190), (454, 235), (393, 263), (363, 218)),
            ((107, 346), (219, 300), (302, 337), (309, 480), (292, 638),
             (211, 704), (108, 617)),
            ((698, 236), (786, 274), (876, 357), (929, 475), (928, 606),
             (866, 691), (747, 724), (694, 635)),
        )
    )
    ear_zone = draw_mask(
        polygons=(
            ((389, 72), (450, 153), (407, 205), (379, 166)),
            ((574, 145), (616, 61), (641, 180), (615, 224)),
        )
    )
    face_lock_zone = draw_mask(
        polygons=(
            ((343, 198), (453, 170), (505, 186), (553, 164), (657, 190),
             (666, 333), (620, 438), (548, 452), (501, 388), (448, 449),
             (365, 425), (332, 319)),
        )
    )

    features = make_feature_masks()
    feature_exclusion = dilate(
        features["eye-left"]
        | features["eye-right"]
        | features["brow-left"]
        | features["brow-right"]
        | features["mouth"],
        2,
    )

    hair = subject & hair_zone & hair_like
    hair |= subject & exclusive_hair
    hair |= subject & ear_zone
    hair |= subject & face_lock_zone & hair_like
    hair &= ~hand_zone
    hair &= ~core_zone
    hair &= ~(clothing_guard & ~face_lock_zone)
    hair &= ~feature_exclusion
    yy = np.indices((HEIGHT, WIDTH))[0]
    hair &= ~(tail_zone & (yy > 650))
    hair = clean_components(hair, minimum_area=6)

    front_zone = draw_mask(
        polygons=(
            ((367, 62), (640, 56), (652, 217), (611, 271), (566, 307),
             (522, 266), (488, 327), (438, 324), (393, 276), (363, 211)),
        )
    )
    side_left_zone = draw_mask(
        polygons=(
            ((322, 218), (431, 209), (467, 289), (452, 399), (409, 469),
             (344, 453), (313, 345)),
        )
    )
    side_right_zone = draw_mask(
        polygons=(
            ((543, 193), (645, 201), (681, 286), (669, 394), (621, 471),
             (560, 441), (532, 334)),
        )
    )
    xx = np.indices((HEIGHT, WIDTH))[1]
    front_hair = hair & front_zone
    side_left = hair & side_left_zone & ~front_hair
    side_right = hair & side_right_zone & ~front_hair & ~side_left
    foreground_overlap = hair & (head_zone | body_guard) & ~front_hair
    side_left |= foreground_overlap & (xx < 500)
    side_right |= foreground_overlap & (xx >= 500)
    side_left &= ~front_hair
    side_right &= ~front_hair & ~side_left
    back_hair = hair & ~front_hair & ~side_left & ~side_right

    mouth_region = features["mouth"]
    mouth_signal = ((red - green > 20) | (mean < 150)) & mouth_region
    mouth_signal = cv2.dilate(
        mouth_signal.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1
    ).astype(bool) & mouth_region

    tail_owner = subject & tail_zone & ~tail_overlay_guard
    head_owner = subject & head_zone & ~hair
    hand_owner = subject & hand_zone
    core_owner = subject & core_zone & ~hand_owner
    torso = subject & ~hair & ~tail_owner & ~head_zone & ~hand_owner & ~core_owner
    torso |= subject & body_guard & ~hand_owner & ~core_owner & ~tail_owner

    return {
        "subject": subject,
        "tail": subject & tail_zone,
        "tail-owner": tail_owner,
        "hand": hand_owner,
        "core": core_owner,
        "core-zone": core_zone,
        "head-zone": head_zone,
        "head-owner": head_owner,
        "body-guard": body_guard,
        "tail-overlay-guard": tail_overlay_guard,
        "torso": torso,
        "hair": hair,
        "back-hair": back_hair,
        "front-hair": front_hair,
        "side-hair-left": side_left,
        "side-hair-right": side_right,
        "mouth-signal": clean_components(mouth_signal, minimum_area=3),
        **features,
    }


def make_eye_layers(
    rgb: np.ndarray,
    blink_rgb: np.ndarray,
    masks: dict[str, np.ndarray],
    side: str,
) -> dict[str, Image.Image]:
    """创建可独立注视的睁眼层与可交付的自然闭眼层。"""
    eye = masks[f"eye-{side}"]
    iris = masks[f"iris-{side}"] & eye
    yy = np.arange(HEIGHT)[:, None]
    iris &= yy >= (279 if side == "left" else 273)
    iris = erode(iris, 1)

    # 眼白层保留原画眼线和眼窝，只修掉虹膜；移动虹膜后不会留下原位 ghost。
    white_rgb = inpaint(rgb, dilate(iris, 1), radius=6)

    lid_region = draw_mask(
        ellipses=(
            (419, 280, 497, 333)
            if side == "left"
            else (497, 273, 578, 328),
        )
    )
    reference_skin = lid_region & (blink_rgb.mean(axis=2) > 150)
    source_skin = lid_region & (rgb.mean(axis=2) > 150)
    calibration = reference_skin & source_skin & ~erode(eye, 2)
    matched_blink = blink_rgb.astype(np.int16)
    if np.any(calibration):
        delta = np.median(
            rgb[calibration].astype(np.int16)
            - blink_rgb[calibration].astype(np.int16),
            axis=0,
        )
        delta = np.clip(delta, -18, 18)
        matched_blink = matched_blink + delta.reshape(1, 1, 3)
    matched_blink = np.clip(matched_blink, 0, 255).astype(np.uint8)

    return {
        f"eye-{side}-white": rgba(white_rgb, mask_alpha(eye, sigma=0.7)),
        f"eye-{side}-iris": rgba(rgb, mask_alpha(iris, sigma=0.35)),
        f"eye-{side}-upper-lid": rgba(
            matched_blink,
            mask_alpha(lid_region, sigma=1.8),
        ),
    }


def resize_rgba_premultiplied(
    image: Image.Image,
    size: tuple[int, int],
) -> Image.Image:
    """以预乘 alpha 缩放语义部件，避免透明边缘出现黑线。"""
    data = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = data[:, :, 3:4] / 255.0
    premultiplied = np.dstack((data[:, :, :3] * alpha, data[:, :, 3]))
    resized = cv2.resize(premultiplied, size, interpolation=cv2.INTER_LANCZOS4)
    resized_alpha = np.clip(resized[:, :, 3:4], 0, 255)
    divisor = np.maximum(resized_alpha / 255.0, 1e-6)
    resized_rgb = np.clip(resized[:, :, :3] / divisor, 0, 255)
    output = np.dstack((resized_rgb, resized_alpha)).astype(np.uint8)
    output[output[:, :, 3] == 0, :3] = 0
    return Image.fromarray(output, mode="RGBA")


def bend_rgba(image: Image.Image, center_offset: float) -> Image.Image:
    """用连续位移场弯曲嘴型，保留原画像素纹理。"""
    data = np.asarray(image.convert("RGBA"), dtype=np.float32)
    height, width = data.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    normalized_x = (xx.astype(np.float32) - (width - 1) / 2) / max(width / 2, 1)
    displacement = center_offset * (1.0 - np.clip(normalized_x**2, 0.0, 1.0))
    alpha = data[:, :, 3:4] / 255.0
    premultiplied = np.dstack((data[:, :, :3] * alpha, data[:, :, 3]))
    warped = cv2.remap(
        premultiplied,
        xx.astype(np.float32),
        yy.astype(np.float32) - displacement,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    warped_alpha = np.clip(warped[:, :, 3:4], 0, 255)
    warped_rgb = np.clip(
        warped[:, :, :3] / np.maximum(warped_alpha / 255.0, 1e-6),
        0,
        255,
    )
    output = np.dstack((warped_rgb, warped_alpha)).astype(np.uint8)
    output[output[:, :, 3] == 0, :3] = 0
    return Image.fromarray(output, mode="RGBA")


def place_face_part(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """把局部语义部件缩放并放回原始全画布坐标。"""
    target = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    resized = resize_rgba_premultiplied(image, (box[2] - box[0], box[3] - box[1]))
    target.alpha_composite(resized, (box[0], box[1]))
    return target


def mouth_source_layer(rgb: np.ndarray, masks: dict[str, np.ndarray]) -> Image.Image:
    """从批准原画提取完整嘴腔轮廓，不夹带下巴和领口。"""
    signal = masks["mouth-signal"] & masks["mouth"]
    signal &= np.arange(HEIGHT)[:, None] <= 376
    signal = cv2.morphologyEx(
        signal.astype(np.uint8),
        cv2.MORPH_CLOSE,
        np.ones((5, 5), np.uint8),
        iterations=1,
    )
    contours, _ = cv2.findContours(signal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    for contour in contours:
        if cv2.contourArea(contour) >= 16:
            cv2.drawContours(filled, [contour], -1, 255, thickness=cv2.FILLED)
    mouth_alpha = mask_alpha(filled > 0, sigma=0.45)
    return rgba(rgb, mouth_alpha)


def make_face_layers(
    rgb: np.ndarray,
    blink_rgb: np.ndarray,
    masks: dict[str, np.ndarray],
) -> dict[str, Image.Image]:
    """创建双眼、双眉与四种源纹理互斥嘴型。"""
    layers: dict[str, Image.Image] = {}
    layers.update(make_eye_layers(rgb, blink_rgb, masks, "left"))
    layers.update(make_eye_layers(rgb, blink_rgb, masks, "right"))

    layers["brow-left"] = rgba(
        rgb,
        mask_alpha(masks["brow-left"], sigma=0.45),
    )
    layers["brow-right"] = rgba(
        rgb,
        mask_alpha(masks["brow-right"], sigma=0.45),
    )

    neutral = mouth_source_layer(rgb, masks)
    neutral_box = neutral.getchannel("A").getbbox()
    if neutral_box is None:
        raise RuntimeError("批准原画未提取到嘴部素材")
    local = neutral.crop(neutral_box)
    layers["mouth-neutral"] = neutral
    layers["mouth-smile"] = place_face_part(
        bend_rgba(local, center_offset=2.0),
        (469, 341, 532, 373),
    )
    layers["mouth-talk"] = place_face_part(
        bend_rgba(local, center_offset=0.5),
        (481, 337, 520, 376),
    )
    layers["mouth-worried"] = place_face_part(
        bend_rgba(local, center_offset=-3.5),
        (473, 343, 529, 373),
    )
    return layers


def make_head_base(
    rgb: np.ndarray,
    subject_alpha: np.ndarray,
    masks: dict[str, np.ndarray],
) -> Image.Image:
    """创建覆盖表情后方与小幅头发位移后的完整脸底。"""
    head_visible = masks["head-owner"]
    head_underfill = dilate(head_visible, 7) & masks["head-zone"]
    feature_union = (
        dilate(masks["eye-left"], 2)
        | dilate(masks["eye-right"], 2)
        | masks["brow-left"]
        | masks["brow-right"]
        | dilate(masks["mouth"], 1)
    )
    repaired = inpaint(rgb, feature_union, radius=7)
    smooth = cv2.GaussianBlur(repaired, (0, 0), 3.2)
    blend = cv2.GaussianBlur(
        erode(feature_union, 1).astype(np.float32),
        (0, 0),
        1.2,
    )[:, :, None]
    repaired = np.rint(
        repaired.astype(np.float32) * (1.0 - blend)
        + smooth.astype(np.float32) * blend
    ).astype(np.uint8)
    hair_replacement = head_underfill & masks["hair"]
    repaired = inpaint(repaired, hair_replacement, radius=8)

    alpha = mask_alpha(head_underfill, sigma=0.75)
    alpha[head_visible] = np.maximum(alpha[head_visible], subject_alpha[head_visible])
    return rgba(repaired, alpha)


def make_effect_layers(
    original_rgb: np.ndarray,
    subject_alpha: np.ndarray,
) -> dict[str, Image.Image]:
    """从不可变原图提取气泡，并重建同构声呐线。"""
    bubble_region = draw_mask(ellipses=BUBBLE_ELLIPSES)
    red = original_rgb[:, :, 0].astype(np.int16)
    green = original_rgb[:, :, 1].astype(np.int16)
    blue = original_rgb[:, :, 2].astype(np.int16)
    chroma = original_rgb.max(axis=2).astype(np.int16) - original_rgb.min(axis=2).astype(np.int16)
    gray = cv2.cvtColor(original_rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 35, 90)
    signal = np.clip(
        np.maximum(blue - red, 0) * 7
        + np.maximum(green - red, 0) * 3
        + chroma * 2
        + (edges > 0) * 155,
        0,
        255,
    ).astype(np.uint8)
    bubble_alpha = signal * bubble_region.astype(np.uint8)
    bubble_alpha = cv2.GaussianBlur(bubble_alpha, (0, 0), 0.55)
    bubble_alpha[subject_alpha > 32] = 0

    sonar = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sonar)
    center = (511, 329)
    for radius, width, opacity in (
        (203, 4, 33),
        (246, 4, 29),
        (289, 5, 27),
        (333, 5, 23),
    ):
        box = (
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        )
        draw.arc(box, 194, 350, fill=(79, 183, 237, opacity), width=width)
        draw.arc(box, 10, 166, fill=(79, 183, 237, opacity), width=width)
    draw.arc((122, 1358, 904, 1552), 184, 356, fill=(73, 156, 225, 36), width=6)
    for x, y in ((462, 44), (588, 42), (796, 193), (759, 742)):
        draw.rounded_rectangle((x, y, x + 24, y + 8), radius=2, fill=(91, 194, 240, 36))

    return {
        "bubbles": rgba(original_rgb, bubble_alpha),
        "sonar": sonar,
    }


def build_layers(
    original_rgb: np.ndarray,
    subject_rgb: np.ndarray,
    subject_alpha: np.ndarray,
    blink_reference_rgb: np.ndarray,
) -> tuple[dict[str, Image.Image], dict[str, np.ndarray]]:
    """构建 23 张真实语义图层与 seam 验证区域。"""
    masks = make_semantic_masks(subject_rgb, subject_alpha)
    layers: dict[str, Image.Image] = {}

    for name in ("back-hair", "front-hair", "side-hair-left", "side-hair-right"):
        layers[name] = rgba(
            subject_rgb,
            mask_alpha(masks[name], subject_alpha, sigma=0.35),
        )

    tail_repair_mask = dilate(masks["hair"] & masks["tail"], 2) & masks["tail"]
    tail_repair = inpaint(subject_rgb, tail_repair_mask, radius=11)
    tail_alpha = mask_alpha(masks["tail"], subject_alpha, sigma=0.4)
    layers["tail"] = rgba(tail_repair, tail_alpha)

    foreground_hair = (
        masks["front-hair"]
        | masks["side-hair-left"]
        | masks["side-hair-right"]
    )
    torso_underfill = (
        dilate(masks["torso"], 8)
        & masks["body-guard"]
        & (masks["hand"] | foreground_hair)
    )
    torso_repair = inpaint(subject_rgb, torso_underfill, radius=9)
    torso_alpha = mask_alpha(masks["torso"], subject_alpha)
    torso_alpha[torso_underfill] = 255
    layers["torso"] = rgba(torso_repair, torso_alpha)

    layers["head-base"] = make_head_base(subject_rgb, subject_alpha, masks)
    layers.update(make_face_layers(subject_rgb, blink_reference_rgb, masks))

    hand_alpha = mask_alpha(masks["hand"], subject_alpha, sigma=0.35)
    layers["hand-front"] = rgba(subject_rgb, hand_alpha)

    core_repair = inpaint(
        subject_rgb,
        dilate(masks["hand"], 2) & masks["core-zone"],
        radius=7,
    )
    core_alpha = mask_alpha(masks["core-zone"], subject_alpha, sigma=0.5)
    layers["core"] = rgba(core_repair, core_alpha)
    layers.update(make_effect_layers(original_rgb, subject_alpha))

    missing = set(LAYER_NAMES) - set(layers)
    extra = set(layers) - set(LAYER_NAMES)
    if missing or extra:
        raise RuntimeError(f"图层清单错误: missing={sorted(missing)} extra={sorted(extra)}")

    tail_seam = draw_mask(
        polygons=(
            ((548, 579), (631, 604), (700, 665), (681, 734),
             (604, 705), (544, 654)),
        )
    ) & masks["subject"]
    seam_masks = {
        "blink": (masks["eye-left"] | masks["eye-right"]) & masks["head-zone"],
        "gaze": (masks["eye-left"] | masks["eye-right"]) & masks["head-zone"],
        "hair": dilate(masks["head-owner"], 5) & masks["head-zone"],
        "hand": torso_underfill,
        "tail": tail_seam,
        "torso-underfill": torso_underfill,
    }
    return layers, seam_masks


def transparent_composite(
    layers: dict[str, Image.Image],
    *,
    visible: set[str],
    transforms: dict[str, Image.Image] | None = None,
    extras: Iterable[Image.Image] = (),
) -> Image.Image:
    """按 manifest 的 z 顺序合成透明角色。"""
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    changed = transforms or {}
    for name in sorted(visible, key=lambda item: Z_INDEX[item]):
        canvas = Image.alpha_composite(canvas, changed.get(name, layers[name]))
    for extra in extras:
        canvas = Image.alpha_composite(canvas, extra)
    return canvas


def checkerboard() -> Image.Image:
    """创建可暴露透明洞与色跳的深浅棋盘底。"""
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (29, 40, 62, 255))
    draw = ImageDraw.Draw(canvas)
    tile = 48
    for y in range(0, HEIGHT, tile):
        for x in range(0, WIDTH, tile):
            if (x // tile + y // tile) % 2 == 0:
                draw.rectangle(
                    (x, y, x + tile - 1, y + tile - 1),
                    fill=(66, 78, 101, 255),
                )
    return canvas


def on_checker(character: Image.Image) -> Image.Image:
    """把透明角色放到 seam 检查底上。"""
    return Image.alpha_composite(checkerboard(), character)


def masked_shift(
    image: Image.Image,
    dx: int,
    dy: int,
    clip_alpha: np.ndarray | None = None,
) -> Image.Image:
    """平移图层并可选限制到父蒙版。"""
    shifted = shift_layer(image, dx, dy)
    if clip_alpha is None:
        return shifted
    data = np.asarray(shifted).copy()
    data[:, :, 3] = np.minimum(data[:, :, 3], clip_alpha)
    return Image.fromarray(data, mode="RGBA")


def make_qa_scenarios(
    layers: dict[str, Image.Image],
) -> tuple[dict[str, Image.Image], dict[str, Image.Image]]:
    """生成六类 seam QA 的透明合成与展示图。"""
    character_scenarios: dict[str, Image.Image] = {}
    display_scenarios: dict[str, Image.Image] = {}

    neutral = transparent_composite(layers, visible=NEUTRAL_VISIBLE)
    character_scenarios["neutral"] = neutral
    display_scenarios["neutral"] = on_checker(neutral)

    blink = transparent_composite(layers, visible=BLINK_VISIBLE)
    character_scenarios["blink"] = blink
    display_scenarios["blink"] = on_checker(blink)

    left_transforms = {
        "eye-left-iris": masked_shift(
            layers["eye-left-iris"], -5, 0, alpha_array(layers["eye-left-white"])
        ),
        "eye-right-iris": masked_shift(
            layers["eye-right-iris"], -5, 0, alpha_array(layers["eye-right-white"])
        ),
    }
    right_transforms = {
        "eye-left-iris": masked_shift(
            layers["eye-left-iris"], 5, 0, alpha_array(layers["eye-left-white"])
        ),
        "eye-right-iris": masked_shift(
            layers["eye-right-iris"], 5, 0, alpha_array(layers["eye-right-white"])
        ),
    }
    gaze_left = transparent_composite(
        layers, visible=NEUTRAL_VISIBLE, transforms=left_transforms
    )
    gaze_right = transparent_composite(
        layers, visible=NEUTRAL_VISIBLE, transforms=right_transforms
    )
    character_scenarios["gaze"] = gaze_left
    gaze_display = Image.new("RGBA", (WIDTH * 2, HEIGHT), (0, 0, 0, 0))
    gaze_display.alpha_composite(on_checker(gaze_left), (0, 0))
    gaze_display.alpha_composite(on_checker(gaze_right), (WIDTH, 0))
    display_scenarios["gaze-extremes"] = gaze_display

    hair_names = ("back-hair", "front-hair", "side-hair-left", "side-hair-right")
    hair_transforms = {
        name: sway_hair_layer(layers[name], name)
        for name in hair_names
    }
    hair = transparent_composite(
        layers, visible=NEUTRAL_VISIBLE, transforms=hair_transforms
    )
    character_scenarios["hair"] = hair
    display_scenarios["hair-offset"] = on_checker(hair)

    hand = transparent_composite(
        layers,
        visible=NEUTRAL_VISIBLE,
        transforms={"hand-front": shift_layer(layers["hand-front"], 4, -3)},
    )
    character_scenarios["hand"] = hand
    display_scenarios["hand-offset"] = on_checker(hand)

    tail = transparent_composite(
        layers,
        visible=NEUTRAL_VISIBLE,
        transforms={"tail": bend_tail(layers["tail"])},
    )
    character_scenarios["tail"] = tail
    display_scenarios["tail-offset"] = on_checker(tail)
    return character_scenarios, display_scenarios


def save_layers(layers: dict[str, Image.Image]) -> None:
    """保存严格全画布 RGBA 图层。"""
    LAYER_DIR.mkdir(parents=True, exist_ok=True)
    for existing in LAYER_DIR.glob("*.png"):
        if existing.stem not in LAYER_NAMES:
            existing.unlink()
    for name in LAYER_NAMES:
        image = layers[name]
        if image.mode != "RGBA" or image.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"图层格式错误: {name} {image.mode} {image.size}")
        image.save(LAYER_DIR / f"{name}.png", optimize=True)


def create_psd(layers: dict[str, Image.Image]) -> None:
    """创建包含七个指定分组的可编辑 PSD。"""
    from psd_tools import PSDImage

    psd = PSDImage.new(mode="RGB", size=(WIDTH, HEIGHT), depth=8)
    for group_name, names in GROUPS.items():
        group = psd.create_group(name=group_name, open_folder=True)
        for name in names:
            layer = psd.create_pixel_layer(layers[name], name=name)
            if name.startswith("mouth-") and name != "mouth-neutral":
                layer.visible = False
            group.append(layer)
    psd.save(PSD_PATH)


def component_overlap(alpha: np.ndarray, anchor: np.ndarray) -> int:
    """计算移动部件与锚区仍保有的搭接像素。"""
    return int(np.count_nonzero((alpha > 16) & anchor))


def original_position_ghost_metrics(
    original: Image.Image,
    shifted: Image.Image,
    stationary: Image.Image,
) -> dict[str, int]:
    """统计移动后仍由静止层复现原像素的残影。"""
    original_data = np.asarray(original).astype(np.int16)
    shifted_data = np.asarray(shifted).astype(np.int16)
    stationary_data = np.asarray(stationary).astype(np.int16)
    vacated = (original_data[:, :, 3] > 64) & (shifted_data[:, :, 3] < 16)
    same_rgb = (
        np.abs(stationary_data[:, :, :3] - original_data[:, :, :3]).max(axis=2)
        <= 2
    )
    ghost = vacated & (stationary_data[:, :, 3] > 64) & same_rgb
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        ghost.astype(np.uint8), connectivity=8
    )
    areas = [int(stats[label, cv2.CC_STAT_AREA]) for label in range(1, count)]
    return {
        "originalPositionGhostPixels": sum(area for area in areas if area >= 96),
        "rawExactMatchPixelCandidates": int(np.count_nonzero(ghost)),
        "largestExactMatchComponent": max(areas, default=0),
    }


def significant_component_count(mask: np.ndarray, minimum_area: int = 24) -> int:
    """统计足以构成视觉部件的连通域数量。"""
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8),
        connectivity=8,
    )
    return sum(
        int(stats[label, cv2.CC_STAT_AREA]) >= minimum_area
        for label in range(1, count)
    )


def largest_component_pixels(mask: np.ndarray, minimum_area: int = 3) -> int:
    """返回视觉异常蒙版中最大连通域面积。"""
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8),
        connectivity=8,
    )
    areas = [
        int(stats[label, cv2.CC_STAT_AREA])
        for label in range(1, count)
        if int(stats[label, cv2.CC_STAT_AREA]) >= minimum_area
    ]
    return max(areas, default=0)


def visual_proxy_metrics(
    reference: Image.Image,
    candidate: Image.Image,
    region: np.ndarray | None = None,
) -> dict[str, int]:
    """从实际 RGBA 合成检测内部透明洞、暗缝和新增断片。"""
    reference_data = np.asarray(reference.convert("RGBA"), dtype=np.int16)
    candidate_data = np.asarray(candidate.convert("RGBA"), dtype=np.int16)
    if reference_data.shape != candidate_data.shape:
        raise ValueError("视觉代理指标要求同尺寸 RGBA 合成图")

    reference_present = reference_data[:, :, 3] > 64
    candidate_present = candidate_data[:, :, 3] > 64
    reference_interior = erode(reference_present, 2)
    inspection = np.ones_like(reference_present, dtype=bool)
    if region is not None:
        if region.shape != reference_present.shape:
            raise ValueError("视觉代理区域尺寸不匹配")
        inspection &= region

    new_holes = reference_interior & inspection & ~candidate_present
    reference_luma = (
        reference_data[:, :, 0] * 54
        + reference_data[:, :, 1] * 183
        + reference_data[:, :, 2] * 19
    ) // 256
    candidate_luma = (
        candidate_data[:, :, 0] * 54
        + candidate_data[:, :, 1] * 183
        + candidate_data[:, :, 2] * 19
    ) // 256
    new_dark = (
        reference_interior
        & inspection
        & candidate_present
        & (reference_luma - candidate_luma >= 38)
        & (candidate_luma <= 118)
    )
    disconnected = max(
        significant_component_count(candidate_present)
        - significant_component_count(reference_present),
        0,
    )
    return {
        "newInteriorHolePixels": int(np.count_nonzero(new_holes)),
        "largestNewHoleComponentPixels": largest_component_pixels(new_holes),
        "largestNewDarkComponentPixels": largest_component_pixels(new_dark),
        "newDisconnectedComponents": int(disconnected),
    }


def seam_metrics(
    scenarios: dict[str, Image.Image],
    layers: dict[str, Image.Image],
    seam_masks: dict[str, np.ndarray],
) -> dict[str, dict[str, int]]:
    """以中性实际合成为基准量化五类动作的视觉异常。"""
    metrics: dict[str, dict[str, int]] = {}
    neutral = scenarios["neutral"]
    for scenario in ("blink", "gaze", "hair", "hand", "tail"):
        proxy = visual_proxy_metrics(
            neutral,
            scenarios[scenario],
            seam_masks[scenario],
        )
        metrics[scenario] = {
            **proxy,
            "transparentHolePixels": proxy["newInteriorHolePixels"],
            "disconnectedRequiredParts": proxy["newDisconnectedComponents"],
            "anchorOverlapPixels": 0,
        }

    hair_alpha = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    for name in ("back-hair", "front-hair", "side-hair-left", "side-hair-right"):
        hair_alpha = np.maximum(
            hair_alpha,
            alpha_array(sway_hair_layer(layers[name], name)),
        )
    hair_anchor = alpha_array(layers["head-base"]) > 16
    metrics["hair"]["anchorOverlapPixels"] = component_overlap(hair_alpha, hair_anchor)
    metrics["hair"]["disconnectedRequiredParts"] = max(
        metrics["hair"]["disconnectedRequiredParts"],
        int(metrics["hair"]["anchorOverlapPixels"] == 0),
    )
    original_hair = transparent_composite(
        layers,
        visible={"back-hair", "front-hair", "side-hair-left", "side-hair-right"},
    )
    shifted_hair = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    for name in ("back-hair", "front-hair", "side-hair-left", "side-hair-right"):
        shifted_hair = Image.alpha_composite(
            shifted_hair,
            sway_hair_layer(layers[name], name),
        )
    stationary_hair = transparent_composite(
        layers,
        visible=CHARACTER_VISIBLE
        - {"back-hair", "front-hair", "side-hair-left", "side-hair-right"},
    )
    metrics["hair"].update(
        original_position_ghost_metrics(original_hair, shifted_hair, stationary_hair)
    )

    hand_alpha = alpha_array(shift_layer(layers["hand-front"], 4, -3))
    hand_anchor = (
        (alpha_array(layers["torso"]) > 16)
        | (alpha_array(layers["core"]) > 16)
    )
    metrics["hand"]["anchorOverlapPixels"] = component_overlap(hand_alpha, hand_anchor)
    metrics["hand"]["disconnectedRequiredParts"] = max(
        metrics["hand"]["disconnectedRequiredParts"],
        int(metrics["hand"]["anchorOverlapPixels"] == 0),
    )
    stationary_hand = transparent_composite(
        layers,
        visible=CHARACTER_VISIBLE - {"hand-front"},
    )
    metrics["hand"].update(
        original_position_ghost_metrics(
            layers["hand-front"],
            shift_layer(layers["hand-front"], 4, -3),
            stationary_hand,
        )
    )

    moved_tail = bend_tail(layers["tail"])
    tail_alpha = alpha_array(moved_tail)
    tail_anchor = alpha_array(layers["torso"]) > 16
    metrics["tail"]["anchorOverlapPixels"] = component_overlap(tail_alpha, tail_anchor)
    metrics["tail"]["disconnectedRequiredParts"] = max(
        metrics["tail"]["disconnectedRequiredParts"],
        int(metrics["tail"]["anchorOverlapPixels"] == 0),
    )
    stationary_tail = transparent_composite(
        layers,
        visible=CHARACTER_VISIBLE - {"tail"},
    )
    metrics["tail"].update(
        original_position_ghost_metrics(layers["tail"], moved_tail, stationary_tail)
    )
    return metrics


def save_qa(display_scenarios: dict[str, Image.Image]) -> None:
    """保存六张供人工 full-size 检查的 QA 图。"""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    filenames = {
        "neutral": "neutral.png",
        "blink": "blink.png",
        "gaze-extremes": "gaze-extremes.png",
        "hair-offset": "hair-offset.png",
        "hand-offset": "hand-offset.png",
        "tail-offset": "tail-offset.png",
    }
    for scenario, filename in filenames.items():
        display_scenarios[scenario].save(EVIDENCE_DIR / filename, optimize=True)


def preview_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """优先使用常见无衬线字体，并在精简环境安全回退。"""
    for candidate in (
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def ocean_background(size: tuple[int, int]) -> Image.Image:
    """创建低干扰深海渐变底，便于用户看清角色而非棋盘。"""
    width, height = size
    yy, xx = np.mgrid[0:height, 0:width]
    progress = yy.astype(np.float32) / max(height - 1, 1)
    top = np.array((23, 68, 104), dtype=np.float32)
    bottom = np.array((5, 16, 38), dtype=np.float32)
    rgb = top[None, None, :] * (1.0 - progress[:, :, None])
    rgb += bottom[None, None, :] * progress[:, :, None]
    glow = np.exp(
        -(
            ((xx - width * 0.48) / max(width * 0.55, 1)) ** 2
            + ((yy - height * 0.25) / max(height * 0.42, 1)) ** 2
        )
        * 2.0
    )
    rgb += glow[:, :, None] * np.array((8, 25, 35), dtype=np.float32)
    canvas = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")
    for x, y, radius, opacity in (
        (66, 126, 8, 62),
        (162, 74, 4, 54),
        (width - 92, 156, 10, 48),
        (width - 165, height - 92, 5, 42),
    ):
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            outline=(124, 221, 248, opacity),
            width=max(1, radius // 3),
        )
    return canvas


def character_on_ocean(character: Image.Image) -> Image.Image:
    """把透明角色叠到中性深海底。"""
    base = ocean_background(character.size).convert("RGBA")
    return Image.alpha_composite(base, character.convert("RGBA")).convert("RGB")


def focused_panel(
    character: Image.Image,
    crop: tuple[int, int, int, int],
    size: tuple[int, int],
) -> Image.Image:
    """输出不拉伸的动作局部，确保面部和 seam 足够大。"""
    focused = character_on_ocean(character).crop(crop)
    return ImageOps.fit(
        focused,
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


def mouth_characters(layers: dict[str, Image.Image]) -> dict[str, Image.Image]:
    """以同一脸底合成四个互斥嘴型。"""
    base_visible = NEUTRAL_VISIBLE - MOUTH_LAYERS
    return {
        name.removeprefix("mouth-"): transparent_composite(
            layers,
            visible=base_visible | {name},
        )
        for name in sorted(MOUTH_LAYERS, key=lambda item: Z_INDEX[item])
    }


def save_mouth_expressions(layers: dict[str, Image.Image]) -> None:
    """保存四嘴型等比例大特写，供 focused QA。"""
    canvas = ocean_background((2048, 1024))
    draw = ImageDraw.Draw(canvas)
    title_font = preview_font(38)
    label_font = preview_font(26)
    draw.text(
        (48, 26),
        "FOUR DELIVERED MOUTH LAYERS / SAME HEAD BASE",
        fill=(230, 248, 255),
        font=title_font,
    )
    variants = mouth_characters(layers)
    for index, name in enumerate(("neutral", "smile", "talk", "worried")):
        left = 32 + index * 504
        top = 96
        right = left + 480
        bottom = 990
        draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=24,
            fill=(10, 28, 51, 230),
            outline=(65, 162, 202, 220),
            width=2,
        )
        draw.text(
            (left + 20, top + 16),
            name.upper(),
            fill=(222, 245, 255),
            font=label_font,
        )
        panel = focused_panel(
            variants[name],
            (350, 160, 650, 440),
            (440, 770),
        )
        canvas.paste(panel, (left + 20, top + 72))
    canvas.save(EVIDENCE_DIR / "mouth-expressions.png", optimize=True)


def save_movable_preview(
    layers: dict[str, Image.Image],
    scenarios: dict[str, Image.Image],
) -> None:
    """输出含前后对照、脸部大特写和三类动作局部的用户预览。"""
    canvas = ocean_background((2400, 1800))
    draw = ImageDraw.Draw(canvas)
    title_font = preview_font(48)
    subtitle_font = preview_font(24)
    label_font = preview_font(24)
    small_font = preview_font(18)
    draw.text(
        (54, 34),
        "DEEPSEEK V2 / FIRST MOVABLE-LAYER PREVIEW",
        fill=(232, 249, 255),
        font=title_font,
    )
    draw.text(
        (56, 98),
        "23 real RGBA layers  |  delivered-layer before/after comparisons",
        fill=(127, 219, 247),
        font=subtitle_font,
    )

    right_transforms = {
        "eye-left-iris": masked_shift(
            layers["eye-left-iris"],
            5,
            0,
            alpha_array(layers["eye-left-white"]),
        ),
        "eye-right-iris": masked_shift(
            layers["eye-right-iris"],
            5,
            0,
            alpha_array(layers["eye-right-white"]),
        ),
    }
    gaze_right = transparent_composite(
        layers,
        visible=NEUTRAL_VISIBLE,
        transforms=right_transforms,
    )
    face_cards = (
        ("OPEN", scenarios["neutral"]),
        ("BLINK", scenarios["blink"]),
        ("GAZE LEFT", scenarios["gaze"]),
        ("GAZE RIGHT", gaze_right),
    )
    for index, (label, character) in enumerate(face_cards):
        left = 48 + index * 588
        top = 154
        draw.rounded_rectangle(
            (left, top, left + 552, top + 466),
            radius=22,
            fill=(8, 27, 51, 235),
            outline=(61, 157, 201, 220),
            width=2,
        )
        draw.text((left + 18, top + 14), label, fill=(226, 246, 255), font=label_font)
        panel = focused_panel(character, (330, 150, 680, 455), (516, 388))
        canvas.paste(panel, (left + 18, top + 62))

    mouths = mouth_characters(layers)
    for index, name in enumerate(("neutral", "smile", "talk", "worried")):
        left = 48 + index * 588
        top = 650
        draw.rounded_rectangle(
            (left, top, left + 552, top + 334),
            radius=22,
            fill=(8, 27, 51, 235),
            outline=(61, 157, 201, 220),
            width=2,
        )
        draw.text(
            (left + 18, top + 12),
            f"MOUTH / {name.upper()}",
            fill=(226, 246, 255),
            font=label_font,
        )
        panel = focused_panel(mouths[name], (390, 255, 610, 410), (516, 260))
        canvas.paste(panel, (left + 18, top + 58))

    action_cards = (
        ("HAIR SWAY / ROOT LOCK", scenarios["hair"], (180, 50, 850, 760)),
        ("HAND OFFSET / +4,-3", scenarios["hand"], (170, 310, 640, 780)),
        ("TAIL SWAY / ROOT LOCK", scenarios["tail"], (430, 500, 960, 1450)),
    )
    for index, (label, moved, crop) in enumerate(action_cards):
        left = 48 + index * 784
        top = 1020
        card_width = 748
        draw.rounded_rectangle(
            (left, top, left + card_width, top + 710),
            radius=24,
            fill=(7, 24, 47, 235),
            outline=(61, 157, 201, 220),
            width=2,
        )
        draw.text((left + 18, top + 14), label, fill=(226, 246, 255), font=label_font)
        draw.text((left + 58, top + 58), "BEFORE", fill=(125, 216, 245), font=small_font)
        draw.text((left + 424, top + 58), "AFTER", fill=(125, 216, 245), font=small_font)
        before = focused_panel(scenarios["neutral"], crop, (340, 610))
        after = focused_panel(moved, crop, (340, 610))
        canvas.paste(before, (left + 18, top + 88))
        canvas.paste(after, (left + 390, top + 88))
        draw.line(
            (left + 366, top + 386, left + 382, top + 386),
            fill=(124, 222, 248),
            width=3,
        )
    canvas.save(EVIDENCE_DIR / "movable-layer-preview.png", optimize=True)


def save_stats(
    layers: dict[str, Image.Image],
    subject: Image.Image,
    scenarios: dict[str, Image.Image],
    seam_masks: dict[str, np.ndarray],
) -> None:
    """保存像素级来源、覆盖率与接缝指标。"""
    character = transparent_composite(layers, visible=CHARACTER_VISIBLE)
    actual = np.asarray(character).astype(np.int16)
    expected = np.asarray(subject).astype(np.int16)
    expected_alpha = expected[:, :, 3]
    visible = expected_alpha > 8
    differences = np.abs(actual[:, :, :3] - expected[:, :, :3])
    visible_differences = differences[visible]
    coverage = int(np.count_nonzero((actual[:, :, 3] > 8) & visible))
    expected_count = int(np.count_nonzero(visible))

    stats = {
        "canvas": {"width": WIDTH, "height": HEIGHT},
        "originalSha256": sha256(ORIGINAL_PATH),
        "subjectSha256": sha256(SUBJECT_PATH),
        "method": "manual-calibrated-masks-plus-local-telea-inpainting",
        "layers": [],
        "neutralComparison": {
            "meanAbsoluteError": round(float(visible_differences.mean()), 6),
            "p95AbsoluteError": int(np.percentile(visible_differences, 95)),
            "subjectCoverageRatio": round(coverage / max(expected_count, 1), 10),
        },
        "seamScenarios": seam_metrics(scenarios, layers, seam_masks),
    }
    for name in LAYER_NAMES:
        path = LAYER_DIR / f"{name}.png"
        alpha = alpha_array(layers[name])
        box = layers[name].getchannel("A").getbbox()
        stats["layers"].append(
            {
                "name": name,
                "sha256": sha256(path),
                "nonTransparentPixels": int(np.count_nonzero(alpha)),
                "fullyOpaquePixels": int(np.count_nonzero(alpha == 255)),
                "bbox": list(box) if box else None,
            }
        )
    (EVIDENCE_DIR / "layer-stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_inputs() -> tuple[Image.Image, Image.Image, Image.Image]:
    """验证批准输入未被替换或缩放。"""
    if sha256(ORIGINAL_PATH) != EXPECTED_ORIGINAL_SHA256:
        raise RuntimeError("原始 PNG SHA-256 不匹配")
    if sha256(SUBJECT_PATH) != EXPECTED_SUBJECT_SHA256:
        raise RuntimeError("批准主体 matte SHA-256 不匹配")
    if sha256(BLINK_REFERENCE_PATH) != EXPECTED_BLINK_REFERENCE_SHA256:
        raise RuntimeError("闭眼参考图 SHA-256 不匹配")
    original = Image.open(ORIGINAL_PATH)
    subject = Image.open(SUBJECT_PATH)
    blink_reference = Image.open(BLINK_REFERENCE_PATH)
    if (
        original.size != (WIDTH, HEIGHT)
        or subject.size != (WIDTH, HEIGHT)
        or blink_reference.size != (WIDTH, HEIGHT)
    ):
        raise RuntimeError("输入画布必须为 1024x1536")
    if original.mode != "RGB" or subject.mode != "RGBA" or blink_reference.mode != "RGB":
        raise RuntimeError(
            "输入模式错误: "
            f"original={original.mode} subject={subject.mode} "
            f"blink={blink_reference.mode}"
        )
    return original, subject, blink_reference


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        choices=("layers", "qa", "all"),
        default="all",
    )
    args = parser.parse_args()

    original, subject, blink_reference = validate_inputs()
    original_rgb = np.asarray(original)
    subject_array = np.asarray(subject)
    subject_rgb = subject_array[:, :, :3]
    subject_alpha = subject_array[:, :, 3]
    layers, seam_masks = build_layers(
        original_rgb,
        subject_rgb,
        subject_alpha,
        np.asarray(blink_reference),
    )
    save_layers(layers)
    if args.stage == "layers":
        print("ASSET_BUILD=PASS STAGE=layers LAYERS=23")
        return

    scenarios, displays = make_qa_scenarios(layers)
    save_qa(displays)
    save_mouth_expressions(layers)
    save_movable_preview(layers, scenarios)
    if args.stage == "all":
        create_psd(layers)
        save_stats(layers, subject, scenarios, seam_masks)
    print(f"ASSET_BUILD=PASS STAGE={args.stage} LAYERS=23")


if __name__ == "__main__":
    main()
