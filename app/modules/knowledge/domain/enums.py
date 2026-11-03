from enum import Enum


class TemplateType(str, Enum):
    HOWTO = "howto"
    FAQ = "faq"
    POLICY = "policy"


class PageVisibility(str, Enum):
    RESTRICTED = "restricted"
    ALL_STAFF = "all_staff"


class VersionState(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
