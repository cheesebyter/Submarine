from submarine_overlay.state import OverlayState


def test_provisional_is_replaced_by_final_without_duplication() -> None:
    state = OverlayState()
    state.apply(
        {
            "type": "transcript.provisional",
            "text": "How are",
            "sourceLanguage": "de",
        }
    )
    state.apply(
        {
            "type": "transcript.final",
            "text": "How are you?",
            "sourceLanguage": "de",
        }
    )
    state.apply(
        {
            "type": "transcript.final",
            "text": "How are you?",
            "sourceLanguage": "de",
        }
    )

    assert state.provisional == ""
    assert list(state.finals) == ["How are you?"]
    assert state.source_language == "de"


def test_adjacent_final_duplicate_ignores_case_and_punctuation() -> None:
    state = OverlayState()
    state.apply(
        {
            "type": "transcript.final",
            "text": "Good night!",
            "sourceLanguage": "es",
        }
    )
    state.apply(
        {
            "type": "transcript.final",
            "text": "good night.",
            "sourceLanguage": "es",
        }
    )

    assert list(state.finals) == ["Good night!"]


def test_history_is_bounded() -> None:
    state = OverlayState()
    for number in range(10):
        state.apply(
            {
                "type": "transcript.final",
                "text": f"Sentence {number}",
                "sourceLanguage": "es",
            }
        )

    assert list(state.finals) == [f"Sentence {number}" for number in range(4, 10)]


def test_clear_removes_final_and_provisional_text_only() -> None:
    state = OverlayState(
        connected=True,
        capture_status="capturing",
        session_id="session-1",
        provisional="In progress",
    )
    state.finals.append("Completed sentence")

    state.clear_transcript()

    assert list(state.finals) == []
    assert state.provisional == ""
    assert state.connected
    assert state.capture_status == "capturing"
    assert state.session_id == "session-1"


def test_audio_level_detects_prolonged_silence() -> None:
    state = OverlayState(capture_status="capturing")
    state.apply({"type": "audio.level", "rms": 0.0, "signal": False})
    assert state.last_audio_at is not None
    assert state.has_no_signal(state.last_audio_at + 3.1)

    state.apply({"type": "audio.level", "rms": 0.2, "signal": True})
    assert state.last_signal_at is not None
    assert not state.has_no_signal(state.last_signal_at + 1.0)
