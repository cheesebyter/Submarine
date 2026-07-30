# Desktop overlay technology spike

## Decision

Use Python Tkinter for the SUB-005 Windows MVP.

## Why

- Tk 8.6 ships with the pinned Python 3.12 runtime, so the overlay adds no web
  runtime or Chromium process.
- Windows supports resizable and always-on-top Tk windows directly.
- Tk remains on its UI thread while an isolated asyncio/thread client performs
  WebSocket I/O, so model inference cannot block painting or controls.
- The view model is independent of Tk and can be unit tested.

## Trade-offs

Tkinter provides less sophisticated typography and multi-monitor window control
than WinUI 3 or Qt. Those are not MVP requirements. The overlay boundary is the
versioned localhost WebSocket, so a later native UI can replace Tkinter without
changing capture or inference.

## Privacy and lifecycle

The backend fan-out hub does not retain transcript text. The overlay holds at
most six final sentences plus one provisional sentence in process memory. It
does not write transcripts, logs or settings. Closing the overlay closes its
subscription; stopping capture requests a clean end to the active browser
session.
