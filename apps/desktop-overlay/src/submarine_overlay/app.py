import queue
import tkinter as tk
from tkinter import ttk
from typing import Any

from submarine_overlay.audio_capture import AudioDevice, NativeCaptureAgent, list_wasapi_devices
from submarine_overlay.client import OverlayClient
from submarine_overlay.state import OverlayState


class OverlayApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.state = OverlayState()
        self.events: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=64)
        self.client = OverlayClient(self.events)
        self.capture_agent = NativeCaptureAgent(self.events)
        self.audio_devices: dict[str, AudioDevice] = {}
        self.font_size = 26

        root.title("Submarine — Live English")
        root.geometry("960x300+160+700")
        root.minsize(520, 220)
        root.configure(bg="#071522")
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.status = tk.StringVar(value="Backend: connecting · Capture: waiting · English")
        self.final_text = tk.StringVar(value="Start translation in the Chrome extension.")
        self.provisional_text = tk.StringVar(value="")
        self.error_text = tk.StringVar(value="")
        self.always_on_top = tk.BooleanVar(value=True)
        self.source_choice = tk.StringVar(value="Auto")
        self.audio_level = tk.DoubleVar(value=0)
        self.audio_source = tk.StringVar(value="")
        self._configured_session: str | None = None

        self._build()
        self._load_audio_devices()
        self.client.start()
        root.after(50, self._poll)

    def _build(self) -> None:
        status = tk.Label(
            self.root,
            textvariable=self.status,
            bg="#071522",
            fg="#68d5ff",
            anchor="w",
            padx=20,
            pady=12,
            font=("Segoe UI", 10),
        )
        status.pack(fill="x")

        self.final_label = tk.Label(
            self.root,
            textvariable=self.final_text,
            bg="#071522",
            fg="#f4f8fb",
            justify="left",
            anchor="sw",
            wraplength=900,
            padx=20,
            font=("Segoe UI Semibold", self.font_size),
        )
        self.final_label.pack(fill="both", expand=True)
        self.provisional_label = tk.Label(
            self.root,
            textvariable=self.provisional_text,
            bg="#071522",
            fg="#8ba2b5",
            justify="left",
            anchor="w",
            wraplength=900,
            padx=20,
            font=("Segoe UI", self.font_size - 4, "italic"),
        )
        self.provisional_label.pack(fill="x")
        tk.Label(
            self.root,
            textvariable=self.error_text,
            bg="#071522",
            fg="#ff806e",
            anchor="w",
            padx=20,
            font=("Segoe UI", 10),
        ).pack(fill="x")

        source_controls = ttk.Frame(self.root, padding=(16, 4))
        source_controls.pack(fill="x")
        ttk.Label(source_controls, text="Windows audio source:").pack(side="left")
        self.audio_source_box = ttk.Combobox(
            source_controls,
            textvariable=self.audio_source,
            state="readonly",
            width=54,
        )
        self.audio_source_box.pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(
            source_controls,
            text="Refresh",
            command=self._load_audio_devices,
        ).pack(side="left")
        ttk.Button(
            source_controls,
            text="Start source",
            command=self._start_audio_source,
        ).pack(side="left", padx=(8, 0))

        controls = ttk.Frame(self.root, padding=(16, 4, 16, 8))
        controls.pack(fill="x")
        ttk.Button(controls, text="A-", command=lambda: self._change_font(-2)).pack(side="left")
        ttk.Button(controls, text="A+", command=lambda: self._change_font(2)).pack(side="left")
        ttk.Button(controls, text="Clear", command=self._clear_transcript).pack(
            side="left", padx=(8, 0)
        )
        ttk.Checkbutton(
            controls,
            text="Always on top",
            variable=self.always_on_top,
            command=self._set_topmost,
        ).pack(side="left", padx=12)
        ttk.Label(controls, text="Source:").pack(side="left")
        language = ttk.Combobox(
            controls,
            textvariable=self.source_choice,
            values=("Auto", "Spanish", "German", "French", "Italian", "Portuguese"),
            state="readonly",
            width=11,
        )
        language.pack(side="left", padx=(4, 12))
        language.bind("<<ComboboxSelected>>", lambda _: self._configure_language())
        ttk.Progressbar(
            controls,
            variable=self.audio_level,
            maximum=100,
            length=90,
        ).pack(side="left")
        ttk.Button(controls, text="Stop capture", command=self._stop_capture).pack(side="right")

    def _poll(self) -> None:
        while True:
            try:
                message = self.events.get_nowait()
            except queue.Empty:
                break
            if message.get("type") == "connection.closed":
                self.state.disconnected()
                self.state.error = str(message["message"])
            elif message.get("type") == "capture.local.error":
                self.state.error = str(message["message"])
            else:
                self.state.apply(message)
            self.events.task_done()
        self._render()
        self.root.after(50, self._poll)

    def _render(self) -> None:
        backend = "connected" if self.state.connected else "connecting"
        source = self.state.source_language or "auto"
        self.status.set(
            f"Backend: {backend} · Model: {self.state.model_status} · "
            f"Capture: {self.state.capture_status} · {source} → English"
        )
        self.final_text.set("\n".join(self.state.finals) or "Waiting for speech…")
        self.provisional_text.set(self.state.provisional)
        self.error_text.set(self.state.error or "")
        self.audio_level.set(min(100, self.state.audio_rms * 1000))
        if self.state.has_no_signal():
            self.error_text.set(
                "Kein Audiosignal. Prüfe Tab-Lautstärke; geschützte Netflix-Inhalte "
                "können Chrome-Capture blockieren."
            )
        if self.state.session_id is not None and self.state.session_id != self._configured_session:
            self._configure_language()
        width = max(self.root.winfo_width() - 40, 300)
        self.final_label.configure(wraplength=width)
        self.provisional_label.configure(wraplength=width)

    def _change_font(self, delta: int) -> None:
        self.font_size = min(48, max(16, self.font_size + delta))
        self.final_label.configure(font=("Segoe UI Semibold", self.font_size))
        self.provisional_label.configure(font=("Segoe UI", self.font_size - 4, "italic"))

    def _set_topmost(self) -> None:
        self.root.attributes("-topmost", self.always_on_top.get())

    def _stop_capture(self) -> None:
        if self.capture_agent.running:
            self.capture_agent.stop()
            return
        if self.state.session_id is None:
            self.state.error = "Keine aktive Chrome-Aufnahme vorhanden."
            return
        self.client.request_capture_stop(self.state.session_id)

    def _clear_transcript(self) -> None:
        self.state.clear_transcript()
        self._render()

    def _configure_language(self) -> None:
        if self.state.session_id is None:
            return
        codes = {
            "Auto": None,
            "Spanish": "es",
            "German": "de",
            "French": "fr",
            "Italian": "it",
            "Portuguese": "pt",
        }
        self.client.configure_language(
            self.state.session_id,
            codes[self.source_choice.get()],
        )
        self._configured_session = self.state.session_id

    def _load_audio_devices(self) -> None:
        try:
            devices = list_wasapi_devices()
        except Exception as error:
            self.state.error = f"Windows audio devices unavailable: {type(error).__name__}"
            return
        self.audio_devices = {device.label: device for device in devices}
        labels = tuple(self.audio_devices)
        self.audio_source_box.configure(values=labels)
        if labels and self.audio_source.get() not in self.audio_devices:
            self.audio_source.set(labels[0])

    def _start_audio_source(self) -> None:
        device = self.audio_devices.get(self.audio_source.get())
        if device is None:
            self.state.error = "Select a Windows microphone or output device first."
            return
        if self.state.capture_status == "capturing":
            self.state.error = "Stop the active Chrome or Windows source first."
            return
        try:
            self.capture_agent.start(device)
            self.state.error = None
        except RuntimeError as error:
            self.state.error = str(error)

    def close(self) -> None:
        self.capture_agent.stop()
        self.client.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    OverlayApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
