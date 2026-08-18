export const CHARACTER_STATES = [
  'idle', 'user_input', 'thinking', 'streaming', 'tool_running',
  'waiting_user', 'success', 'error', 'sleeping', 'waking',
] as const;

export type CharacterState = typeof CHARACTER_STATES[number];
export type MotionLevel = 'off' | 'gentle' | 'full';

export type CharacterEvent =
  | { type: 'agent-state'; state: Exclude<CharacterState, 'sleeping' | 'waking'>; at: number }
  | { type: 'real-input'; at: number }
  | { type: 'idle-timeout'; at: number }
  | { type: 'motion-finished'; motionId: string; at: number };

export interface CharacterSnapshot {
  state: CharacterState;
  previousState: CharacterState | null;
  enteredAt: number;
  motionLevel: MotionLevel;
}

export interface MotionCommand {
  id: string;
  channel: 'body' | 'face' | 'gaze' | 'prop' | 'camera';
  name: string;
  priority: number;
  durationMs: number;
}

export interface CharacterRenderer {
  mount(target: HTMLElement): Promise<void>;
  apply(snapshot: CharacterSnapshot, commands: readonly MotionCommand[]): void;
  setGaze(x: number, y: number): void;
  dispose(): void;
}

export const isCharacterState = (value: string): value is CharacterState =>
  (CHARACTER_STATES as readonly string[]).includes(value);
