import json
import queue
import struct
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np
import pyaudiowpatch as pyaudio  # type: ignore[import-untyped]
from websockets.sync.client import connect
from websockets.sync.connection import Connection


@dataclass(frozen=True, slots=True)
class AudioDevice:
    index: int
    name: str
    sample_rate: int
    channels: int
    loopback: bool

    @property
    def label(self) -> str:
        kind = "Output" if self.loopback else "Microphone"
        return f"{kind} — {self.name.removesuffix(' [Loopback]')}"


def list_wasapi_devices() -> list[AudioDevice]:
    audio = pyaudio.PyAudio()
    try:
        wasapi_index = next(
            int(host["index"])
            for host in audio.get_host_api_info_generator()
            if "WASAPI" in str(host["name"])
        )
        devices = []
        for value in audio.get_device_info_generator():
            if int(value["hostApi"]) != wasapi_index or int(value["maxInputChannels"]) < 1:
                continue
            devices.append(
                AudioDevice(
                    index=int(value["index"]),
                    name=str(value["name"]),
                    sample_rate=round(float(value["defaultSampleRate"])),
                    channels=min(2, int(value["maxInputChannels"])),
                    loopback=bool(value.get("isLoopbackDevice", False)),
                )
            )
        return sorted(devices, key=lambda device: (device.loopback, device.name.casefold()))
    finally:
        audio.terminate()


def resample_to_pcm16(raw: bytes, channels: int, output_samples: int = 320) -> bytes:
    samples = np.frombuffer(raw, dtype=np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if samples.size == 0:
        return b"\x00" * (output_samples * 2)
    source_positions = np.linspace(0, samples.size - 1, samples.size)
    target_positions = np.linspace(0, samples.size - 1, output_samples)
    mono = np.interp(target_positions, source_positions, samples)
    pcm = np.clip(mono * 32767, -32768, 32767).astype("<i2")
    return pcm.tobytes()


class NativeCaptureAgent:
    def __init__(
        self,
        events: queue.Queue[dict[str, Any]],
        url: str = "ws://127.0.0.1:8765/ws/native-capture",
    ) -> None:
        self.events = events
        self.url = url
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, device: AudioDevice) -> None:
        if self.running:
            raise RuntimeError("A native audio source is already active")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(device,),
            name="submarine-native-capture",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            if not self._thread.is_alive():
                self._thread = None

    def _run(self, device: AudioDevice) -> None:
        audio = pyaudio.PyAudio()
        stream: Any = None
        session_id: str | None = None
        try:
            frames_per_buffer = max(1, round(device.sample_rate * 0.02))
            stream = audio.open(
                format=pyaudio.paFloat32,
                channels=device.channels,
                rate=device.sample_rate,
                input=True,
                input_device_index=device.index,
                frames_per_buffer=frames_per_buffer,
            )
            with connect(self.url, open_timeout=3, close_timeout=2, max_size=16 * 1024) as socket:
                request_id = uuid.uuid4().hex
                socket.send(
                    json.dumps(
                        {
                            "type": "hello",
                            "protocolVersion": 1,
                            "clientType": "capture",
                            "requestId": request_id,
                        }
                    )
                )
                socket.send(
                    json.dumps(
                        {
                            "type": "session.start",
                            "protocolVersion": 1,
                            "requestId": request_id,
                            "audioFormat": {
                                "encoding": "pcm_s16le",
                                "sampleRateHz": 16000,
                                "channels": 1,
                                "frameDurationMs": 20,
                            },
                        }
                    )
                )
                started = json.loads(str(socket.recv(timeout=5)))
                if started.get("type") != "session.started":
                    raise RuntimeError(str(started.get("message", "Backend rejected audio source")))
                session_id = str(started["sessionId"])
                receiver = threading.Thread(
                    target=self._drain_server,
                    args=(socket,),
                    name="submarine-native-capture-receiver",
                    daemon=True,
                )
                receiver.start()
                sequence = 0
                started_at = time.monotonic()
                while not self._stop.is_set():
                    raw = stream.read(frames_per_buffer, exception_on_overflow=False)
                    payload = resample_to_pcm16(raw, device.channels)
                    timestamp_ms = round((time.monotonic() - started_at) * 1000)
                    header = b"SUBA" + struct.pack(
                        "<BBHIQ",
                        1,
                        0,
                        20,
                        sequence,
                        timestamp_ms,
                    )
                    socket.send(header + payload)
                    sequence = (sequence + 1) & 0xFFFFFFFF
                socket.send(
                    json.dumps(
                        {
                            "type": "session.stop",
                            "protocolVersion": 1,
                            "sessionId": session_id,
                            "reason": "user",
                        }
                    )
                )
        except Exception as error:
            self.events.put(
                {
                    "type": "capture.local.error",
                    "message": f"Audio source failed: {type(error).__name__}: {error}",
                }
            )
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            audio.terminate()

    def _drain_server(self, socket: Connection) -> None:
        try:
            while not self._stop.is_set():
                message = json.loads(str(socket.recv()))
                if message.get("type") == "error":
                    self.events.put(
                        {
                            "type": "capture.local.error",
                            "message": str(message.get("message", "Backend audio error")),
                        }
                    )
                    self._stop.set()
        except Exception:
            return
