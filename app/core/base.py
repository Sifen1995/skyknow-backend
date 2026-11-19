from sqlalchemy.orm import DeclarativeBase


# 1. Global Base for the public schema (Super Admins, Tenant Registry)
# Alembic will track models inheriting from this.
class GlobalBase(DeclarativeBase):
    pass


# 2. Tenant Base for dynamic schemas (Tenant Users, Roles, etc.)
# Alembic will ignore these. They are created dynamically per tenant.
class TenantBase(DeclarativeBase):
    pass


# Backwards compatibility alias for tenant-scoped models
Base = TenantBase
