import type { MotionCommand } from './types';

export class MotionCoordinator {
  resolve(commands: readonly MotionCommand[]): readonly MotionCommand[] {
    const selected = new Map<MotionCommand['channel'], MotionCommand>();

    for (const command of commands) {
      const current = selected.get(command.channel);
      if (!current || command.priority >= current.priority) {
        selected.set(command.channel, command);
      }
    }

    return [...selected.values()];
  }
}
