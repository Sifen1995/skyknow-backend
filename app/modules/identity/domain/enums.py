from enum import StrEnum


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class SystemRole(StrEnum):
    ADMIN = "admin"
    AUTHOR = "author"
    REVIEWER = "reviewer"
    PUBLISHER = "publisher"


class RoleScope(StrEnum):
    COMPANY = "company"
    UNIT_AND_BELOW = "unit_and_below"
    OWN_UNIT = "own_unit"


class IdPType(StrEnum):
    STANDALONE = "standalone"
    OIDC = "oidc"
    SAML = "saml"
    LDAP = "ldap"
