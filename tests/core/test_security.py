import bcrypt

from app.core.security import hash_password, verify_password, verify_trusted_origin


def test_password_hash_can_be_verified() -> None:
    password = "correct horse battery staple"

    password_hash = hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)


def test_legacy_bcrypt_password_hash_can_still_be_verified() -> None:
    password = "legacy password"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)


def test_verify_trusted_origin() -> None:
    allowed = ("http://localhost:3000", "https://example.com")
    assert verify_trusted_origin("http://localhost:3000", allowed) is True
    assert verify_trusted_origin("https://evil.com", allowed) is False
    assert verify_trusted_origin(None, allowed) is False
