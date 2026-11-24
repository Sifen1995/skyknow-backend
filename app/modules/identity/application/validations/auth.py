import re

from app.modules.identity.application.dtos import TenantLoginRequest
from app.modules.identity.application.errors import TenantAuthenticationFailedError

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_tenant_login_request(request: TenantLoginRequest) -> TenantLoginRequest:
    email = request.email.strip().lower()
    if not email or not EMAIL_PATTERN.match(email):
        raise TenantAuthenticationFailedError("Invalid email or password")

    if not request.password or not request.password.strip():
        raise TenantAuthenticationFailedError("Invalid email or password")

    return TenantLoginRequest(email=email, password=request.password)
