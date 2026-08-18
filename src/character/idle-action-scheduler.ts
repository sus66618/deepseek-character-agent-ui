import type { CharacterSnapshot, MotionCommand } from './types';

const MIN_SLEEP_DELAY_MS = 150_000;
const MAX_SLEEP_DELAY_MS = 210_000;
const MIN_SPECIAL_ACTION_INTERVAL_MS = 5_000;
const MAX_SPECIAL_ACTION_INTERVAL_MS = 20_000;

const SPECIAL_ACTIONS = [
  { name: 'blink', channel: 'face', durationMs: 180, weight: 6, cooldownMs: 20_000 },
  { name: 'look-away', channel: 'gaze', durationMs: 1_200, weight: 3, cooldownMs: 12_000 },
  { name: 'adjust-stance', channel: 'body', durationMs: 1_500, weight: 2, cooldownMs: 30_000 },
  { name: 'touch-hair', channel: 'body', durationMs: 1_400, weight: 1, cooldownMs: 45_000 },
  { name: 'tail-sway', channel: 'prop', durationMs: 1_600, weight: 4, cooldownMs: 10_000 },
] as const satisfies readonly (Pick<MotionCommand, 'name' | 'channel' | 'durationMs'> & {
  weight: number;
  cooldownMs: number;
})[];

export interface IdleActionSchedulerOptions {
  random?: () => number;
  clock?: () => number;
}

export class IdleActionScheduler {
  private readonly random: () => number;
  private readonly clock: () => number;
  private idleEnteredAt: number | null = null;
  private sleepAt = 0;
  private nextSpecialActionAt = 0;
  private lastSpecialActionName: string | null = null;
  private readonly actionPerformedAt = new Map<string, number>();
  private sleepIssued = false;

  constructor(
    private readonly getSnapshot: () => CharacterSnapshot,
    options: IdleActionSchedulerOptions = {},
  ) {
    this.random = options.random ?? Math.random;
    this.clock = options.clock ?? Date.now;
  }

  tick(now = this.clock()): readonly MotionCommand[] {
    const snapshot = this.getSnapshot();

    if (snapshot.state !== 'idle') {
      this.clearIdleSchedule();
      return [];
    }

    if (this.idleEnteredAt !== snapshot.enteredAt) {
      this.startIdleSchedule(snapshot.enteredAt);
    }

    if (!this.sleepIssued && now >= this.sleepAt) {
      this.sleepIssued = true;
      return [this.command('sleep', 'body', 100, 800, now)];
    }

    if (snapshot.motionLevel === 'off') {
      return [];
    }

    if (!this.sleepIssued && now >= this.nextSpecialActionAt) {
      return [this.nextSpecialAction(now)];
    }

    return [];
  }

  private startIdleSchedule(enteredAt: number): void {
    const randomValue = Math.min(1, Math.max(0, this.random()));
    const sleepDelay = MIN_SLEEP_DELAY_MS
      + randomValue * (MAX_SLEEP_DELAY_MS - MIN_SLEEP_DELAY_MS);

    this.idleEnteredAt = enteredAt;
    this.sleepAt = enteredAt + sleepDelay;
    this.nextSpecialActionAt = enteredAt + this.specialActionInterval();
    this.lastSpecialActionName = null;
    this.actionPerformedAt.clear();
    this.sleepIssued = false;
  }

  private clearIdleSchedule(): void {
    this.idleEnteredAt = null;
    this.sleepIssued = false;
  }

  private nextSpecialAction(now: number): MotionCommand {
    const availableActions = SPECIAL_ACTIONS.filter((action) => this.isAvailable(action, now));
    const action = this.selectWeightedAction(
      availableActions.length > 0 ? availableActions : SPECIAL_ACTIONS,
    );

    this.lastSpecialActionName = action.name;
    this.actionPerformedAt.set(action.name, now);
    this.nextSpecialActionAt = now + this.specialActionInterval();
    return this.command(action.name, action.channel, 10, action.durationMs, now);
  }

  private isAvailable(
    action: typeof SPECIAL_ACTIONS[number],
    now: number,
  ): boolean {
    const lastPerformedAt = this.actionPerformedAt.get(action.name);
    return action.name !== this.lastSpecialActionName
      && (lastPerformedAt === undefined || now - lastPerformedAt >= action.cooldownMs);
  }

  private selectWeightedAction(
    actions: readonly typeof SPECIAL_ACTIONS[number][],
  ): typeof SPECIAL_ACTIONS[number] {
    const totalWeight = actions.reduce((total, action) => total + action.weight, 0);
    let threshold = this.normalizedRandom() * totalWeight;

    for (const action of actions) {
      threshold -= action.weight;
      if (threshold < 0) {
        return action;
      }
    }

    return actions[actions.length - 1]!;
  }

  private specialActionInterval(): number {
    return MIN_SPECIAL_ACTION_INTERVAL_MS + this.normalizedRandom()
      * (MAX_SPECIAL_ACTION_INTERVAL_MS - MIN_SPECIAL_ACTION_INTERVAL_MS);
  }

  private normalizedRandom(): number {
    const value = this.random();
    return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0;
  }

  private command(
    name: string,
    channel: MotionCommand['channel'],
    priority: number,
    durationMs: number,
    now: number,
  ): MotionCommand {
    return { id: `idle-${name}-${now}`, channel, name, priority, durationMs };
  }
}
