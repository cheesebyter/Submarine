import {
  PROTOCOL_VERSION,
  type ControlMessage,
} from "@submarine/protocol/types";

const MAX_QUEUED_AUDIO_FRAMES = 50;
const MAX_SOCKET_BUFFER_BYTES = 256 * 1024;

export class BoundedAudioQueue {
  readonly #frames: ArrayBuffer[] = [];

  public constructor(public readonly capacity = MAX_QUEUED_AUDIO_FRAMES) {
    if (!Number.isInteger(capacity) || capacity < 1) {
      throw new Error("Queue capacity must be a positive integer");
    }
  }

  public push(frame: ArrayBuffer): void {
    if (this.#frames.length === this.capacity) {
      this.#frames.shift();
    }
    this.#frames.push(frame);
  }

  public shift(): ArrayBuffer | undefined {
    return this.#frames.shift();
  }

  public clear(): void {
    this.#frames.length = 0;
  }

  public get length(): number {
    return this.#frames.length;
  }
}

export interface CaptureTransportCallbacks {
  onSessionStarted(sessionId: string): void;
  onError(message: string): void;
  onStopped(): void;
}

export class CaptureTransport {
  readonly #queue = new BoundedAudioQueue();
  readonly #requestId = crypto.randomUUID().replaceAll("-", "_");
  #socket: WebSocket | undefined;
  #sessionId: string | undefined;
  #flushTimer: number | undefined;

  public constructor(
    private readonly url: string,
    private readonly callbacks: CaptureTransportCallbacks,
  ) {}

  public async connect(): Promise<void> {
    if (this.#socket !== undefined) {
      throw new Error("Capture transport is already connected");
    }

    const socket = new WebSocket(this.url);
    socket.binaryType = "arraybuffer";
    this.#socket = socket;
    socket.addEventListener("message", (event) => this.#handleMessage(event));
    socket.addEventListener("close", () => {
      this.#cleanup();
      this.callbacks.onStopped();
    });

    await new Promise<void>((resolve, reject) => {
      let opened = false;
      const timeout = window.setTimeout(() => {
        reject(new Error("Local Submarine service did not respond within 3 seconds."));
        socket.close();
      }, 3000);

      socket.addEventListener(
        "open",
        () => {
          opened = true;
          window.clearTimeout(timeout);
          socket.send(
            JSON.stringify({
              type: "hello",
              protocolVersion: PROTOCOL_VERSION,
              clientType: "capture",
              requestId: this.#requestId,
            }),
          );
          socket.send(
            JSON.stringify({
              type: "session.start",
              protocolVersion: PROTOCOL_VERSION,
              requestId: this.#requestId,
              audioFormat: {
                encoding: "pcm_s16le",
                sampleRateHz: 16000,
                channels: 1,
                frameDurationMs: 20,
              },
            }),
          );
          this.#flushTimer = window.setInterval(() => this.#flush(), 20);
          resolve();
        },
        { once: true },
      );
      socket.addEventListener(
        "error",
        () => {
          window.clearTimeout(timeout);
          if (opened) {
            this.callbacks.onError("Connection to the local Submarine service failed.");
          } else {
            reject(new Error("Cannot connect to the local Submarine service."));
          }
        },
      );
    });
  }

  public enqueue(frame: ArrayBuffer): void {
    if (this.#sessionId === undefined) {
      return;
    }
    const socket = this.#socket;
    if (
      socket?.readyState === WebSocket.OPEN &&
      socket.bufferedAmount < MAX_SOCKET_BUFFER_BYTES &&
      this.#queue.length === 0
    ) {
      socket.send(frame);
      return;
    }
    this.#queue.push(frame);
  }

  public stop(reason: "user" | "source-ended" | "client-shutdown" | "error"): void {
    const socket = this.#socket;
    if (socket?.readyState === WebSocket.OPEN && this.#sessionId !== undefined) {
      socket.send(
        JSON.stringify({
          type: "session.stop",
          protocolVersion: PROTOCOL_VERSION,
          sessionId: this.#sessionId,
          reason,
        }),
      );
    }
    window.setTimeout(() => socket?.close(1000, "Capture stopped"), 2000);
  }

  #handleMessage(event: MessageEvent<unknown>): void {
    if (typeof event.data !== "string") {
      return;
    }
    let message: ControlMessage;
    try {
      message = parseServerMessage(event.data);
    } catch {
      this.callbacks.onError("The local service returned an invalid protocol message.");
      return;
    }

    if (message.type === "session.started") {
      this.#sessionId = message.sessionId;
      this.callbacks.onSessionStarted(message.sessionId);
    } else if (message.type === "session.stopped") {
      this.#socket?.close(1000, "Session stopped");
    } else if (message.type === "error") {
      this.callbacks.onError(message.message);
    }
  }

  #flush(): void {
    const socket = this.#socket;
    if (socket?.readyState !== WebSocket.OPEN || socket.bufferedAmount >= MAX_SOCKET_BUFFER_BYTES) {
      return;
    }
    const frame = this.#queue.shift();
    if (frame !== undefined) {
      socket.send(frame);
    }
  }

  #cleanup(): void {
    if (this.#flushTimer !== undefined) {
      window.clearInterval(this.#flushTimer);
    }
    this.#queue.clear();
    this.#socket = undefined;
    this.#sessionId = undefined;
    this.#flushTimer = undefined;
  }
}

export function parseServerMessage(raw: string): ControlMessage {
  const value: unknown = JSON.parse(raw);
  if (
    typeof value !== "object" ||
    value === null ||
    !("type" in value) ||
    !("protocolVersion" in value) ||
    value.protocolVersion !== PROTOCOL_VERSION
  ) {
    throw new Error("Invalid protocol response");
  }

  if (
    value.type === "session.started" &&
    "requestId" in value &&
    typeof value.requestId === "string" &&
    "sessionId" in value &&
    typeof value.sessionId === "string"
  ) {
    return value as ControlMessage;
  }
  if (
    value.type === "session.stopped" &&
    "sessionId" in value &&
    typeof value.sessionId === "string" &&
    "reason" in value &&
    typeof value.reason === "string"
  ) {
    return value as ControlMessage;
  }
  if (
    (value.type === "transcript.provisional" || value.type === "transcript.final") &&
    "sessionId" in value &&
    typeof value.sessionId === "string" &&
    "sequence" in value &&
    typeof value.sequence === "number" &&
    "text" in value &&
    typeof value.text === "string" &&
    "sourceLanguage" in value &&
    (typeof value.sourceLanguage === "string" || value.sourceLanguage === null)
  ) {
    // Subtitle rendering belongs to the desktop overlay. The capture client only
    // validates these server events so a normal transcript cannot end capture.
    return value as ControlMessage;
  }
  if (
    value.type === "error" &&
    "code" in value &&
    typeof value.code === "string" &&
    "message" in value &&
    typeof value.message === "string" &&
    "recoverable" in value &&
    typeof value.recoverable === "boolean"
  ) {
    return value as ControlMessage;
  }
  throw new Error("Unexpected protocol response");
}
