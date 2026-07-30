import numpy as np

from submarine_overlay.audio_capture import resample_to_pcm16


def test_resampler_produces_one_protocol_frame_from_stereo_float_audio() -> None:
    stereo = np.column_stack(
        (
            np.full(960, 0.5, dtype=np.float32),
            np.full(960, -0.25, dtype=np.float32),
        )
    )

    pcm = resample_to_pcm16(stereo.tobytes(), channels=2)
    samples = np.frombuffer(pcm, dtype="<i2")

    assert len(pcm) == 640
    assert samples.size == 320
    assert np.allclose(samples.mean(), 4095, atol=2)


def test_resampler_handles_silence() -> None:
    assert resample_to_pcm16(b"", channels=1) == b"\x00" * 640
