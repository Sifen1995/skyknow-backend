import re
from uuid import UUID

from app.core.errors import ApplicationError
from app.modules.identity.interface.schemas import LoginRequest, RegisterRequest

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_BCRYPT_PASSWORD_BYTES = 72


class IdentityInputError(ApplicationError):
    status_code = 422
    code = "invalid_identity_input"


def validate_login_request(request: LoginRequest) -> LoginRequest:
    email = request.email.strip()
    if not _EMAIL_PATTERN.fullmatch(email):
        raise IdentityInputError("A valid email address is required")
    password_bytes = len(request.password.encode("utf-8"))
    if not 1 <= password_bytes <= _MAX_BCRYPT_PASSWORD_BYTES:
        raise IdentityInputError("Password must be between 1 and 72 UTF-8 bytes")
    return request.model_copy(update={"email": email})


def validate_register_request(request: RegisterRequest) -> RegisterRequest:
    full_name = request.full_name.strip()
    telecom_id = request.telecom_id.strip()
    email = request.email.strip()

    if not full_name:
        raise IdentityInputError("Full name is required")
    if not telecom_id:
        raise IdentityInputError("Telecom ID is required")
    if not _EMAIL_PATTERN.fullmatch(email):
        raise IdentityInputError("A valid email address is required")
    password_bytes = request.password.encode("utf-8")
    if not 8 <= len(password_bytes) <= _MAX_BCRYPT_PASSWORD_BYTES:
        raise IdentityInputError("Password must be between 8 and 72 UTF-8 bytes")
    try:
        org_unit_id = UUID(request.org_unit_id)
    except ValueError as error:
        raise IdentityInputError("Org unit ID must be a valid UUID") from error

    return request.model_copy(
        update={
            "full_name": full_name,
            "telecom_id": telecom_id,
            "email": email,
            "org_unit_id": str(org_unit_id),
        }
    )
