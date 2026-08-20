import {
  copyFileSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { afterEach, describe, expect, test } from 'vitest';

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

interface ValidatorResult {
  status: number | null;
  stdout: string;
  stderr: string;
}

const projectRoot = process.cwd();
const manifestPath = resolve(
  projectRoot,
  'assets/character/deepseek-v2/character.manifest.json',
);
const validatorPath = resolve(
  projectRoot,
  'scripts/validate-character-assets.mjs',
);
const temporaryPaths: string[] = [];

const readManifest = (): AssetManifest =>
  JSON.parse(readFileSync(manifestPath, 'utf8')) as AssetManifest;

const runValidator = (candidatePath = manifestPath): ValidatorResult => {
  const result = spawnSync(process.execPath, [validatorPath, candidatePath], {
    cwd: projectRoot,
    encoding: 'utf8',
  });

  return {
    status: result.status,
    stdout: result.stdout,
    stderr: result.stderr,
  };
};

const writeMutatedManifest = (
  mutate: (manifest: AssetManifest) => void,
): string => {
  const manifest = structuredClone(readManifest());
  mutate(manifest);
  const path = resolve(
    dirname(manifestPath),
    `.asset-manifest-test-${crypto.randomUUID()}.json`,
  );
  writeFileSync(path, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  temporaryPaths.push(path);
  return path;
};

afterEach(() => {
  for (const path of temporaryPaths.splice(0)) {
    rmSync(path, { force: true, recursive: true });
  }
});

describe('character asset manifest contract', () => {
  test('publishes the exact required layer inventory on the source canvas', () => {
    const manifest = readManifest();

    expect(manifest.schemaVersion).toBe(1);
    expect(manifest.canvas).toEqual({ width: 1024, height: 1536 });
    expect(manifest.layers.map(({ name }) => name)).toEqual(REQUIRED_LAYER_NAMES);
  });

  test('gives every layer a unique and known render contract', () => {
    const manifest = readManifest();
    const zIndices = manifest.layers.map(({ zIndex }) => zIndex);

    expect(new Set(zIndices).size).toBe(zIndices.length);
    for (const layer of manifest.layers) {
      expect(layer.file).toMatch(/^layers\/[a-z0-9-]+\.png$/);
      expect(Number.isInteger(layer.zIndex)).toBe(true);
      expect(layer.anchor.x).toBeGreaterThanOrEqual(0);
      expect(layer.anchor.x).toBeLessThanOrEqual(1);
      expect(layer.anchor.y).toBeGreaterThanOrEqual(0);
      expect(layer.anchor.y).toBeLessThanOrEqual(1);
      expect(KNOWN_MOTION_GROUPS.has(layer.motionGroup)).toBe(true);
      expect(layer.required).toBe(true);
    }
  });

  test('validates the real package through the command-line entry point', () => {
    const result = runValidator();

    expect(result.stderr).toBe('');
    expect(result.status).toBe(0);
    expect(result.stdout).toContain('ASSET_VALIDATION=PASS');
    expect(result.stdout).toContain('LAYERS=23');
  });

  test.each([
    {
      label: 'a missing layer file',
      expectedCode: 'MISSING_FILE',
      mutate: (manifest: AssetManifest) => {
        manifest.layers[0].file = 'layers/not-present.png';
      },
    },
    {
      label: 'duplicate z-indices',
      expectedCode: 'DUPLICATE_Z_INDEX',
      mutate: (manifest: AssetManifest) => {
        manifest.layers[1].zIndex = manifest.layers[0].zIndex;
      },
    },
    {
      label: 'an anchor outside the normalized range',
      expectedCode: 'INVALID_ANCHOR',
      mutate: (manifest: AssetManifest) => {
        manifest.layers[0].anchor.x = 1.01;
      },
    },
    {
      label: 'an unknown motion group',
      expectedCode: 'UNKNOWN_MOTION_GROUP',
      mutate: (manifest: AssetManifest) => {
        manifest.layers[0].motionGroup = 'teleport';
      },
    },
  ])('rejects $label', ({ expectedCode, mutate }) => {
    const result = runValidator(writeMutatedManifest(mutate));

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('ASSET_VALIDATION=FAIL');
    expect(result.stderr).toContain(expectedCode);
  });

  test('rejects a PNG without an explicit alpha channel', () => {
    const result = runValidator(
      writeMutatedManifest((manifest) => {
        manifest.layers[0].file = 'source/original.png';
      }),
    );

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('MISSING_ALPHA');
  });

  test('rejects a PNG whose dimensions do not match the canvas', () => {
    const fixtureDirectory = mkdtempSync(resolve(tmpdir(), 'character-asset-'));
    temporaryPaths.push(fixtureDirectory);
    const fixturePath = resolve(fixtureDirectory, 'wrong-size.png');
    writeFileSync(
      fixturePath,
      Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+Xw9VAAAAAElFTkSuQmCC',
        'base64',
      ),
    );
    const localFixture = resolve(dirname(manifestPath), 'source/wrong-size.png');
    copyFileSync(fixturePath, localFixture);
    temporaryPaths.push(localFixture);

    const result = runValidator(
      writeMutatedManifest((manifest) => {
        manifest.layers[0].file = 'source/wrong-size.png';
      }),
    );

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('INVALID_DIMENSIONS');
  });
});
