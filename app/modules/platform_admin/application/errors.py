from app.core.errors import ApplicationError


class AuthenticationFailedError(ApplicationError):
    status_code = 401
    code = "authentication_failed"
