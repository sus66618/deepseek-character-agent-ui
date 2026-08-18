export interface GazeTarget {
  x: number;
  y: number;
}

export interface GazeControllerOptions {
  responseTimeMs?: number;
}

const DEFAULT_RESPONSE_TIME_MS = 150;

export class GazeController {
  private readonly responseTimeMs: number;
  private current: GazeTarget = { x: 0, y: 0 };

  constructor(options: GazeControllerOptions = {}) {
    this.responseTimeMs = isPositiveFinite(options.responseTimeMs)
      ? options.responseTimeMs
      : DEFAULT_RESPONSE_TIME_MS;
  }

  update(target: GazeTarget, deltaMs: number): GazeTarget {
    const bounded = { x: clamp(target.x), y: clamp(target.y) };
    const elapsed = isPositiveFinite(deltaMs) ? deltaMs : 0;
    const progress = 1 - Math.exp(-elapsed / this.responseTimeMs);

    this.current = {
      x: this.current.x + (bounded.x - this.current.x) * progress,
      y: this.current.y + (bounded.y - this.current.y) * progress,
    };

    return { ...this.current };
  }
}

const clamp = (value: number): number => isFiniteNumber(value)
  ? Math.min(1, Math.max(-1, value))
  : 0;

const isFiniteNumber = (value: number | undefined): value is number => Number.isFinite(value);

const isPositiveFinite = (value: number | undefined): value is number =>
  isFiniteNumber(value) && value > 0;
