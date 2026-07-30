import { decodeAudioFrame } from "@submarine/protocol";
import { describe, expect, it } from "vitest";

import { PcmFramePipeline, encodeAudioFrame } from "../src/audio.js";

describe("PCM frame pipeline", () => {
  it("resamples 48 kHz mono input into complete 16 kHz protocol frames", () => {
    const pipeline = new PcmFramePipeline(48_000);
    const input = Float32Array.from({ length: 960 }, (_, index) =>
      Math.sin((2 * Math.PI * 440 * index) / 48_000),
    );

    const frames = pipeline.push(input);

    expect(frames).toHaveLength(1);
    expect(frames[0]).toHaveLength(320);
    expect(frames[0]?.some((sample) => sample !== 0)).toBe(true);
  });

  it("does not emit partial frames", () => {
    const pipeline = new PcmFramePipeline(48_000);
    expect(pipeline.push(new Float32Array(400))).toEqual([]);
  });
});

it("encodes PCM in the shared binary protocol format", () => {
  const pcm = new Int16Array(320);
  pcm[0] = -32_768;
  pcm[1] = 32_767;

  const decoded = decodeAudioFrame(encodeAudioFrame(pcm, 9, 123n));

  expect(decoded.sequence).toBe(9);
  expect(decoded.timestampMs).toBe(123n);
  const payload = new DataView(decoded.payload.buffer);
  expect(payload.getInt16(0, true)).toBe(-32_768);
  expect(payload.getInt16(2, true)).toBe(32_767);
});
