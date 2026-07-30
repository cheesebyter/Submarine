export type CapturePhase =
  | "idle"
  | "connecting"
  | "capturing"
  | "stopping"
  | "error";

export interface CaptureStatus {
  phase: CapturePhase;
  message: string;
  tabId?: number;
}

export type ExtensionMessage =
  | { target: "service-worker"; type: "capture.start"; tabId: number }
  | { target: "service-worker"; type: "capture.stop" }
  | { target: "service-worker"; type: "capture.status" }
  | {
      target: "offscreen";
      type: "capture.start";
      streamId: string;
      tabId: number;
    }
  | { target: "offscreen"; type: "capture.stop"; reason: StopReason }
  | { target: "offscreen"; type: "capture.status" }
  | { target: "service-worker"; type: "capture.status.changed"; status: CaptureStatus };

export type StopReason = "user" | "source-ended" | "client-shutdown" | "error";

export interface MessageResponse {
  ok: boolean;
  status: CaptureStatus;
}

export const IDLE_STATUS: CaptureStatus = {
  phase: "idle",
  message: "Ready to capture the active tab.",
};
