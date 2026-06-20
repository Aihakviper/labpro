from datetime import timedelta
from uuid import uuid4

from app.core.security import (
    TokenType,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    password = "correct-horse-battery-staple"
    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("wrong-password", hashed_password)


def test_access_token_round_trip() -> None:
    session_id = uuid4()
    token = create_token(
        subject="user-id",
        token_type=TokenType.ACCESS,
        session_id=session_id,
        expires_delta=timedelta(minutes=1),
    )
    payload = decode_token(token)

    assert payload["sub"] == "user-id"
    assert payload["type"] == "access"
    assert payload["sid"] == str(session_id)
