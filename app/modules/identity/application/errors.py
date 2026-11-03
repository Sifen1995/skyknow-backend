from app.core.errors import ApplicationError


class AuthenticationFailedError(ApplicationError):
    status_code = 401
    code = "authentication_failed"


class DuplicateIdentityError(ApplicationError):
    status_code = 409
    code = "duplicate_identity"


class OrgUnitUnavailableError(ApplicationError):
    status_code = 404
    code = "org_unit_unavailable"
