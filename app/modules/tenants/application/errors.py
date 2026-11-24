from app.core.errors import ApplicationError


class TenantError(ApplicationError):
    status_code = 500
    code = "tenant_error"


class SubdomainAlreadyExistsError(TenantError):
    status_code = 409
    code = "subdomain_already_exists"


class CustomDomainAlreadyExistsError(TenantError):
    status_code = 409
    code = "custom_domain_already_exists"


class InvalidSubdomainError(TenantError):
    status_code = 422
    code = "invalid_subdomain"


class InvalidTenantInputError(TenantError):
    status_code = 422
    code = "invalid_tenant_input"


class TenantNotFoundError(TenantError):
    status_code = 404
    code = "tenant_not_found"


class TenantProvisioningFailedError(TenantError):
    status_code = 500
    code = "tenant_provisioning_failed"
