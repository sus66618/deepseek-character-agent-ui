import type { CharacterSnapshot, MotionCommand } from './types';

const MIN_SLEEP_DELAY_MS = 150_000;
const MAX_SLEEP_DELAY_MS = 210_000;
const SPECIAL_ACTION_INTERVAL_MS = 15_000;

const SPECIAL_ACTIONS = [
  { name: 'blink', channel: 'face', durationMs: 180 },
  { name: 'look-away', channel: 'gaze', durationMs: 1_200 },
  { name: 'adjust-stance', channel: 'body', durationMs: 1_500 },
  { name: 'touch-hair', channel: 'body', durationMs: 1_400 },
  { name: 'tail-sway', channel: 'prop', durationMs: 1_600 },
] as const satisfies readonly Pick<MotionCommand, 'name' | 'channel' | 'durationMs'>[];

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
  private lastSpecialActionIndex = -1;
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

    if (snapshot.motionLevel === 'off') {
      return [];
    }

    if (!this.sleepIssued && now >= this.sleepAt) {
      this.sleepIssued = true;
      return [this.command('sleep', 'body', 100, 800, now)];
    }

    if (!this.sleepIssued && now >= this.nextSpecialActionAt) {
      this.nextSpecialActionAt = now + SPECIAL_ACTION_INTERVAL_MS;
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
    this.nextSpecialActionAt = enteredAt + SPECIAL_ACTION_INTERVAL_MS;
    this.lastSpecialActionIndex = -1;
    this.sleepIssued = false;
  }

  private clearIdleSchedule(): void {
    this.idleEnteredAt = null;
    this.sleepIssued = false;
  }

  private nextSpecialAction(now: number): MotionCommand {
    let index = Math.min(
      SPECIAL_ACTIONS.length - 1,
      Math.floor(Math.min(1, Math.max(0, this.random())) * SPECIAL_ACTIONS.length),
    );

    if (index === this.lastSpecialActionIndex) {
      index = (index + 1) % SPECIAL_ACTIONS.length;
    }

    this.lastSpecialActionIndex = index;
    const action = SPECIAL_ACTIONS[index]!;
    return this.command(action.name, action.channel, 10, action.durationMs, now);
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
