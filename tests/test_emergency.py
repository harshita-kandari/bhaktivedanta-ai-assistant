from app.services import emergency


def test_agent_question_does_not_trigger_triage() -> None:
    transcript = (
        "assistant: Do you feel any severe pain, difficulty breathing, or urgent symptoms?\n"
        "user: no, just a blocked ear"
    )
    assert emergency.check_emergency(emergency.caller_text(transcript)) is None


def test_caller_symptom_triggers_triage() -> None:
    transcript = (
        "assistant: How can I help?\n"
        "user: I have severe chest pain since this morning"
    )
    assert emergency.check_emergency(emergency.caller_text(transcript)) == "severe chest pain"


def test_transcript_without_roles_is_still_checked() -> None:
    assert emergency.check_emergency(emergency.caller_text("unconscious and not breathing"))
