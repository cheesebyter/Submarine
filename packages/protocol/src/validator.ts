import Ajv2020, { type ErrorObject } from "ajv/dist/2020.js";

import schema from "./control-message.schema.json" with { type: "json" };
import {
  AUDIO_HEADER_BYTES,
  AUDIO_PAYLOAD_BYTES,
  MAX_AUDIO_MESSAGE_BYTES,
  MAX_CONTROL_MESSAGE_BYTES,
  PROTOCOL_VERSION,
  type AudioFrame,
  type ControlMessage,
} from "./types.js";

const AUDIO_MAGIC = new Uint8Array([0x53, 0x55, 0x42, 0x41]);
const ajv = new Ajv2020({ allErrors: true, strict: true });
const validateSchema = ajv.compile<ControlMessage>(schema);
const encoder = new TextEncoder();

export class ProtocolValidationError extends Error {
  public constructor(
    message: string,
    public readonly code:
      | "unsupported_version"
      | "invalid_message"
      | "message_too_large",
    public readonly details: readonly ErrorObject[] = [],
  ) {
    super(message);
  }
}

export function validateControlMessage(raw: string): ControlMessage {
  if (encoder.encode(raw).byteLength > MAX_CONTROL_MESSAGE_BYTES) {
    throw new ProtocolValidationError("Control message exceeds 16 KiB", "message_too_large");
  }

  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new ProtocolValidationError("Control message is not valid JSON", "invalid_message");
  }

  if (
    typeof value === "object" &&
    value !== null &&
    "protocolVersion" in value &&
    value.protocolVersion !== PROTOCOL_VERSION
  ) {
    throw new ProtocolValidationError("Unsupported protocol version", "unsupported_version");
  }

  if (!validateSchema(value)) {
    throw new ProtocolValidationError(
      "Control message does not match protocol v1",
      "invalid_message",
      validateSchema.errors ?? [],
    );
  }
  return value;
}

export function decodeAudioFrame(raw: ArrayBuffer): AudioFrame {
  if (raw.byteLength > MAX_AUDIO_MESSAGE_BYTES) {
    throw new ProtocolValidationError("Audio frame is too large", "message_too_large");
  }
  if (raw.byteLength !== MAX_AUDIO_MESSAGE_BYTES) {
    throw new ProtocolValidationError("Audio frame has an invalid length", "invalid_message");
  }

  const bytes = new Uint8Array(raw);
  if (!AUDIO_MAGIC.every((value, index) => bytes[index] === value)) {
    throw new ProtocolValidationError("Audio frame magic is invalid", "invalid_message");
  }

  const view = new DataView(raw);
  if (view.getUint8(4) !== PROTOCOL_VERSION) {
    throw new ProtocolValidationError("Unsupported protocol version", "unsupported_version");
  }
  if (view.getUint8(5) !== 0 || view.getUint16(6, true) !== AUDIO_HEADER_BYTES) {
    throw new ProtocolValidationError("Audio frame header is invalid", "invalid_message");
  }

  return {
    sequence: view.getUint32(8, true),
    timestampMs: view.getBigUint64(12, true),
    payload: bytes.slice(AUDIO_HEADER_BYTES, AUDIO_HEADER_BYTES + AUDIO_PAYLOAD_BYTES),
  };
}
