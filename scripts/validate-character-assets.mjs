#!/usr/bin/env node

import { createHash } from 'node:crypto';
import {
  existsSync,
  readFileSync,
  realpathSync,
  statSync,
} from 'node:fs';
import { dirname, isAbsolute, relative, resolve, sep } from 'node:path';
import { inflateSync } from 'node:zlib';

const REQUIRED_LAYER_NAMES = [
  'back-hair',
  'tail',
  'torso',
  'head-base',
  'eye-left-white',
  'eye-left-iris',
  'eye-left-upper-lid',
  'eye-right-white',
  'eye-right-iris',
  'eye-right-upper-lid',
  'brow-left',
  'brow-right',
  'mouth-neutral',
  'mouth-smile',
  'mouth-talk',
  'mouth-worried',
  'front-hair',
  'side-hair-left',
  'side-hair-right',
  'hand-front',
  'core',
  'bubbles',
  'sonar',
];

const KNOWN_MOTION_GROUPS = new Set([
  'blink',
  'body',
  'brow',
  'effects',
  'gaze',
  'hair',
  'hand',
  'head',
  'mouth',
  'prop',
  'tail',
]);

const PNG_SIGNATURE = Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
]);

class ValidationFailure extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

const fail = (code, message) => {
  throw new ValidationFailure(code, message);
};

const isRecord = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

const paeth = (left, up, upperLeft) => {
  const prediction = left + up - upperLeft;
  const leftDistance = Math.abs(prediction - left);
  const upDistance = Math.abs(prediction - up);
  const upperLeftDistance = Math.abs(prediction - upperLeft);
  if (leftDistance <= upDistance && leftDistance <= upperLeftDistance) {
    return left;
  }
  return upDistance <= upperLeftDistance ? up : upperLeft;
};

const inspectPng = (buffer, expectedWidth, expectedHeight, layerName) => {
  if (buffer.length < 33 || !buffer.subarray(0, 8).equals(PNG_SIGNATURE)) {
    fail('INVALID_PNG', `${layerName} 不是有效 PNG`);
  }

  let offset = 8;
  let header = null;
  const compressedParts = [];
  let sawEnd = false;
  while (offset + 12 <= buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const chunkEnd = offset + 12 + length;
    if (chunkEnd > buffer.length) {
      fail('INVALID_PNG', `${layerName} 的 PNG chunk 越界`);
    }
    const type = buffer.toString('ascii', offset + 4, offset + 8);
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      if (header !== null || length !== 13) {
        fail('INVALID_PNG', `${layerName} 的 IHDR 非法`);
      }
      header = {
        width: data.readUInt32BE(0),
        height: data.readUInt32BE(4),
        bitDepth: data[8],
        colorType: data[9],
        compression: data[10],
        filter: data[11],
        interlace: data[12],
      };
    } else if (type === 'IDAT') {
      compressedParts.push(data);
    } else if (type === 'IEND') {
      sawEnd = true;
      break;
    }
    offset = chunkEnd;
  }

  if (header === null) {
    fail('INVALID_PNG', `${layerName} 缺少 IHDR`);
  }
  if (header.width !== expectedWidth || header.height !== expectedHeight) {
    fail(
      'INVALID_DIMENSIONS',
      `${layerName} 尺寸为 ${header.width}x${header.height}`,
    );
  }
  if (header.colorType !== 4 && header.colorType !== 6) {
    fail('MISSING_ALPHA', `${layerName} 没有显式 alpha 通道`);
  }
  if (!sawEnd || compressedParts.length === 0) {
    fail('INVALID_PNG', `${layerName} 缺少必需 PNG chunk`);
  }
  if (
    header.bitDepth !== 8 ||
    header.compression !== 0 ||
    header.filter !== 0 ||
    header.interlace !== 0
  ) {
    fail('UNSUPPORTED_PNG', `${layerName} 必须是 8-bit 非隔行 RGBA/GA PNG`);
  }

  const bytesPerPixel = header.colorType === 6 ? 4 : 2;
  const rowBytes = header.width * bytesPerPixel;
  let inflated;
  try {
    inflated = inflateSync(Buffer.concat(compressedParts));
  } catch {
    fail('INVALID_PNG', `${layerName} 的 IDAT 无法解压`);
  }
  const expectedBytes = (rowBytes + 1) * header.height;
  if (inflated.length !== expectedBytes) {
    fail('INVALID_PNG', `${layerName} 解压后的像素长度异常`);
  }

  // 逐行撤销 PNG filter，才能确认 alpha 不是一张透明空气层。
  const previous = Buffer.alloc(rowBytes);
  const current = Buffer.alloc(rowBytes);
  let visiblePixels = 0;
  let sourceOffset = 0;
  for (let y = 0; y < header.height; y += 1) {
    const filterType = inflated[sourceOffset];
    sourceOffset += 1;
    for (let x = 0; x < rowBytes; x += 1) {
      const raw = inflated[sourceOffset + x];
      const left = x >= bytesPerPixel ? current[x - bytesPerPixel] : 0;
      const up = previous[x];
      const upperLeft = x >= bytesPerPixel ? previous[x - bytesPerPixel] : 0;
      let reconstructed;
      if (filterType === 0) {
        reconstructed = raw;
      } else if (filterType === 1) {
        reconstructed = raw + left;
      } else if (filterType === 2) {
        reconstructed = raw + up;
      } else if (filterType === 3) {
        reconstructed = raw + Math.floor((left + up) / 2);
      } else if (filterType === 4) {
        reconstructed = raw + paeth(left, up, upperLeft);
      } else {
        fail('INVALID_PNG', `${layerName} 使用未知 PNG filter`);
      }
      current[x] = reconstructed & 0xff;
    }
    for (let x = bytesPerPixel - 1; x < rowBytes; x += bytesPerPixel) {
      if (current[x] !== 0) {
        visiblePixels += 1;
      }
    }
    current.copy(previous);
    sourceOffset += rowBytes;
  }
  if (visiblePixels === 0) {
    fail('EMPTY_ALPHA', `${layerName} 是空白透明层`);
  }
  if (visiblePixels === header.width * header.height) {
    fail('FULL_CANVAS_LAYER', `${layerName} 覆盖整张画布，疑似重复整图`);
  }
  return visiblePixels;
};

