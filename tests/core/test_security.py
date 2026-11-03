from app.core.security import hash_password, verify_password


def test_password_hash_can_be_verified() -> None:
    password = "correct horse battery staple"

    password_hash = hash_password(password)

    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)
