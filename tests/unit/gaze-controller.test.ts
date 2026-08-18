import { describe, expect, test } from 'vitest';
import { GazeController } from '../../src/character/gaze-controller';

describe('GazeController', () => {
  test('clamps an extreme pointer target into the supported gaze range', () => {
    const gaze = new GazeController();

    expect(gaze.update({ x: -100, y: 100 }, 10_000)).toEqual({ x: -1, y: 1 });
  });

  test('moves less than 25 percent of the remaining distance in 16 ms', () => {
    const gaze = new GazeController();

    const next = gaze.update({ x: 1, y: 1 }, 16);

    expect(next.x).toBeGreaterThan(0);
    expect(next.x).toBeLessThan(0.25);
    expect(next.y).toBeGreaterThan(0);
    expect(next.y).toBeLessThan(0.25);
  });

  test('does not change the gaze for NaN or negative elapsed time', () => {
    const gaze = new GazeController();
    const initial = gaze.update({ x: 1, y: 1 }, 16);

    expect(gaze.update({ x: -1, y: -1 }, Number.NaN)).toEqual(initial);
    expect(gaze.update({ x: -1, y: -1 }, -16)).toEqual(initial);
  });

  test.each([Number.NaN, Number.POSITIVE_INFINITY, 0, -1])(
    'uses a safe response time for invalid option %s',
    (responseTimeMs) => {
      const gaze = new GazeController({ responseTimeMs });
      const next = gaze.update({ x: 1, y: 1 }, 16);

      expect(next.x).toBeGreaterThan(0);
      expect(next.x).toBeLessThan(0.25);
      expect(next.y).toBeGreaterThan(0);
      expect(next.y).toBeLessThan(0.25);
    },
  );

  test('does not overshoot and remains stable across frame subdivision', () => {
    const singleFrame = new GazeController().update({ x: 1, y: -1 }, 160);
    const splitFrames = new GazeController();
    let result = { x: 0, y: 0 };

    for (let index = 0; index < 10; index += 1) {
      result = splitFrames.update({ x: 1, y: -1 }, 16);
    }

    expect(singleFrame.x).toBeLessThanOrEqual(1);
    expect(singleFrame.y).toBeGreaterThanOrEqual(-1);
    expect(result.x).toBeCloseTo(singleFrame.x, 12);
    expect(result.y).toBeCloseTo(singleFrame.y, 12);
  });
});