const assertInsidePackage = (packageDirectory, filePath, layerName) => {
  if (isAbsolute(filePath)) {
    fail('INVALID_FILE_PATH', `${layerName} 使用绝对路径`);
  }
  const candidate = resolve(packageDirectory, filePath);
  const relativePath = relative(packageDirectory, candidate);
  if (
    relativePath === '..' ||
    relativePath.startsWith(`..${sep}`) ||
    isAbsolute(relativePath)
  ) {
    fail('INVALID_FILE_PATH', `${layerName} 越出资产包目录`);
  }
  if (!existsSync(candidate) || !statSync(candidate).isFile()) {
    fail('MISSING_FILE', `${layerName} 缺少文件 ${filePath}`);
  }
  const packageRealPath = realpathSync(packageDirectory);
  const candidateRealPath = realpathSync(candidate);
  const realRelative = relative(packageRealPath, candidateRealPath);
  if (
    realRelative === '..' ||
    realRelative.startsWith(`..${sep}`) ||
    isAbsolute(realRelative)
  ) {
    fail('INVALID_FILE_PATH', `${layerName} 通过链接越出资产包目录`);
  }
  return candidateRealPath;
};

const validateManifest = (manifestPath) => {
  if (!existsSync(manifestPath) || !statSync(manifestPath).isFile()) {
    fail('MISSING_MANIFEST', `找不到 manifest: ${manifestPath}`);
  }
  let manifest;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  } catch {
    fail('INVALID_JSON', 'manifest 不是有效 JSON');
  }
  if (!isRecord(manifest) || manifest.schemaVersion !== 1) {
    fail('INVALID_SCHEMA', 'schemaVersion 必须严格等于 1');
  }
  if (
    !isRecord(manifest.canvas) ||
    manifest.canvas.width !== 1024 ||
    manifest.canvas.height !== 1536
  ) {
    fail('INVALID_CANVAS', '画布必须严格为 1024x1536');
  }
  if (!Array.isArray(manifest.layers)) {
    fail('INVALID_LAYERS', 'layers 必须是数组');
  }
  const names = manifest.layers.map((layer) => layer?.name);
  if (
    names.length !== REQUIRED_LAYER_NAMES.length ||
    names.some((name, index) => name !== REQUIRED_LAYER_NAMES[index])
  ) {
    fail('INVALID_INVENTORY', '图层必须按约定顺序完整列出 23 项');
  }

  const zIndices = new Set();
  const fileHashes = new Set();
  const packageDirectory = dirname(realpathSync(manifestPath));
  for (const layer of manifest.layers) {
    if (!isRecord(layer)) {
      fail('INVALID_LAYER', '图层条目必须是对象');
    }
    if (typeof layer.file !== 'string' || !layer.file.endsWith('.png')) {
      fail('INVALID_FILE_PATH', `${layer.name} 的文件路径非法`);
    }
    if (!Number.isInteger(layer.zIndex)) {
      fail('INVALID_Z_INDEX', `${layer.name} 的 zIndex 必须是整数`);
    }
    if (zIndices.has(layer.zIndex)) {
      fail('DUPLICATE_Z_INDEX', `${layer.name} 重复使用 zIndex ${layer.zIndex}`);
    }
    zIndices.add(layer.zIndex);
    if (
      !isRecord(layer.anchor) ||
      !Number.isFinite(layer.anchor.x) ||
      !Number.isFinite(layer.anchor.y) ||
      layer.anchor.x < 0 ||
      layer.anchor.x > 1 ||
      layer.anchor.y < 0 ||
      layer.anchor.y > 1
    ) {
      fail('INVALID_ANCHOR', `${layer.name} 的 anchor 必须落在 0..1`);
    }
    if (!KNOWN_MOTION_GROUPS.has(layer.motionGroup)) {
      fail('UNKNOWN_MOTION_GROUP', `${layer.name} 的 motionGroup 未登记`);
    }
    if (layer.required !== true) {
      fail('INVALID_REQUIRED', `${layer.name} 必须标记 required=true`);
    }

    const layerPath = assertInsidePackage(
      packageDirectory,
      layer.file,
      layer.name,
    );
    const content = readFileSync(layerPath);
    inspectPng(
      content,
      manifest.canvas.width,
      manifest.canvas.height,
      layer.name,
    );
    const digest = createHash('sha256').update(content).digest('hex');
    if (fileHashes.has(digest)) {
      fail('DUPLICATE_LAYER_CONTENT', `${layer.name} 与另一图层字节完全重复`);
    }
    fileHashes.add(digest);
  }
  return manifest.layers.length;
};

const manifestPath = resolve(
  process.argv[2] ??
    'assets/character/deepseek-v2/character.manifest.json',
);

try {
  const layerCount = validateManifest(manifestPath);
  process.stdout.write(`ASSET_VALIDATION=PASS LAYERS=${layerCount}\n`);
} catch (error) {
  const code = error instanceof ValidationFailure ? error.code : 'INTERNAL_ERROR';
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`ASSET_VALIDATION=FAIL CODE=${code} MESSAGE=${message}\n`);
  process.exitCode = 1;
}
