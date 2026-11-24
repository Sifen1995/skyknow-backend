"""Id generation. Time-ordered UUIDs (UUIDv7) keep inserts fast on big tables."""

import uuid


def new_id() -> uuid.UUID:
    try:
        import uuid_utils  # pip install uuid-utils

        return uuid.UUID(str(uuid_utils.uuid7()))
    except ImportError:  # fall back to a random UUID so nothing breaks
        return uuid.uuid4()
