export const PROTOCOL_VERSION = 1 as const;
export const MAX_CONTROL_MESSAGE_BYTES = 16 * 1024;
export const AUDIO_HEADER_BYTES = 20;
export const AUDIO_PAYLOAD_BYTES = 640;
export const MAX_AUDIO_MESSAGE_BYTES = AUDIO_HEADER_BYTES + AUDIO_PAYLOAD_BYTES;

export type ClientType = "capture" | "subtitle";
export type SessionState = "idle" | "starting" | "streaming" | "stopping" | "stopped";

export interface AudioFormat {
  encoding: "pcm_s16le";
  sampleRateHz: 16000;
  channels: 1;
  frameDurationMs: 20;
}

export type ControlMessage =
  | {
      type: "hello";
      protocolVersion: 1;
      clientType: ClientType;
      requestId: string;
    }
  | {
      type: "session.start";
      protocolVersion: 1;
      requestId: string;
      audioFormat: AudioFormat;
    }
  | {
      type: "session.started";
      protocolVersion: 1;
      requestId: string;
      sessionId: string;
    }
  | {
      type: "session.configure";
      protocolVersion: 1;
      sessionId: string;
      sourceLanguage: string | null;
    }
  | {
      type: "session.stop";
      protocolVersion: 1;
      sessionId: string;
      reason: "user" | "source-ended" | "client-shutdown" | "error";
    }
  | {
      type: "session.stopped";
      protocolVersion: 1;
      sessionId: string;
      reason: "user" | "source-ended" | "client-shutdown" | "error" | "server-shutdown";
    }
  | {
      type: "transcript.provisional" | "transcript.final";
      protocolVersion: 1;
      sessionId: string;
      sequence: number;
      text: string;
      sourceLanguage: string | null;
    }
  | {
      type: "audio.level";
      protocolVersion: 1;
      sessionId: string;
      rms: number;
      signal: boolean;
    }
  | {
      type: "health.request";
      protocolVersion: 1;
      requestId: string;
    }
  | {
      type: "health.response";
      protocolVersion: 1;
      requestId: string;
      status: "ready" | "loading" | "degraded";
    }
  | {
      type: "error";
      protocolVersion: 1;
      code:
        | "unsupported_version"
        | "invalid_message"
        | "invalid_state"
        | "message_too_large"
        | "session_not_found"
        | "server_unavailable";
      message: string;
      recoverable: boolean;
      requestId?: string;
      sessionId?: string;
    };

export interface AudioFrame {
  sequence: number;
  timestampMs: bigint;
  payload: Uint8Array;
}
