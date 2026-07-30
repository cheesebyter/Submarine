# RTX 4090 large-v3 baseline

- Date: 2026-07-24
- GPU: NVIDIA GeForce RTX 4090, 24 GB
- Driver: 596.21
- Model: `Systran/faster-whisper-large-v3`
- Runtime: faster-whisper 1.2.1, CTranslate2 4.8.1
- Precision: FP16
- Beam size: 1
- Task: translate to English
- VAD: RMS live segmentation plus Silero VAD

Fixtures were generated locally with Windows voices and retained only under the
ignored `var/logs/translation-benchmark` directory.

| Fixture | Audio | Detected | Probability | Inference | Result |
| --- | ---: | --- | ---: | ---: | --- |
| German | 7.61 s | de | 0.9902 | 782.5 ms | “Good morning! This is a German sentence. We replace it with English.” |
| English | 6.01 s | en | 0.9839 | 498.9 ms | “Good morning. Today we are testing a completely local translation into English.” |

Three subsequent warm German runs measured 716.4 ms, 569.6 ms and 612.8 ms.
The warm median was 612.8 ms, approximately 12 times faster than real time for
the 7.61-second fixture.

Re-run with:

```powershell
.\scripts\benchmark-translation.ps1
```

Synthetic speech is a deterministic smoke fixture, not a comprehensive accuracy
benchmark. Real browser audio must be measured separately as the UI is integrated.
