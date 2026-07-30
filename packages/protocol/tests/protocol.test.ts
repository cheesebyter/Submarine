import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  InvalidSessionTransitionError,
  ProtocolValidationError,
  AUDIO_HEADER_BYTES,
  AUDIO_PAYLOAD_BYTES,
  decodeAudioFrame,
  transitionSession,
  validateControlMessage,
  type SessionState,
} from "../src/index.js";

interface MessageFixture {
  name: string;
  valid: boolean;
  errorCode?: string;
  message: unknown;
}

interface TransitionFixture {
  state: SessionState;
  messageType: string;
  valid: boolean;
  next?: SessionState;
}

function readFixtures<T>(name: string): T {
  const url = new URL(`../fixtures/${name}`, import.meta.url);
  return JSON.parse(readFileSync(url, "utf8")) as T;
}

describe("shared control message fixtures", () => {
  const fixtures = readFixtures<MessageFixture[]>("control-messages.json");

  for (const fixture of fixtures) {
    it(fixture.name, () => {
      const raw = JSON.stringify(fixture.message);
      if (fixture.valid) {
        expect(validateControlMessage(raw)).toEqual(fixture.message);
      } else {
        try {
          validateControlMessage(raw);
          throw new Error("Expected protocol validation to fail");
        } catch (error) {
          expect(error).toBeInstanceOf(ProtocolValidationError);
          expect((error as ProtocolValidationError).code).toBe(fixture.errorCode);
        }
      }
    });
  }
});

describe("shared state transition fixtures", () => {
  const fixtures = readFixtures<TransitionFixture[]>("state-transitions.json");

  for (const fixture of fixtures) {
    it(`${fixture.state} + ${fixture.messageType}`, () => {
      if (fixture.valid) {
        expect(transitionSession(fixture.state, fixture.messageType)).toBe(fixture.next);
      } else {
        expect(() => transitionSession(fixture.state, fixture.messageType)).toThrow(
          InvalidSessionTransitionError,
        );
      }
    });
  }
});

it("rejects oversized control messages", () => {
  expect(() => validateControlMessage(" ".repeat(16 * 1024 + 1))).toThrowError(
    expect.objectContaining({ code: "message_too_large" }),
  );
});

function audioFrame(version = 1, magic = "SUBA"): ArrayBuffer {
  const buffer = new ArrayBuffer(AUDIO_HEADER_BYTES + AUDIO_PAYLOAD_BYTES);
  const bytes = new Uint8Array(buffer);
  bytes.set(new TextEncoder().encode(magic), 0);
  const view = new DataView(buffer);
  view.setUint8(4, version);
  view.setUint8(5, 0);
  view.setUint16(6, AUDIO_HEADER_BYTES, true);
  view.setUint32(8, 42, true);
  view.setBigUint64(12, 1234n, true);
  return buffer;
}

it("decodes a valid audio frame", () => {
  const frame = decodeAudioFrame(audioFrame());
  expect(frame.sequence).toBe(42);
  expect(frame.timestampMs).toBe(1234n);
  expect(frame.payload.byteLength).toBe(AUDIO_PAYLOAD_BYTES);
});

it.each([
  ["invalid magic", audioFrame(1, "NOPE"), "invalid_message"],
  ["unsupported version", audioFrame(2), "unsupported_version"],
  ["too short", audioFrame().slice(0, -1), "invalid_message"],
  ["too large", new ArrayBuffer(AUDIO_HEADER_BYTES + AUDIO_PAYLOAD_BYTES + 1), "message_too_large"],
])("rejects %s audio frames", (_name, raw, code) => {
  try {
    decodeAudioFrame(raw as ArrayBuffer);
    throw new Error("Expected audio validation to fail");
  } catch (error) {
    expect(error).toBeInstanceOf(ProtocolValidationError);
    expect((error as ProtocolValidationError).code).toBe(code);
  }
});
