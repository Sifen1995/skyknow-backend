import asyncio

from argon2 import PasswordHasher
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.modules.platform_admin.domain.models import PlatformAdmin


async def seed_super_super_admin() -> None:
    email = settings.SUPER_SUPER_ADMIN_EMAIL
    password_setting = settings.SUPER_SUPER_ADMIN_PASSWORD
    if email is None and password_setting is None:
        print("Super-super admin credentials are not configured; skipping seed.")
        return
    if email is None or password_setting is None:
        raise ValueError(
            "SUPER_SUPER_ADMIN_EMAIL and SUPER_SUPER_ADMIN_PASSWORD "
            "must both be configured."
        )

    email = email.strip()
    if not email:
        raise ValueError("SUPER_SUPER_ADMIN_EMAIL must not be empty.")
    password = password_setting.get_secret_value()
    if not password:
        raise ValueError("SUPER_SUPER_ADMIN_PASSWORD must not be empty")

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT pg_advisory_xact_lock(846314, 1)"))
            existing_super_admin = await session.scalar(
                select(PlatformAdmin).where(PlatformAdmin.is_super_superuser.is_(True))
            )
            if existing_super_admin is not None:
                print("A super-super admin already exists; leaving it unchanged.")
                return

            existing_admin = await session.scalar(
                select(PlatformAdmin).where(PlatformAdmin.email == email)
            )
            if existing_admin is not None:
                raise RuntimeError(
                    "The configured email already belongs to a non-super "
                    "platform admin; refusing to promote it."
                )

            session.add(
                PlatformAdmin(
                    name="Super Super Admin",
                    email=email,
                    password_hash=PasswordHasher().hash(password),
                    is_super_superuser=True,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing_super_admin = await session.scalar(
                    select(PlatformAdmin).where(
                        PlatformAdmin.is_super_superuser.is_(True)
                    )
                )
                if existing_super_admin is None:
                    raise
                print("A super-super admin already exists; leaving it unchanged.")
                return
            print("Created the configured super-super admin.")
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed_super_super_admin())


if __name__ == "__main__":
    main()
