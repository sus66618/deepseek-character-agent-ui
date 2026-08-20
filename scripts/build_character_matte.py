#!/usr/bin/env python3
"""构建并验收 DeepSeek v2 角色透明主体。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time
from typing import Any

import cv2
import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SOURCE_SHA256 = (
    "24DF7985AE880E21CB5EB7FF6C811631C00CEFC82F9BE4C91D580350C61A79D5"
)
EXPECTED_SOURCE_SIZE = (1024, 1536)
EXPECTED_MODEL_SHA256 = (
    "F15622D853E8260172812B657053460E20806F04B9E05147D49AF7BED31A6E99"
)
EXPECTED_MODEL_MD5 = "6F184E756BB3BD901C8849220A83E38E"
CANONICAL_SOURCE = Path(
    "E:/adventure/ai_code/codex_image/character/ai-anime-girl-deepseek-v2.png"
)
SOURCE_COPY = (
    PROJECT_ROOT / "assets/character/deepseek-v2/source/original.png"
)
OUTPUT_PATH = (
    PROJECT_ROOT / "assets/character/deepseek-v2/source/subject-rgba.png"
)
SOURCE_EVIDENCE_PATH = PROJECT_ROOT / "evidence/asset-source.json"
EVIDENCE_DIR = PROJECT_ROOT / "evidence/assets"

MODEL_PROVENANCE = {
    "architecture": "ISNetDIS",
    "rembgModelName": "isnet-anime",
    "upstreamRepository": "https://github.com/SkyTNT/anime-segmentation",
    "officialModelPage": "https://huggingface.co/skytnt/anime-seg/blob/main/isnetis.onnx",
    "rembgReleaseArtifact": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx",
    "license": "Apache-2.0",
}


def sha256_file(path: Path) -> str:
    """返回文件的大写 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def md5_file(path: Path) -> str:
    """返回模型发布记录使用的大写 MD5。"""
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_source_evidence(
    path: Path,
    *,
    source_path: Path,
    copied_path: Path,
    source_sha256: str,
    copied_sha256: str,
) -> dict[str, Any]:
    """验证已有的不可变源证据与本次实际读取完全一致。"""
    evidence = json.loads(path.read_text(encoding="utf-8"))
    checks = {
        "algorithm": evidence.get("algorithm") == "SHA-256",
        "expectedSha256": evidence.get("expectedSha256", "").upper()
        == EXPECTED_SOURCE_SHA256,
        "sourcePath": Path(evidence.get("sourcePath", "")) == source_path,
        "copiedPath": evidence.get("copiedPath")
        == copied_path.relative_to(PROJECT_ROOT).as_posix(),
        "sourceSha256": evidence.get("sourceSha256", "").upper()
        == source_sha256,
        "copiedSha256": evidence.get("copiedSha256", "").upper()
        == copied_sha256,
        "matching": evidence.get("matching") is True,
        "bytes": evidence.get("bytes") == source_path.stat().st_size,
        "dimensions": evidence.get("dimensions")
        == {"width": EXPECTED_SOURCE_SIZE[0], "height": EXPECTED_SOURCE_SIZE[1]},
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"不可变源证据不匹配: {', '.join(failed)}")
    return evidence


def load_verified_source(
    path: Path,
    *,
    expected_sha256: str,
    expected_size: tuple[int, int],
) -> Image.Image:
    """先验证不可变源，再以 RGB 方式载入。"""
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256.upper():
        raise ValueError(
            f"源文件 SHA-256 不匹配: expected={expected_sha256.upper()} "
            f"actual={actual_sha256}"
        )

    with Image.open(path) as image:
        if image.size != expected_size:
            raise ValueError(f"源文件尺寸错误: expected={expected_size} actual={image.size}")
        return image.convert("RGB")


def compose_rgba(rgb: np.ndarray, alpha: np.ndarray) -> Image.Image:
    """只把 alpha 附到原图 RGB，禁止模型重绘像素混入。"""
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"RGB 数组形状错误: {rgb.shape}")
    if alpha.shape != rgb.shape[:2]:
        raise ValueError(f"alpha 与 RGB 尺寸不一致: {alpha.shape} vs {rgb.shape[:2]}")
    if rgb.dtype != np.uint8 or alpha.dtype != np.uint8:
        raise ValueError("RGB 与 alpha 必须是 uint8")
    return Image.fromarray(np.dstack((rgb, alpha)), mode="RGBA")


