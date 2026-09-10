import pytest
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


def test_password_hashing_and_verification():
    raw_password = "SecurePassword#2026"
    hashed = get_password_hash(raw_password)

    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_jwt_access_and_refresh_token_generation():
    subject = "42"
    role = "ADMIN"
    email = "admin@carafford.in"

    access_token = create_access_token(subject=subject, role=role, email=email)
    refresh_token = create_refresh_token(subject=subject, role=role, email=email)

    assert isinstance(access_token, str)
    assert isinstance(refresh_token, str)
    assert access_token != refresh_token

    # Verify decoded access payload
    payload = decode_token(access_token)
    assert payload["sub"] == subject
    assert payload["role"] == role
    assert payload["email"] == email
    assert payload["type"] == "access"
    assert "exp" in payload

    # Verify decoded refresh payload
    ref_payload = decode_token(refresh_token)
    assert ref_payload["sub"] == subject
    assert ref_payload["role"] == role
    assert ref_payload["type"] == "refresh"


def test_jwt_invalid_token():
    with pytest.raises(ValueError, match="Invalid authentication token"):
        decode_token("invalid.jwt.token.string")
