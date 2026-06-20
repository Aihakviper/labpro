from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
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
    token = create_access_token("user-id", expires_delta=timedelta(minutes=1))
    payload = decode_access_token(token)

    assert payload["sub"] == "user-id"