def keep_primary_subject(alpha: np.ndarray, *, threshold: int = 16) -> np.ndarray:
    """保留最大连通主体及其软边，移除泡泡、声呐与地面等孤立残留。"""
    if alpha.ndim != 2 or alpha.dtype != np.uint8:
        raise ValueError("alpha 必须是二维 uint8 数组")
    if not 1 <= threshold <= 254:
        raise ValueError("threshold 必须在 1..254")

    foreground = (alpha >= threshold).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        foreground,
        connectivity=8,
    )
    if count <= 1:
        return np.zeros_like(alpha)

    areas = stats[1:, cv2.CC_STAT_AREA]
    primary_label = int(np.argmax(areas)) + 1
    primary = labels == primary_label
    soft_edge_band = cv2.dilate(
        primary.astype(np.uint8),
        np.ones((5, 5), dtype=np.uint8),
        iterations=1,
    ).astype(bool)
    keep = primary | (soft_edge_band & (alpha > 0) & (alpha < threshold))

    result = np.zeros_like(alpha)
    result[keep] = alpha[keep]
    return result


def remove_ground_reflection(
    alpha: np.ndarray,
    *,
    guide_alpha: np.ndarray | None = None,
    scan_start: int,
    apply_start: int,
    confidence_threshold: int = 220,
    edge_margin: int = 2,
) -> np.ndarray:
    """按每列高置信主体的下边界裁掉靴底反射，并保留少量软边。"""
    if alpha.ndim != 2 or alpha.dtype != np.uint8:
        raise ValueError("alpha 必须是二维 uint8 数组")
    guide = alpha if guide_alpha is None else guide_alpha
    if guide.shape != alpha.shape or guide.dtype != np.uint8:
        raise ValueError("guide_alpha 必须与 alpha 同尺寸且为 uint8")
    height, width = alpha.shape
    if not 0 <= scan_start <= apply_start < height:
        raise ValueError("scan_start 与 apply_start 超出画布")
    if not 1 <= confidence_threshold <= 254:
        raise ValueError("confidence_threshold 必须在 1..254")
    if edge_margin < 0:
        raise ValueError("edge_margin 不能为负数")

    result = alpha.copy()
    for x in range(width):
        confident_rows = np.flatnonzero(
            guide[scan_start:, x] >= confidence_threshold
        )
        if confident_rows.size == 0:
            result[apply_start:, x] = 0
            continue
        boundary = scan_start + int(confident_rows[-1])
        first_removed = max(apply_start, boundary + edge_margin + 1)
        result[first_removed:, x] = 0
    return result


def measure_alpha(
    alpha: np.ndarray,
    *,
    foreground_threshold: int = 128,
) -> dict[str, Any]:
    """测量连通性、软边与被主体完全包围的 alpha 洞。"""
    if alpha.ndim != 2 or alpha.dtype != np.uint8:
        raise ValueError("alpha 必须是二维 uint8 数组")
    if not 1 <= foreground_threshold <= 254:
        raise ValueError("foreground_threshold 必须在 1..254")

    foreground = alpha >= foreground_threshold
    foreground_count, _, foreground_stats, _ = cv2.connectedComponentsWithStats(
        foreground.astype(np.uint8),
        connectivity=8,
    )
    foreground_areas = (
        foreground_stats[1:, cv2.CC_STAT_AREA]
        if foreground_count > 1
        else np.array([], dtype=np.int32)
    )

    background = (~foreground).astype(np.uint8)
    background_count, background_labels, background_stats, _ = (
        cv2.connectedComponentsWithStats(background, connectivity=8)
    )
    border_labels = set(np.unique(background_labels[0, :]))
    border_labels.update(np.unique(background_labels[-1, :]))
    border_labels.update(np.unique(background_labels[:, 0]))
    border_labels.update(np.unique(background_labels[:, -1]))
    hole_labels = [
        label
        for label in range(1, background_count)
        if label not in border_labels
    ]
    hole_pixels = sum(
        int(background_stats[label, cv2.CC_STAT_AREA]) for label in hole_labels
    )

    nonzero_pixels = int(np.count_nonzero(alpha))
    foreground_pixels = int(np.count_nonzero(foreground))
    largest_component_pixels = (
        int(foreground_areas.max()) if foreground_areas.size else 0
    )
    return {
        "nonTransparentPixels": nonzero_pixels,
        "fullyOpaquePixels": int(np.count_nonzero(alpha == 255)),
        "softAlphaPixels": int(np.count_nonzero((alpha > 0) & (alpha < 255))),
        "foregroundPixelsAt128": foreground_pixels,
        "foregroundComponentCountAt128": int(max(foreground_count - 1, 0)),
        "largestForegroundComponentPixelsAt128": largest_component_pixels,
        "largestForegroundComponentRatioAt128": (
            largest_component_pixels / foreground_pixels if foreground_pixels else 0.0
        ),
        "internalHoleCount": len(hole_labels),
        "internalHolePixels": hole_pixels,
        "alphaExtrema": [int(alpha.min()), int(alpha.max())],
    }


