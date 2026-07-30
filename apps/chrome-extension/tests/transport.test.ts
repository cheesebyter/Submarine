import { describe, expect, it } from "vitest";

import { BoundedAudioQueue, parseServerMessage } from "../src/transport.js";

describe("bounded audio queue", () => {
  it("drops the oldest frame when at capacity", () => {
    const queue = new BoundedAudioQueue(2);
    const first = new ArrayBuffer(1);
    const second = new ArrayBuffer(2);
    const third = new ArrayBuffer(3);

    queue.push(first);
    queue.push(second);
    queue.push(third);

    expect(queue.length).toBe(2);
    expect(queue.shift()).toBe(second);
    expect(queue.shift()).toBe(third);
  });

  it("clears queued audio on disconnect", () => {
    const queue = new BoundedAudioQueue(2);
    queue.push(new ArrayBuffer(1));
    queue.clear();
    expect(queue.length).toBe(0);
  });
});

describe("server message parser", () => {
  it.each(["transcript.provisional", "transcript.final"])(
    "accepts %s events without treating them as transport errors",
    (type) => {
      expect(
        parseServerMessage(
          JSON.stringify({
            type,
            protocolVersion: 1,
            sessionId: "session-1",
            sequence: 4,
            text: "How are you?",
            sourceLanguage: "es",
          }),
        ),
      ).toMatchObject({ type, text: "How are you?" });
    },
  );
});
