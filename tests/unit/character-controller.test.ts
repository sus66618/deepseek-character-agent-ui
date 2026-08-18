import { describe, expect, test } from 'vitest';
import { CharacterController } from '../../src/character/character-controller';

describe('CharacterController', () => {
  test('real input wakes a sleeping character', () => {
    const controller = new CharacterController(0);
    controller.dispatch({ type: 'idle-timeout', at: 180_000 });
    expect(controller.getSnapshot().state).toBe('sleeping');

    controller.dispatch({ type: 'real-input', at: 180_100 });

    expect(controller.getSnapshot()).toMatchObject({
      state: 'waking',
      previousState: 'sleeping',
      enteredAt: 180_100,
    });
  });

  test('thinking interrupts an idle motion', () => {
    const controller = new CharacterController(0);

    controller.dispatch({ type: 'agent-state', state: 'thinking', at: 50 });

    expect(controller.getSnapshot().state).toBe('thinking');
  });

  test('motion completion transitions waking character to user input', () => {
    const controller = new CharacterController(0);
    controller.dispatch({ type: 'idle-timeout', at: 180_000 });
    controller.dispatch({ type: 'real-input', at: 180_100 });

    controller.dispatch({ type: 'motion-finished', motionId: 'wake-up', at: 180_600 });

    expect(controller.getSnapshot()).toMatchObject({
      state: 'user_input',
      previousState: 'waking',
      enteredAt: 180_600,
    });
  });

  test('agent state replaces a cosmetic sleeping state immediately', () => {
    const controller = new CharacterController(0);
    controller.dispatch({ type: 'idle-timeout', at: 180_000 });

    controller.dispatch({ type: 'agent-state', state: 'streaming', at: 180_050 });

    expect(controller.getSnapshot()).toMatchObject({
      state: 'streaming',
      previousState: 'sleeping',
      enteredAt: 180_050,
    });
  });

  test('ignores events older than the current state entry', () => {
    const controller = new CharacterController(0);
    controller.dispatch({ type: 'agent-state', state: 'thinking', at: 100 });

    const snapshot = controller.dispatch({ type: 'idle-timeout', at: 99 });

    expect(snapshot).toMatchObject({
      state: 'thinking',
      previousState: 'idle',
      enteredAt: 100,
    });
  });
});
