import { describe, expect, test } from 'vitest';
import { CHARACTER_STATES, isCharacterState } from '../../src/character/types';

describe('character state contract', () => {
  test('contains every approved state', () => {
    expect(CHARACTER_STATES).toEqual([
      'idle', 'user_input', 'thinking', 'streaming', 'tool_running',
      'waiting_user', 'success', 'error', 'sleeping', 'waking',
    ]);
  });

  test('rejects unknown state names', () => {
    expect(isCharacterState('dancing')).toBe(false);
  });
});
