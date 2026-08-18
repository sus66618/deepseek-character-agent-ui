import type {
  CharacterEvent,
  CharacterSnapshot,
  MotionLevel,
} from './types';

const reduceSnapshot = (
  snapshot: CharacterSnapshot,
  event: CharacterEvent,
): CharacterSnapshot => {
  if (event.at < snapshot.enteredAt) {
    return snapshot;
  }

  switch (event.type) {
    case 'agent-state':
      return transitionTo(snapshot, event.state, event.at);
    case 'real-input':
      return snapshot.state === 'sleeping'
        ? transitionTo(snapshot, 'waking', event.at)
        : snapshot;
    case 'idle-timeout':
      return snapshot.state === 'idle'
        ? transitionTo(snapshot, 'sleeping', event.at)
        : snapshot;
    case 'motion-finished':
      return snapshot.state === 'waking'
        ? transitionTo(snapshot, 'user_input', event.at)
        : snapshot;
  }
};

const transitionTo = (
  snapshot: CharacterSnapshot,
  state: CharacterSnapshot['state'],
  enteredAt: number,
): CharacterSnapshot => ({
  state,
  previousState: snapshot.state,
  enteredAt,
  motionLevel: snapshot.motionLevel,
});

export class CharacterController {
  private snapshot: CharacterSnapshot;

  constructor(now: number, motionLevel: MotionLevel = 'full') {
    this.snapshot = {
      state: 'idle',
      previousState: null,
      enteredAt: now,
      motionLevel,
    };
  }

  dispatch(event: CharacterEvent): CharacterSnapshot {
    this.snapshot = reduceSnapshot(this.snapshot, event);
    return this.getSnapshot();
  }

  getSnapshot(): CharacterSnapshot {
    return { ...this.snapshot };
  }
}
