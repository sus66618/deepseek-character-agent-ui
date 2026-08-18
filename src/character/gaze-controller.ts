export interface GazeTarget {
  x: number;
  y: number;
}

export interface GazeControllerOptions {
  responseTimeMs?: number;
}

export class GazeController {
  private readonly responseTimeMs: number;
  private current: GazeTarget = { x: 0, y: 0 };

  constructor(options: GazeControllerOptions = {}) {
    this.responseTimeMs = options.responseTimeMs ?? 150;
  }

  update(target: GazeTarget, deltaMs: number): GazeTarget {
    const bounded = { x: clamp(target.x), y: clamp(target.y) };
    const elapsed = Math.max(0, deltaMs);
    const progress = 1 - Math.exp(-elapsed / this.responseTimeMs);

    this.current = {
      x: this.current.x + (bounded.x - this.current.x) * progress,
      y: this.current.y + (bounded.y - this.current.y) * progress,
    };

    return { ...this.current };
  }
}

const clamp = (value: number): number => Math.min(1, Math.max(-1, value));
