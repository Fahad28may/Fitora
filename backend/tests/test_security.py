import time
from uuid import uuid4

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_is_not_plaintext() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert hashed.startswith("$argon2")


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_rejects_garbage_hash() -> None:
    assert verify_password("anything", "not-a-real-hash") is False


def test_access_token_round_trips_user_id() -> None:
    user_id = uuid4()
    token, expires_in = create_access_token(user_id)
    assert expires_in > 0
    assert decode_access_token(token) == user_id


def test_access_token_rejects_tampered_signature() -> None:
    user_id = uuid4()
    token, _ = create_access_token(user_id)
    header, payload, signature = token.split(".")
    # Flip a character in the middle of the signature, not the last char —
    # base64url's final character can have insignificant trailing bits, which
    # made this test flaky when it only mutated token[-1].
    mid = len(signature) // 2
    flipped = "A" if signature[mid] != "A" else "B"
    tampered = f"{header}.{payload}.{signature[:mid]}{flipped}{signature[mid + 1:]}"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_access_token_rejects_wrong_token_type() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    now = int(time.time())
    forged = jwt.encode(
        {"sub": str(uuid4()), "type": "refresh", "iat": now, "exp": now + 900},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)


def test_refresh_tokens_are_unique_and_hashed_deterministically() -> None:
    token_a = generate_refresh_token()
    token_b = generate_refresh_token()
    assert token_a != token_b
    assert hash_refresh_token(token_a) == hash_refresh_token(token_a)
    assert hash_refresh_token(token_a) != hash_refresh_token(token_b)
    assert hash_refresh_token(token_a) != token_a
