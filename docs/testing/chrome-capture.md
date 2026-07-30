# Manual Chrome capture verification

Run this checklist after changes to tab capture, offscreen audio or the extension
manifest.

## Preparation

```powershell
.\scripts\check.ps1
.\scripts\dev-backend.ps1
```

In Chrome, open `chrome://extensions`, enable Developer mode, select **Load
unpacked**, and choose `apps/chrome-extension/dist`. Reload the unpacked
extension after every rebuild.

## Happy path

1. Open a normal HTTPS tab containing continuous speech or music and start playback.
2. Open Submarine and press **Start translation**.
3. Confirm the popup reports active capture and the extension badge reads `ON`.
4. Confirm the source tab remains audible at the same expected output device.
5. Wait at least 10 seconds and confirm the popup remains responsive.
6. Press **Stop translation**.
7. Confirm the badge clears, capture ends and normal tab playback continues.

## Source termination

1. Start capture again.
2. Close the captured tab.
3. Confirm capture stops and a subsequent capture can start on another tab.

## Failure behavior

1. Stop the backend.
2. Press **Start translation**.
3. Confirm an actionable local-service error appears within approximately three
   seconds and memory use does not continue growing.
4. Restart the backend and confirm capture can start without reloading Chrome.

## Privacy inspection

In Chrome's extension service-worker and offscreen-document inspectors, confirm
that the only network connection is `ws://127.0.0.1:8765/ws/capture`. No captured
content should appear in extension or backend logs.

Record Chrome version, Windows version and the result in the active ticket.
