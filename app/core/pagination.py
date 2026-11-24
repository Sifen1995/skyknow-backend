"""THE visibility rules. Every query that returns content must use this module.

One place decides who may see what, so no feature can forget the rule.
For the MVP the viewer is a placeholder; Phase 1 fills it from the logged-in user.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Viewer:
    user_id: uuid.UUID | None = None
    group_ids: tuple[uuid.UUID, ...] = ()  # groups the user belongs to
    audience: str = "agent"  # later: "customer" for the help centre and chatbot


# SQL fragment for the `chunks` table (alias c). A chunk is visible when
#   - it is meant for this audience, AND
#   - it has no group restriction, OR the viewer is in at least one allowed group.
CHUNK_VISIBILITY_SQL = """
    (c.audiences @> ARRAY[CAST(:audience AS text)]
     AND (cardinality(c.allowed_group_ids) = 0
          OR c.allowed_group_ids && CAST(:group_ids AS uuid[])))
"""


def visibility_params(viewer: Viewer) -> dict[str, object]:
    return {"audience": viewer.audience, "group_ids": list(viewer.group_ids)}