def measure_edge_halo(
    rgb: np.ndarray,
    alpha: np.ndarray,
    *,
    low_alpha_limit: int = 32,
    pale_luma_minimum: float = 210.0,
    pale_chroma_maximum: int = 25,
) -> dict[str, Any]:
    """量化低 alpha 浅色残边，并测量软边相对主体轮廓的宽度。"""
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ValueError("RGB 必须是三通道 uint8 数组")
    if alpha.shape != rgb.shape[:2] or alpha.dtype != np.uint8:
        raise ValueError("alpha 必须与 RGB 同尺寸且为 uint8")
    if not 2 <= low_alpha_limit <= 255:
        raise ValueError("low_alpha_limit 必须在 2..255")
    if not 0 <= pale_luma_minimum <= 255:
        raise ValueError("pale_luma_minimum 必须在 0..255")
    if not 0 <= pale_chroma_maximum <= 255:
        raise ValueError("pale_chroma_maximum 必须在 0..255")

    rgb_i16 = rgb.astype(np.int16)
    luma = rgb_i16.mean(axis=2)
    chroma = rgb_i16.max(axis=2) - rgb_i16.min(axis=2)
    low_alpha = (alpha > 0) & (alpha < low_alpha_limit)
    pale = (luma >= pale_luma_minimum) & (chroma <= pale_chroma_maximum)
    pale_risk = low_alpha & pale

    core = alpha >= 128
    fringe = (alpha > 0) & ~core
    if np.any(core) and np.any(fringe):
        distances = cv2.distanceTransform(
            (~core).astype(np.uint8),
            cv2.DIST_L2,
            5,
        )[fringe]
        distance_summary = {
            "p50": float(np.percentile(distances, 50)),
            "p90": float(np.percentile(distances, 90)),
            "p95": float(np.percentile(distances, 95)),
            "p99": float(np.percentile(distances, 99)),
            "maximum": float(distances.max()),
        }
    else:
        distance_summary = {
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "maximum": 0.0,
        }

    return {
        "lowAlphaLimitExclusive": low_alpha_limit,
        "lowAlphaPixelCount": int(np.count_nonzero(low_alpha)),
        "lowAlphaPalePixelCount": int(np.count_nonzero(pale_risk)),
        "lowAlphaPaleEquivalentOpaquePixels": float(alpha[pale_risk].sum() / 255),
        "foregroundFringePixels": int(np.count_nonzero(fringe)),
        "foregroundFringeDistancePixels": distance_summary,
    }


def measure_internal_holes(
    alpha: np.ndarray,
    *,
    foreground_threshold: int = 128,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """列出阈值轮廓内最大的封闭透明区域，供人工区分发丝留白与误抠洞。"""
    foreground = alpha >= foreground_threshold
    background = (~foreground).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        background,
        connectivity=8,
    )
    border_labels = set(np.unique(labels[0, :]))
    border_labels.update(np.unique(labels[-1, :]))
    border_labels.update(np.unique(labels[:, 0]))
    border_labels.update(np.unique(labels[:, -1]))

    holes: list[dict[str, Any]] = []
    for label in range(1, count):
        if label in border_labels:
            continue
        left = int(stats[label, cv2.CC_STAT_LEFT])
        top = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        holes.append(
            {
                "pixels": int(stats[label, cv2.CC_STAT_AREA]),
                "bboxInclusive": [
                    left,
                    top,
                    left + width - 1,
                    top + height - 1,
                ],
            }
        )
    holes.sort(key=lambda item: item["pixels"], reverse=True)
    return holes[:limit]


