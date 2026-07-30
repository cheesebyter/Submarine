import {
  AUDIO_HEADER_BYTES,
  AUDIO_PAYLOAD_BYTES,
  PROTOCOL_VERSION,
} from "@submarine/protocol/types";

const TARGET_SAMPLE_RATE = 16_000;
const SAMPLES_PER_FRAME = AUDIO_PAYLOAD_BYTES / 2;
const AUDIO_MAGIC = new Uint8Array([0x53, 0x55, 0x42, 0x41]);

export class PcmFramePipeline {
  readonly #ratio: number;
  #samples: number[] = [];
  #sourcePosition = 0;
  #pcm: number[] = [];

  public constructor(sourceSampleRate: number) {
    if (!Number.isFinite(sourceSampleRate) || sourceSampleRate < TARGET_SAMPLE_RATE) {
      throw new Error("Source sample rate must be at least 16 kHz");
    }
    this.#ratio = sourceSampleRate / TARGET_SAMPLE_RATE;
  }

  public push(input: Float32Array): Int16Array[] {
    for (const sample of input) {
      this.#samples.push(sample);
    }

    while (this.#sourcePosition + 1 < this.#samples.length) {
      const lowerIndex = Math.floor(this.#sourcePosition);
      const fraction = this.#sourcePosition - lowerIndex;
      const lower = this.#samples[lowerIndex];
      const upper = this.#samples[lowerIndex + 1];
      if (lower === undefined || upper === undefined) {
        break;
      }
      const interpolated = lower + (upper - lower) * fraction;
      this.#pcm.push(floatToPcm16(interpolated));
      this.#sourcePosition += this.#ratio;
    }

    const consumed = Math.floor(this.#sourcePosition);
    if (consumed > 0) {
      this.#samples.splice(0, consumed);
      this.#sourcePosition -= consumed;
    }

    const frames: Int16Array[] = [];
    while (this.#pcm.length >= SAMPLES_PER_FRAME) {
      frames.push(Int16Array.from(this.#pcm.splice(0, SAMPLES_PER_FRAME)));
    }
    return frames;
  }

  public reset(): void {
    this.#samples = [];
    this.#pcm = [];
    this.#sourcePosition = 0;
  }
}

export function encodeAudioFrame(
  pcm: Int16Array,
  sequence: number,
  timestampMs: bigint,
): ArrayBuffer {
  if (pcm.length !== SAMPLES_PER_FRAME) {
    throw new Error(`PCM frame must contain ${SAMPLES_PER_FRAME} samples`);
  }

  const buffer = new ArrayBuffer(AUDIO_HEADER_BYTES + AUDIO_PAYLOAD_BYTES);
  const bytes = new Uint8Array(buffer);
  bytes.set(AUDIO_MAGIC);
  const view = new DataView(buffer);
  view.setUint8(4, PROTOCOL_VERSION);
  view.setUint8(5, 0);
  view.setUint16(6, AUDIO_HEADER_BYTES, true);
  view.setUint32(8, sequence, true);
  view.setBigUint64(12, timestampMs, true);
  for (let index = 0; index < pcm.length; index += 1) {
    view.setInt16(AUDIO_HEADER_BYTES + index * 2, pcm[index] ?? 0, true);
  }
  return buffer;
}

function floatToPcm16(sample: number): number {
  const clamped = Math.max(-1, Math.min(1, sample));
  return clamped < 0 ? Math.round(clamped * 0x8000) : Math.round(clamped * 0x7fff);
}
