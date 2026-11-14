import pytest

from app.modules.platform_admin.application.dtos import SuperUserRequest
from app.modules.platform_admin.application.validations.auth import (
    IdentityInputError,
    validate_login_request,
)


def test_login_validator_accepts_password_longer_than_bcrypt_limit() -> None:
    request = SuperUserRequest(email="  admin@example.com  ", password="p" * 100)

    validated_request = validate_login_request(request)

    assert validated_request.email == "admin@example.com"
    assert validated_request.password == request.password


def test_login_validator_rejects_empty_password() -> None:
    request = SuperUserRequest(email="admin@example.com", password="")

    with pytest.raises(IdentityInputError, match="Password must not be empty"):
        validate_login_request(request)


def test_login_validator_rejects_invalid_email() -> None:
    request = SuperUserRequest(email="invalid-email", password="valid-password")

    with pytest.raises(IdentityInputError, match="A valid email address is required"):
        validate_login_request(request)
