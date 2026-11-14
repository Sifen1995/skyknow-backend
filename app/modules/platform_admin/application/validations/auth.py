import re

from app.core.errors import ApplicationError
from app.modules.platform_admin.application.dtos import SuperUserRequest

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class IdentityInputError(ApplicationError):
    status_code = 422
    code = "invalid_identity_input"


def validate_login_request(request: SuperUserRequest) -> SuperUserRequest:
    email = request.email.strip()
    if not _EMAIL_PATTERN.fullmatch(email):
        raise IdentityInputError("A valid email address is required")
    if not request.password:
        raise IdentityInputError("Password must not be empty")
    return request.model_copy(update={"email": email})
