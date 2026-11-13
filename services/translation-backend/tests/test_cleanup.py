from submarine_backend.cleanup import EMPTY_MARKER, OllamaCleaner


def _cleaner(*glossary: str) -> OllamaCleaner:
    return OllamaCleaner(
        enabled=True,
        url="http://127.0.0.1:11434",
        model="test",
        timeout_seconds=1,
        glossary=glossary,
    )


def test_prompt_contains_glossary_source_language_and_text() -> None:
    prompt = _cleaner("Tobi", "Angelita").build_prompt("hello toby", "es")
    assert "Spanish (es)" in prompt
    assert "Tobi, Angelita" in prompt
    assert prompt.endswith("hello toby")


def test_prompt_without_glossary_has_no_glossary_rule() -> None:
    assert "exactly as written here" not in _cleaner().build_prompt("hello", None)


def test_plain_correction_is_accepted() -> None:
    assert _cleaner().accept("i put on vaseline", "I put on Vaseline.") == "I put on Vaseline."


def test_glossary_spelling_fix_is_accepted_but_dropped_name_is_not() -> None:
    cleaner = _cleaner("Tobi", "Angelita")
    assert cleaner.accept("Then Toby came.", "Then Tobi came.") == "Then Tobi came."
    assert cleaner.accept("Then Maria came.", "Then she came.") == "Then Maria came."


def test_short_artifact_can_be_removed_but_long_text_cannot() -> None:
    cleaner = _cleaner()
    assert cleaner.accept("Thanks for watching!", EMPTY_MARKER) == ""
    long_text = "we talked for a long time about the trip and what we would cook later on"
    assert cleaner.accept(long_text, EMPTY_MARKER) == long_text


def test_commentary_and_empty_answers_fall_back_to_raw_text() -> None:
    cleaner = _cleaner()
    assert cleaner.accept("Hello.", "") == "Hello."
    assert cleaner.accept("Hello.", "Here is the corrected text you asked for: " * 3) == "Hello."
