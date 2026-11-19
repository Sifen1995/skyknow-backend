from enum import Enum


class HostingMode(str, Enum):
    SHARED = "shared"
    DEDICATED = "dedicated"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
