import type { SessionState } from "./types.js";

const transitions: Readonly<Record<SessionState, Readonly<Partial<Record<string, SessionState>>>>> = {
  idle: { "session.start": "starting" },
  starting: { "session.started": "streaming" },
  streaming: { "session.stop": "stopping" },
  stopping: { "session.stopped": "stopped" },
  stopped: { "session.start": "starting" },
};

export class InvalidSessionTransitionError extends Error {}

export function transitionSession(state: SessionState, messageType: string): SessionState {
  if (messageType === "error" || messageType.startsWith("health.")) {
    return state;
  }
  const next = transitions[state][messageType];
  if (next === undefined) {
    throw new InvalidSessionTransitionError(
      `Message ${messageType} is invalid while session is ${state}`,
    );
  }
  return next;
}
