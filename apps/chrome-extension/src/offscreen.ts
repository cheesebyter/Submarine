import { PcmFramePipeline, encodeAudioFrame } from "./audio.js";
import {
  IDLE_STATUS,
  type CaptureStatus,
  type ExtensionMessage,
  type MessageResponse,
  type StopReason,
} from "./messages.js";
import { CaptureTransport } from "./transport.js";

const BACKEND_URL = "ws://127.0.0.1:8765/ws/capture";

let status: CaptureStatus = IDLE_STATUS;
let mediaStream: MediaStream | undefined;
let audioContext: AudioContext | undefined;
let processor: AudioWorkletNode | undefined;
let transport: CaptureTransport | undefined;
let sequence = 0;
let sessionStartedAt = 0;
let stopping = false;

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    _sender,
    sendResponse: (response: MessageResponse) => void,
  ) => {
    if (message.target !== "offscreen") {
      return false;
    }
    void handleMessage(message).then(sendResponse);
    return true;
  },
);

async function handleMessage(
  message: Extract<ExtensionMessage, { target: "offscreen" }>,
): Promise<MessageResponse> {
  if (message.type === "capture.status") {
    return { ok: status.phase !== "error", status };
  }
  if (message.type === "capture.stop") {
    await stopCapture(message.reason);
    return { ok: true, status };
  }
  if (message.type === "capture.start") {
    try {
      await startCapture(message.streamId, message.tabId);
      return { ok: true, status };
    } catch (error) {
      await stopCapture("error");
      await setStatus({
        phase: "error",
        message:
          error instanceof Error
            ? error.message
            : "The selected tab could not be captured.",
      });
      return { ok: false, status };
    }
  }
  return { ok: false, status };
}

async function startCapture(streamId: string, tabId: number): Promise<void> {
  if (mediaStream !== undefined) {
    throw new Error("A Chrome tab is already being captured.");
  }
  stopping = false;
  sequence = 0;
  await setStatus({
    phase: "connecting",
    message: "Connecting to the local translation service…",
    tabId,
  });

  const newTransport = new CaptureTransport(BACKEND_URL, {
    onSessionStarted: () => {
      sessionStartedAt = performance.now();
      void setStatus({
        phase: "capturing",
        message: "Capturing and translating this tab locally.",
        tabId,
      });
    },
    onError: (message) => {
      void setStatus({ phase: "error", message, tabId });
      void stopCapture("error");
    },
    onStopped: () => {
      if (!stopping) {
        void setStatus({
          phase: "error",
          message: "The local translation service closed the connection.",
          tabId,
        }).then(() => stopCapture("error"));
      }
    },
  });
  await newTransport.connect();
  transport = newTransport;

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: streamId,
      },
    } as MediaTrackConstraints,
    video: false,
  });
  mediaStream = stream;

  for (const track of stream.getAudioTracks()) {
    track.addEventListener("ended", () => void stopCapture("source-ended"), { once: true });
  }

  const context = new AudioContext();
  audioContext = context;
  await context.resume();
  const source = context.createMediaStreamSource(stream);

  // Reconnect captured audio to the default destination so the user keeps hearing the tab.
  source.connect(context.destination);

  const resampler = new PcmFramePipeline(context.sampleRate);
  await context.audioWorklet.addModule("audio-worklet.js");
  const worklet = new AudioWorkletNode(context, "submarine-capture", {
    numberOfInputs: 1,
    numberOfOutputs: 1,
    outputChannelCount: [1],
  });
  processor = worklet;
  worklet.port.onmessage = (event: MessageEvent<Float32Array>) => {
    const input = event.data;
    for (const pcm of resampler.push(input)) {
      const elapsed = BigInt(Math.max(0, Math.round(performance.now() - sessionStartedAt)));
      newTransport.enqueue(encodeAudioFrame(pcm, sequence, elapsed));
      sequence = (sequence + 1) >>> 0;
    }
  };
  source.connect(worklet);

  // The worklet must be connected to run; zero gain prevents duplicate playback.
  const silentGain = context.createGain();
  silentGain.gain.value = 0;
  worklet.connect(silentGain);
  silentGain.connect(context.destination);
}

async function stopCapture(reason: StopReason): Promise<void> {
  if (stopping) {
    return;
  }
  stopping = true;
  if (status.phase !== "error") {
    await setStatus({ phase: "stopping", message: "Stopping capture…" });
  }
  transport?.stop(reason);
  processor?.disconnect();
  processor = undefined;
  for (const track of mediaStream?.getTracks() ?? []) {
    track.stop();
  }
  mediaStream = undefined;
  if (audioContext !== undefined) {
    await audioContext.close();
    audioContext = undefined;
  }
  transport = undefined;
  sequence = 0;
  if (status.phase !== "error") {
    await setStatus(IDLE_STATUS);
  }
  stopping = false;
}

async function setStatus(next: CaptureStatus): Promise<void> {
  status = next;
  await chrome.runtime.sendMessage({
    target: "service-worker",
    type: "capture.status.changed",
    status,
  } satisfies ExtensionMessage);
}
