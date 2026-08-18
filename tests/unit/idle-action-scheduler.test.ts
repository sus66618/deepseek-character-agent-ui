import { describe, expect, test } from 'vitest';
import { IdleActionScheduler } from '../../src/character/idle-action-scheduler';
import { MotionCoordinator } from '../../src/character/motion-coordinator';
import type { CharacterSnapshot, MotionCommand } from '../../src/character/types';

const snapshot = (state: CharacterSnapshot['state'] = 'idle'): CharacterSnapshot => ({
  state,
  previousState: null,
  enteredAt: 0,
  motionLevel: 'full',
});

describe('IdleActionScheduler', () => {
  test('schedules sleep at 150,000 ms when random is zero', () => {
    const scheduler = new IdleActionScheduler(() => snapshot(), {
      random: () => 0,
      clock: () => 150_000,
    });

    expect(scheduler.tick()).toMatchObject([{ name: 'sleep' }]);
  });

  test('schedules sleep at 210,000 ms when random is one', () => {
    const scheduler = new IdleActionScheduler(() => snapshot(), { random: () => 1 });

    expect(scheduler.tick(209_999)).not.toContainEqual(expect.objectContaining({ name: 'sleep' }));
    expect(scheduler.tick(210_000)).toMatchObject([{ name: 'sleep' }]);
  });

  test('schedules a midpoint random sleep delay inside the approved interval', () => {
    const scheduler = new IdleActionScheduler(() => snapshot(), { random: () => 0.5 });

    expect(scheduler.tick(179_999)).not.toContainEqual(expect.objectContaining({ name: 'sleep' }));
    expect(scheduler.tick(180_000)).toMatchObject([{ name: 'sleep' }]);
  });

  test('never repeats a special action immediately', () => {
    const scheduler = new IdleActionScheduler(() => snapshot(), { random: () => 0 });

    const first = scheduler.tick(15_000)[0];
    const second = scheduler.tick(30_000)[0];

    expect(first?.name).toBe('blink');
    expect(second?.name).not.toBe(first?.name);
  });

  test.each([
    'user_input', 'thinking', 'streaming', 'tool_running', 'waiting_user',
    'success', 'error', 'sleeping', 'waking',
] as const)('clears idle actions immediately in %s', (state) => {
    let current = snapshot();
    const scheduler = new IdleActionScheduler(() => current, { random: () => 0 });
    expect(scheduler.tick(15_000)).toHaveLength(1);

    current = snapshot(state);

    expect(scheduler.tick(15_001)).toEqual([]);
  });

  test('does not turn pointer activity into a wake command', () => {
    const scheduler = new IdleActionScheduler(() => snapshot('sleeping'));

    expect(scheduler.tick(200_000)).toEqual([]);
  });

  test('honors the existing off motion-level contract', () => {
    const current = { ...snapshot(), motionLevel: 'off' as const };
    const scheduler = new IdleActionScheduler(() => current, { random: () => 0 });

    expect(scheduler.tick(15_000)).toEqual([]);
  });

  test('emits sleep on schedule even when visual motion is off', () => {
    const current = { ...snapshot(), motionLevel: 'off' as const };
    const scheduler = new IdleActionScheduler(() => current, { random: () => 0 });

    expect(scheduler.tick(150_000)).toMatchObject([{ name: 'sleep' }]);
  });

  test('uses action weights when choosing an idle action', () => {
    const values = [0, 0, 0.99, 0, 0];
    const scheduler = new IdleActionScheduler(() => snapshot(), {
      random: () => values.shift() ?? 0,
    });

    expect(scheduler.tick(5_000)).toMatchObject([{ name: 'tail-sway' }]);
    expect(scheduler.tick(10_000)).toMatchObject([{ name: 'blink' }]);
  });

  test('applies each action cooldown independently', () => {
    const values = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    const scheduler = new IdleActionScheduler(() => snapshot(), {
      random: () => values.shift() ?? 0,
    });

    expect(scheduler.tick(5_000)).toMatchObject([{ name: 'blink' }]);
    expect(scheduler.tick(10_000)).toMatchObject([{ name: 'look-away' }]);
    expect(scheduler.tick(15_000)).toMatchObject([{ name: 'adjust-stance' }]);
    expect(scheduler.tick(25_000)).toMatchObject([{ name: 'blink' }]);
  });
});

const command = (
  id: string,
  channel: MotionCommand['channel'],
  priority: number,
): MotionCommand => ({ id, channel, name: id, priority, durationMs: 100 });

describe('MotionCoordinator', () => {
  test('keeps the highest-priority command on a channel', () => {
    const result = new MotionCoordinator().resolve([
      command('body-low', 'body', 1),
      command('body-high', 'body', 2),
    ]);

    expect(result).toEqual([command('body-high', 'body', 2)]);
  });

  test('keeps the newest command when priorities tie', () => {
    const result = new MotionCoordinator().resolve([
      command('old', 'face', 2),
      command('new', 'face', 2),
    ]);

    expect(result).toEqual([command('new', 'face', 2)]);
  });

  test('allows commands on independent channels together', () => {
    const commands: MotionCommand[] = [
      command('body', 'body', 1), command('face', 'face', 1),
      command('gaze', 'gaze', 1), command('prop', 'prop', 1),
      command('camera', 'camera', 1),
    ];

    expect(new MotionCoordinator().resolve(commands)).toEqual(commands);
  });
});
