from app.core.errors import ApplicationError


class TenantNotFoundError(ApplicationError):
    status_code = 404
    code = "tenant_not_found"


class TenantInactiveError(ApplicationError):
    status_code = 403
    code = "tenant_inactive"


class TenantAuthError(ApplicationError):
    status_code = 401
    code = "tenant_auth_error"


class TenantAuthenticationFailedError(TenantAuthError):
    status_code = 401
    code = "authentication_failed"


class TenantUserDisabledError(TenantAuthError):
    status_code = 403
    code = "user_disabled"


class TenantUserPendingError(TenantAuthError):
    status_code = 403
    code = "user_pending"


class TenantAdminAccessDeniedError(TenantAuthError):
    status_code = 403
    code = "admin_access_required"


class TenantRefreshTokenInvalidError(TenantAuthError):
    status_code = 401
    code = "refresh_token_invalid"
