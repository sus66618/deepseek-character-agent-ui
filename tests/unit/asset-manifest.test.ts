import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, test } from 'vitest';

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
] as const;

interface AssetLayer {
  name: string;
  file: string;
  zIndex: number;
  anchor: { x: number; y: number };
  motionGroup: string;
  required: boolean;
}

interface AssetManifest {
  schemaVersion: number;
  canvas: { width: number; height: number };
  layers: AssetLayer[];
}

const manifestPath = resolve(
  process.cwd(),
  'assets/character/deepseek-v2/character.manifest.json',
);

const readManifest = (): AssetManifest =>
  JSON.parse(readFileSync(manifestPath, 'utf8')) as AssetManifest;

describe('character asset manifest contract', () => {
  test('publishes the exact required layer inventory on the source canvas', () => {
    const manifest = readManifest();

    expect(manifest.schemaVersion).toBe(1);
    expect(manifest.canvas).toEqual({ width: 1024, height: 1536 });
    expect(manifest.layers.map(({ name }) => name)).toEqual(REQUIRED_LAYER_NAMES);
  });

  test('gives every layer an explicit render contract', () => {
    const manifest = readManifest();

    for (const layer of manifest.layers) {
      expect(layer.file).toMatch(/^layers\/[a-z0-9-]+\.png$/);
      expect(Number.isInteger(layer.zIndex)).toBe(true);
      expect(layer.anchor.x).toBeGreaterThanOrEqual(0);
      expect(layer.anchor.x).toBeLessThanOrEqual(1);
      expect(layer.anchor.y).toBeGreaterThanOrEqual(0);
      expect(layer.anchor.y).toBeLessThanOrEqual(1);
      expect(layer.motionGroup.length).toBeGreaterThan(0);
      expect(layer.required).toBe(true);
    }
  });
});