def measure_critical_retention(
    raw_alpha: np.ndarray,
    final_alpha: np.ndarray,
) -> dict[str, Any]:
    """用高置信原始预测检查重点区域是否被后处理误删。"""
    regions = {
        "earsAndCurls": (260, 35, 930, 470),
        "fingersAndHands": (180, 300, 760, 760),
        "capeAndSkirts": (175, 430, 800, 1110),
        "boots": (280, 1080, 700, 1536),
        "tailAndFins": (540, 650, 970, 1485),
    }
    result: dict[str, Any] = {}
    for name, (left, top, right, bottom) in regions.items():
        reference = raw_alpha[top:bottom, left:right] >= 240
        retained = final_alpha[top:bottom, left:right] >= 128
        reference_pixels = int(np.count_nonzero(reference))
        lost_pixels = int(np.count_nonzero(reference & ~retained))
        result[name] = {
            "bboxExclusive": [left, top, right, bottom],
            "rawHighConfidencePixels": reference_pixels,
            "lostBelowFinal128Pixels": lost_pixels,
            "lossRatio": (
                lost_pixels / reference_pixels if reference_pixels else 0.0
            ),
        }
    return result


def make_checker_background(
    size: tuple[int, int],
    *,
    cell_size: int = 32,
) -> Image.Image:
    """生成中等对比棋盘，便于同时检查亮边和暗边。"""
    width, height = size
    yy, xx = np.indices((height, width))
    cells = ((xx // cell_size) + (yy // cell_size)) % 2
    colors = np.array([[72, 82, 102], [190, 198, 211]], dtype=np.uint8)
    return Image.fromarray(colors[cells], mode="RGB")


def composite_for_qa(subject: Image.Image, background: Image.Image) -> Image.Image:
    """把主体合成到指定背景，不改动正式输出。"""
    if subject.mode != "RGBA" or background.mode != "RGB":
        raise ValueError("QA 合成要求 RGBA 主体与 RGB 背景")
    if subject.size != background.size:
        raise ValueError("QA 主体与背景尺寸不一致")
    canvas = background.convert("RGBA")
    canvas.alpha_composite(subject)
    return canvas.convert("RGB")


def save_qa_images(subject: Image.Image, output_dir: Path) -> list[dict[str, Any]]:
    """保存深、浅、棋盘背景及重点局部的 200% 像素级 QA 图。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    backgrounds = {
        "dark": Image.new("RGB", subject.size, (9, 17, 32)),
        "light": Image.new("RGB", subject.size, (248, 250, 255)),
        "checker": make_checker_background(subject.size),
    }
    composites = {
        name: composite_for_qa(subject, background)
        for name, background in backgrounds.items()
    }
    records: list[dict[str, Any]] = []
    doubled_size = (subject.width * 2, subject.height * 2)
    for name, image in composites.items():
        path = output_dir / f"matte-{name}-200.png"
        image.resize(doubled_size, Image.Resampling.NEAREST).save(
            path,
            optimize=True,
        )
        records.append(
            {
                "kind": name,
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "dimensions": [doubled_size[0], doubled_size[1]],
                "scalePercent": 200,
            }
        )

    detail_regions = {
        "ears-curls": (260, 35, 930, 470),
        "hands-cape": (180, 300, 800, 800),
        "skirts": (180, 680, 820, 1110),
        "boots": (280, 1080, 700, 1536),
        "tail-fins": (540, 650, 970, 1485),
    }
    checker = composites["checker"]
    for name, box in detail_regions.items():
        crop = checker.crop(box)
        path = output_dir / f"matte-detail-{name}-checker-200.png"
        crop.resize(
            (crop.width * 2, crop.height * 2),
            Image.Resampling.NEAREST,
        ).save(path, optimize=True)
        records.append(
            {
                "kind": f"detail-{name}-checker",
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sourceBboxExclusive": list(box),
                "dimensions": [crop.width * 2, crop.height * 2],
                "scalePercent": 200,
            }
        )
    return records


def run_inference(source: Image.Image, model_path: Path) -> tuple[np.ndarray, list[str], float]:
    """只在本地 CPU 上运行经过哈希锁定的 isnet-anime ONNX。"""
    if model_path.name != "isnet-anime.onnx":
        raise ValueError("模型文件名必须为 isnet-anime.onnx，避免 rembg 静默下载")
    if sha256_file(model_path) != EXPECTED_MODEL_SHA256:
        raise ValueError("isnet-anime 模型 SHA-256 不匹配")
    if md5_file(model_path) != EXPECTED_MODEL_MD5:
        raise ValueError("isnet-anime 模型 MD5 不匹配")

    os.environ["U2NET_HOME"] = str(model_path.parent.resolve())
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    from rembg import new_session

    started = time.perf_counter()
    session = new_session(
        "isnet-anime",
        providers=["CPUExecutionProvider"],
    )
    providers = list(session.inner_session.get_providers())
    if providers != ["CPUExecutionProvider"]:
        raise RuntimeError(f"推理 provider 不符合 CPU-only 约束: {providers}")
    predictions = session.predict(source)
    elapsed_seconds = time.perf_counter() - started
    if len(predictions) != 1:
        raise RuntimeError(f"isnet-anime 返回了异常 mask 数量: {len(predictions)}")
    raw_alpha = np.asarray(predictions[0].convert("L"), dtype=np.uint8)
    if raw_alpha.shape != (source.height, source.width):
        raise RuntimeError(f"模型 mask 尺寸异常: {raw_alpha.shape}")
    return raw_alpha, providers, elapsed_seconds


def build_matte(
    *,
    canonical_source: Path,
    source_copy: Path,
    model_path: Path,
    output_path: Path,
    evidence_dir: Path,
) -> dict[str, Any]:
    """执行源验证、分割、边缘细化、QA 渲染与量化验收。"""
    canonical_sha256 = sha256_file(canonical_source)
    copied_sha256 = sha256_file(source_copy)
    if canonical_sha256 != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"原始源 SHA-256 不匹配: {canonical_sha256}")
    if copied_sha256 != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"工作区源副本 SHA-256 不匹配: {copied_sha256}")
    if canonical_source.stat().st_size != source_copy.stat().st_size:
        raise ValueError("原始源与工作区副本字节数不一致")
    validate_source_evidence(
        SOURCE_EVIDENCE_PATH,
        source_path=canonical_source,
        copied_path=source_copy,
        source_sha256=canonical_sha256,
        copied_sha256=copied_sha256,
    )

    source = load_verified_source(
        source_copy,
        expected_sha256=EXPECTED_SOURCE_SHA256,
        expected_size=EXPECTED_SOURCE_SIZE,
    )
    source_rgb = np.asarray(source, dtype=np.uint8)
    raw_alpha, providers, elapsed_seconds = run_inference(source, model_path)

    from rembg.bg import alpha_matting_cutout

    matted = alpha_matting_cutout(
        source,
        Image.fromarray(raw_alpha, mode="L"),
        foreground_threshold=235,
        background_threshold=5,
        erode_structure_size=3,
    )
    matted_alpha = np.asarray(matted, dtype=np.uint8)[:, :, 3]
    matted_primary = keep_primary_subject(matted_alpha, threshold=16)
    raw_primary = keep_primary_subject(raw_alpha, threshold=16)
    final_alpha = remove_ground_reflection(
        matted_primary,
        guide_alpha=raw_primary,
        scan_start=1320,
        apply_start=1400,
        confidence_threshold=248,
        edge_margin=3,
    )
    subject = compose_rgba(source_rgb, final_alpha)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    subject.save(output_path, optimize=True)
    Image.fromarray(raw_alpha, mode="L").save(
        evidence_dir / "matte-isnet-raw-mask.png",
        optimize=True,
    )
    Image.fromarray(final_alpha, mode="L").save(
        evidence_dir / "matte-final-alpha.png",
        optimize=True,
    )
    qa_images = save_qa_images(subject, evidence_dir)

    persisted = np.asarray(Image.open(output_path).convert("RGBA"), dtype=np.uint8)
    rgb_exact_match = bool(np.array_equal(persisted[:, :, :3], source_rgb))
    alpha_metrics = measure_alpha(final_alpha)
    edge_metrics = measure_edge_halo(source_rgb, final_alpha)
    holes = measure_internal_holes(final_alpha)
    retention = measure_critical_retention(raw_alpha, final_alpha)

    reflection_removed = (matted_primary > 0) & (final_alpha == 0)
    detached_removed = (matted_alpha > 0) & (matted_primary == 0)
    foreground_pixels = alpha_metrics["foregroundPixelsAt128"]
    largest_pixels = alpha_metrics["largestForegroundComponentPixelsAt128"]
    residual = {
        "detachedMattePixelsRemoved": int(np.count_nonzero(detached_removed)),
        "groundReflectionPixelsRemoved": int(np.count_nonzero(reflection_removed)),
        "foregroundDetachedPixelsAt128": int(foreground_pixels - largest_pixels),
        "nonTransparentPixelsBelowRow1490": int(
            np.count_nonzero(final_alpha[1490:, :] > 0)
        ),
    }

    gates = {
        "sourceHashLocked": canonical_sha256 == copied_sha256 == EXPECTED_SOURCE_SHA256,
        "modelHashLocked": sha256_file(model_path) == EXPECTED_MODEL_SHA256,
        "cpuOnlyInference": providers == ["CPUExecutionProvider"],
        "rgba1024x1536": subject.mode == "RGBA" and subject.size == EXPECTED_SOURCE_SIZE,
        "rgbExactlyFromSource": rgb_exact_match,
        "primaryConnectivityAt128": alpha_metrics[
            "largestForegroundComponentRatioAt128"
        ]
        >= 0.999,
        "groundReflectionCleared": residual["nonTransparentPixelsBelowRow1490"] == 0,
        "criticalRegionRetention": all(
            region["lossRatio"] <= 0.005 for region in retention.values()
        ),
    }
    status = "PASS" if all(gates.values()) else "FAIL"
    report = {
        "schemaVersion": 1,
        "status": status,
        "scope": "Task 5A transparent subject matte only; no layer pack or PSD",
        "source": {
            "canonicalPath": canonical_source.as_posix(),
            "copiedPath": source_copy.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": canonical_sha256,
            "bytes": canonical_source.stat().st_size,
            "dimensions": list(source.size),
            "immutableEvidencePath": SOURCE_EVIDENCE_PATH.relative_to(
                PROJECT_ROOT
            ).as_posix(),
        },
        "model": {
            **MODEL_PROVENANCE,
            "sha256": sha256_file(model_path),
            "md5": md5_file(model_path),
            "bytes": model_path.stat().st_size,
            "providers": providers,
            "rembgVersion": importlib.metadata.version("rembg"),
            "onnxruntimeVersion": importlib.metadata.version("onnxruntime"),
            "inferenceSeconds": round(elapsed_seconds, 3),
            "sourceImageNetworkTransmission": False,
        },
        "refinement": {
            "alphaMatting": {
                "foregroundThreshold": 235,
                "backgroundThreshold": 5,
                "erodeStructureSize": 3,
            },
            "primarySubjectThreshold": 16,
            "groundReflectionCleanup": {
                "guide": "raw isnet-anime primary component",
                "scanStartRow": 1320,
                "applyStartRow": 1400,
                "confidenceThreshold": 248,
                "edgeMarginPixels": 3,
            },
        },
        "output": {
            "path": output_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256_file(output_path),
            "mode": subject.mode,
            "dimensions": list(subject.size),
            "rgbExactMatchWithSource": rgb_exact_match,
        },
        "measurements": {
            "alpha": alpha_metrics,
            "largestInternalHolesAt128": holes,
            "edgeHaloRisk": edge_metrics,
            "residualBackground": residual,
            "criticalRegionRetention": retention,
        },
        "qaImages": qa_images,
        "gates": gates,
    }
    qa_path = evidence_dir / "subject-matte-qa.json"
    qa_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if status != "PASS":
        failed = [name for name, passed in gates.items() if not passed]
        raise RuntimeError(f"MATTE_VALIDATION=FAIL gates={','.join(failed)}")
    return report


def parse_args() -> argparse.Namespace:
    """解析可复现构建参数；模型必须显式提供，脚本不会联网下载。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="已验证的本地 isnet-anime.onnx 路径",
    )
    parser.add_argument(
        "--canonical-source",
        type=Path,
        default=CANONICAL_SOURCE,
    )
    parser.add_argument(
        "--source-copy",
        type=Path,
        default=SOURCE_COPY,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=EVIDENCE_DIR,
    )
    return parser.parse_args()


def main() -> int:
    """命令行入口。"""
    args = parse_args()
    report = build_matte(
        canonical_source=args.canonical_source.resolve(),
        source_copy=args.source_copy.resolve(),
        model_path=args.model.resolve(),
        output_path=args.output.resolve(),
        evidence_dir=args.evidence_dir.resolve(),
    )
    print(
        "MATTE_VALIDATION=PASS "
        f"output={report['output']['path']} "
        f"sha256={report['output']['sha256']} "
        f"inferenceSeconds={report['model']['inferenceSeconds']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
