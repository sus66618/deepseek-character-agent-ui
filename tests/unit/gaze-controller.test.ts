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
});
