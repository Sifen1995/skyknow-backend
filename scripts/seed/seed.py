import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.core.security import hash_password

LANGUAGES = (
    ("en", "English", "English", 1),
    ("am", "Amharic", "አማርኛ", 2),
    ("om", "Oromo", "Afaan Oromoo", 3),
)

ORG_UNITS = (
    ("ceo", "ceo", "CEO", None),
    ("chief_cs", "chief_cs", "Chief Customer Service", "ceo"),
    ("bo", "bo", "Back Office", "chief_cs"),
    ("fo", "fo", "Front Office", "chief_cs"),
    ("digital", "digital", "Digital Channels", "fo"),
    ("call_center", "call_center", "Call Center", "fo"),
    ("sup_a", "sup_a", "Supervisor A", "call_center"),
    ("coach_1", "coach_1", "Coach 1's team", "sup_a"),
    ("sup_b", "sup_b", "Supervisor B", "call_center"),
)

USERS = (
    ("ceo", "Abebe Bekele", "ceo@example.test", True, "ceo"),
    ("chief_cs", "Hana Tesfaye", "chief-cs@example.test", False, "chief_cs"),
    ("bo_officer", "Dawit Alemu", "bo-officer@example.test", False, "bo"),
    (
        "call_center_manager",
        "Selamawit Tadesse",
        "call-center-manager@example.test",
        False,
        "call_center",
    ),
    ("supervisor_a", "Bereket Kebede", "supervisor-a@example.test", False, "sup_a"),
    ("supervisor_b", "Meron Girma", "supervisor-b@example.test", False, "sup_b"),
    ("coach_1", "Samuel Haile", "coach-1@example.test", False, "coach_1"),
    ("agent_1", "Bethlehem Getachew", "agent-1@example.test", False, "coach_1"),
)

PAGE_AUTHOR_ASSIGNMENT = ("coach_1", "author", "coach_1")

ROLE_ASSIGNMENTS = (
    PAGE_AUTHOR_ASSIGNMENT,
    ("supervisor_a", "reviewer", "sup_a"),
    ("supervisor_b", "reviewer", "sup_b"),
    ("call_center_manager", "publisher", "call_center"),
)


async def seed() -> None:
    seed_password = os.environ.get("SEED_USER_PASSWORD")
    if not seed_password or len(seed_password) < 8:
        raise SystemExit(
            "Set SEED_USER_PASSWORD to a password of at least 8 characters."
        )
    if len(seed_password.encode("utf-8")) > 72:
        raise SystemExit(
            "SEED_USER_PASSWORD must be no more than 72 UTF-8 bytes for bcrypt."
        )

    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as connection:
            for code, name, native_name, sort_order in LANGUAGES:
                await connection.execute(
                    text(
                        """
						INSERT INTO languages (code, name, native_name, sort_order)
						VALUES (:code, :name, :native_name, :sort_order)
						ON CONFLICT (code) DO UPDATE SET
							name = EXCLUDED.name,
							native_name = EXCLUDED.native_name,
							is_active = TRUE,
							sort_order = EXCLUDED.sort_order
						"""
                    ),
                    {
                        "code": code,
                        "name": name,
                        "native_name": native_name,
                        "sort_order": sort_order,
                    },
                )

            org_unit_ids: dict[str, object] = {}
            for path, label, name, parent_path in ORG_UNITS:
                parent_id = org_unit_ids.get(parent_path) if parent_path else None
                result = await connection.execute(
                    text(
                        """
						INSERT INTO org_units (parent_id, label, name, path)
						VALUES (
							:parent_id,
							CAST(:label AS ltree),
							CAST(:name AS citext),
							CAST(:label AS ltree)
						)
						ON CONFLICT (path) DO UPDATE SET
							parent_id = EXCLUDED.parent_id,
							label = EXCLUDED.label,
							name = EXCLUDED.name,
							is_active = TRUE
						RETURNING id
						"""
                    ),
                    {
                        "parent_id": parent_id,
                        "label": label,
                        "name": name,
                    },
                )
                org_unit_ids[path] = result.scalar_one()

            for path, _, _, _ in ORG_UNITS:
                await connection.execute(
                    text(
                        "UPDATE org_units SET head_user_id = NULL "
                        "WHERE path = CAST(:path AS ltree)"
                    ),
                    {"path": path},
                )

            user_ids: dict[str, object] = {}
            for external_id, full_name, email, is_admin, org_path in USERS:
                password_hash = hash_password(seed_password)
                result = await connection.execute(
                    text(
                        """
						INSERT INTO users (
							external_id, email, full_name, password_hash, is_admin,
							org_unit_id, preferred_language
						)
						VALUES (
							:external_id, CAST(:email AS citext), :full_name,
							:password_hash, :is_admin, :org_unit_id, 'en'
						)
						ON CONFLICT (email) DO UPDATE SET
							external_id = EXCLUDED.external_id,
							full_name = EXCLUDED.full_name,
							password_hash = EXCLUDED.password_hash,
							status = 'active',
							is_admin = EXCLUDED.is_admin,
							org_unit_id = EXCLUDED.org_unit_id,
							preferred_language = EXCLUDED.preferred_language
						RETURNING id
						"""
                    ),
                    {
                        "external_id": f"seed:{external_id}",
                        "email": email,
                        "full_name": full_name,
                        "password_hash": password_hash,
                        "is_admin": is_admin,
                        "org_unit_id": org_unit_ids[org_path],
                    },
                )
                user_ids[external_id] = result.scalar_one()

            heads = (
                ("ceo", "ceo"),
                ("chief_cs", "chief_cs"),
                ("call_center", "call_center_manager"),
                ("sup_a", "supervisor_a"),
                ("coach_1", "coach_1"),
                ("sup_b", "supervisor_b"),
            )
            for org_path, user_key in heads:
                await connection.execute(
                    text(
                        """
						UPDATE org_units
						SET head_user_id = :user_id
						WHERE path = CAST(:path AS ltree)
						"""
                    ),
                    {"path": org_path, "user_id": user_ids[user_key]},
                )

            for user_key, role, org_path in ROLE_ASSIGNMENTS:
                await connection.execute(
                    text(
                        """
						INSERT INTO role_assignments (user_id, role, org_unit_id)
						VALUES (:user_id, CAST(:role AS role_name), :org_unit_id)
						ON CONFLICT (user_id, role, org_unit_id) DO NOTHING
						"""
                    ),
                    {
                        "user_id": user_ids[user_key],
                        "role": role,
                        "org_unit_id": org_unit_ids[org_path],
                    },
                )

        print("Seeded languages, org units, users, and role assignments.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
