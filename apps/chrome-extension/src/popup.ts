import {
  IDLE_STATUS,
  type CaptureStatus,
  type ExtensionMessage,
  type MessageResponse,
} from "./messages.js";

const statusElement = requireElement<HTMLParagraphElement>("status");
const toggleButton = requireElement<HTMLButtonElement>("toggle");
let status: CaptureStatus = IDLE_STATUS;

toggleButton.addEventListener("click", () => {
  void toggleCapture();
});

void refreshStatus();

async function refreshStatus(): Promise<void> {
  const timeout = window.setTimeout(() => {
    render({
      phase: "error",
      message: "The extension service did not respond. Reload Submarine on chrome://extensions.",
    });
  }, 2000);
  try {
    const response = await chrome.runtime.sendMessage({
      target: "service-worker",
      type: "capture.status",
    } satisfies ExtensionMessage);
    window.clearTimeout(timeout);
    render((response as MessageResponse).status);
  } catch {
    window.clearTimeout(timeout);
    render({
      phase: "error",
      message: "The Submarine extension service is unavailable. Reload the extension.",
    });
  }
}

async function toggleCapture(): Promise<void> {
  toggleButton.disabled = true;
  try {
    let message: ExtensionMessage;
    if (status.phase === "capturing" || status.phase === "connecting") {
      message = { target: "service-worker", type: "capture.stop" };
    } else {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.id === undefined) {
        throw new Error("No active Chrome tab is available.");
      }
      message = {
        target: "service-worker",
        type: "capture.start",
        tabId: tab.id,
      };
    }
    const response = (await chrome.runtime.sendMessage(message)) as MessageResponse;
    render(response.status);
  } catch (error) {
    render({
      phase: "error",
      message: error instanceof Error ? error.message : "Capture could not be changed.",
    });
  }
}

function render(next: CaptureStatus): void {
  status = next;
  statusElement.textContent = next.message;
  statusElement.dataset.kind = next.phase === "error" ? "error" : "normal";
  const active = next.phase === "capturing" || next.phase === "connecting";
  toggleButton.textContent = active ? "Stop translation" : "Start translation";
  toggleButton.dataset.active = String(active);
  toggleButton.disabled = next.phase === "stopping";
}

function requireElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (element === null) {
    throw new Error(`Missing required element: ${id}`);
  }
  return element as T;
}
