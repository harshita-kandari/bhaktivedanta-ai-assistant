import pytest
from pydantic import ValidationError

from app.api.schemas import CallPlaceRequest


def test_call_language_accepts_hindi() -> None:
    request = CallPlaceRequest(recipient_phone_number="+919876543210", language="hi")
    assert request.language == "hi"


def test_call_language_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        CallPlaceRequest(recipient_phone_number="+919876543210", language="fr")
