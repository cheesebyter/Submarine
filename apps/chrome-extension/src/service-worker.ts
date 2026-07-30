import {
  IDLE_STATUS,
  type CaptureStatus,
  type ExtensionMessage,
  type MessageResponse,
} from "./messages.js";

const OFFSCREEN_PATH = "offscreen.html";
let currentStatus: CaptureStatus = IDLE_STATUS;
let creatingOffscreen: Promise<void> | undefined;

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    _sender,
    sendResponse: (response: MessageResponse) => void,
  ) => {
    if (message.target !== "service-worker") {
      return false;
    }
    void handleMessage(message)
      .then(sendResponse)
      .catch(async (error: unknown) => {
        currentStatus = {
          phase: "error",
          message:
            error instanceof Error
              ? error.message
              : "The Submarine extension service encountered an unexpected error.",
        };
        await updateBadge(currentStatus);
        sendResponse({ ok: false, status: currentStatus });
      });
    return true;
  },
);

async function handleMessage(message: ExtensionMessage): Promise<MessageResponse> {
  if (message.type === "capture.status.changed") {
    currentStatus = message.status;
    await updateBadge(message.status);
    return { ok: true, status: currentStatus };
  }
  if (message.type === "capture.status") {
    return { ok: true, status: currentStatus };
  }
  if (message.type === "capture.stop") {
    currentStatus = { phase: "stopping", message: "Stopping capture…" };
    await updateBadge(currentStatus);
    const response = await sendToOffscreen({
      target: "offscreen",
      type: "capture.stop",
      reason: "user",
    });
    return response ?? { ok: true, status: currentStatus };
  }
  if (message.type === "capture.start") {
    try {
      currentStatus = {
        phase: "connecting",
        message: "Connecting to the local translation service…",
        tabId: message.tabId,
      };
      await updateBadge(currentStatus);
      await ensureOffscreenDocument();
      const streamId = await chrome.tabCapture.getMediaStreamId({
        targetTabId: message.tabId,
      });
      const response = await sendToOffscreen({
        target: "offscreen",
        type: "capture.start",
        streamId,
        tabId: message.tabId,
      }, 20);
      if (response === undefined) {
        throw new Error(
          "The offscreen audio processor did not become ready. Reload the extension.",
        );
      }
      return response;
    } catch (error) {
      currentStatus = {
        phase: "error",
        message: error instanceof Error ? error.message : "Chrome could not start tab capture.",
      };
      await updateBadge(currentStatus);
      return { ok: false, status: currentStatus };
    }
  }
  return { ok: false, status: currentStatus };
}

async function ensureOffscreenDocument(): Promise<void> {
  const offscreenUrl = chrome.runtime.getURL(OFFSCREEN_PATH);
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT" as chrome.runtime.ContextType],
    documentUrls: [offscreenUrl],
  });
  if (contexts.length > 0) {
    return;
  }
  creatingOffscreen ??= chrome.offscreen.createDocument({
    url: OFFSCREEN_PATH,
    reasons: [
      "USER_MEDIA" as chrome.offscreen.Reason,
      "AUDIO_PLAYBACK" as chrome.offscreen.Reason,
    ],
    justification: "Capture and locally replay audio from the user-selected Chrome tab.",
  });
  try {
    await creatingOffscreen;
  } finally {
    creatingOffscreen = undefined;
  }
}

async function sendToOffscreen(
  message: ExtensionMessage,
  attempts = 1,
): Promise<MessageResponse | undefined> {
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT" as chrome.runtime.ContextType],
  });
  if (contexts.length === 0) {
    return undefined;
  }

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await chrome.runtime.sendMessage(message);
    } catch (error) {
      // createDocument() can resolve before the offscreen module has registered
      // its message listener. Retry only this known startup race.
      const errorMessage = error instanceof Error ? error.message : String(error);
      if (!errorMessage.includes("Receiving end does not exist")) {
        throw error;
      }
      if (attempt + 1 < attempts) {
        await delay(50);
      }
    }
  }
  return undefined;
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

async function updateBadge(status: CaptureStatus): Promise<void> {
  const active = status.phase === "capturing";
  await chrome.action.setBadgeText({ text: active ? "ON" : "" });
  if (active) {
    await chrome.action.setBadgeBackgroundColor({ color: "#16a5d8" });
  }
}
