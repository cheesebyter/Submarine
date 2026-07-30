# Local translation pipeline

Submarine translates locally with `faster-whisper` 1.2.1 and the
`Systran/faster-whisper-large-v3` CTranslate2 model.

## Runtime flow

1. The receiver validates each 20 ms protocol audio frame.
2. A bounded 500-frame queue absorbs at most 10 seconds of inference delay and
   drops the oldest frame when full.
3. An RMS energy gate detects speech boundaries with 200 ms pre-roll and
   finalizes after 600 ms of silence.
4. Active speech emits provisional work approximately once per second.
5. Final and provisional chunks run on a worker thread so CUDA inference never
   blocks the WebSocket event loop.
6. faster-whisper performs automatic source-language detection, `task=translate`
   and an additional Silero-VAD pass.
7. Empty model results are not emitted. Provisional and final events share a
   sequence until the final event commits it.

Audio, inferred text and language information remain in memory and are not logged.

## Model lifecycle

The backend accepts only an existing local model directory and passes
`local_files_only=True`. Model acquisition is the explicit
`scripts/download-whisper-model.ps1` step. Startup performs a real CUDA warm-up;
health is `ready` only if model loading and encoder inference both succeed.

On Windows, pinned official NVIDIA cuBLAS 12 and cuDNN 9 wheels provide
process-local DLLs. They are not added to the machine-wide `PATH`.

