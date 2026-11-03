from enum import Enum


class RoleName(str, Enum):
    AUTHOR = "author"
    REVIEWER = "reviewer"
    PUBLISHER = "publisher"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
