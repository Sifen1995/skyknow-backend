import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.security import hash_password
from app.modules.identity.application.dtos import (
    TenantLoginRequest,
    TenantLogoutRequest,
    TenantRefreshRequest,
)
from app.modules.identity.application.errors import (
    TenantAuthenticationFailedError,
    TenantRefreshTokenInvalidError,
    TenantUserDisabledError,
)
from app.modules.identity.application.logout import TenantLogout
from app.modules.identity.application.refresh_token import TenantRefreshTokenUseCase
from app.modules.identity.application.tenant_admin_login import TenantAdminLogin
from app.modules.identity.domain.enums import RoleScope, SystemRole, UserStatus
from app.modules.identity.domain.models import Role, User, UserIdentity
from app.modules.identity.domain.repository import TenantRefreshTokenRecord


class FakeTenantUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.last_login_updates: list[tuple[UUID, datetime]] = []

    async def get_by_email(self, email: str) -> User | None:
        return self.users.get(email.lower())

    async def get_by_id(self, user_id: UUID) -> User | None:
        for user in self.users.values():
            if user.id == user_id:
                return user
        return None

    async def update_last_login(self, user: User, timestamp: datetime) -> None:
        self.last_login_updates.append((user.id, timestamp))
        user.last_login_at = timestamp


class FakeTenantIdentityRepository:
    def __init__(self) -> None:
        self.identities: dict[UUID, UserIdentity] = {}

    async def get_standalone_identity(self, user_id: UUID) -> UserIdentity | None:
        return self.identities.get(user_id)

    async def get_identity_by_provider(
        self, identity_provider_id: UUID, provider_user_id: str
    ) -> UserIdentity | None:
        return None


class FakeTenantRefreshTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[UUID, TenantRefreshTokenRecord] = {}
        self.revoked_all_users: list[UUID] = []

    async def store_refresh_token(
        self,
        *,
        family_id: UUID,
        user_id: UUID,
        secret_hash: str,
        expires_at: datetime,
    ) -> None:
        self.tokens[family_id] = TenantRefreshTokenRecord(
            family_id=family_id,
            user_id=user_id,
            current_generation=1,
            secret_hash=secret_hash,
            expires_at=expires_at,
            revoked_at=None,
        )

    async def get_refresh_token(
        self, family_id: UUID
    ) -> TenantRefreshTokenRecord | None:
        return self.tokens.get(family_id)

    async def rotate_refresh_token(
        self,
        *,
        family_id: UUID,
        new_secret_hash: str,
        new_expires_at: datetime,
    ) -> int:
        record = self.tokens[family_id]
        new_gen = record.current_generation + 1
        self.tokens[family_id] = TenantRefreshTokenRecord(
            family_id=family_id,
            user_id=record.user_id,
            current_generation=new_gen,
            secret_hash=new_secret_hash,
            expires_at=new_expires_at,
            revoked_at=None,
        )
        return new_gen

    async def revoke_refresh_token(self, family_id: UUID) -> None:
        record = self.tokens.get(family_id)
        if record:
            self.tokens[family_id] = TenantRefreshTokenRecord(
                family_id=family_id,
                user_id=record.user_id,
                current_generation=record.current_generation,
                secret_hash=record.secret_hash,
                expires_at=record.expires_at,
                revoked_at=datetime.now(UTC),
            )

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        self.revoked_all_users.append(user_id)


def create_test_fixtures() -> tuple[
    FakeTenantUserRepository,
    FakeTenantIdentityRepository,
    FakeTenantRefreshTokenRepository,
    User,
]:
    user_repo = FakeTenantUserRepository()
    identity_repo = FakeTenantIdentityRepository()
    token_repo = FakeTenantRefreshTokenRepository()

    admin_role = Role(
        id=uuid4(),
        name=SystemRole.ADMIN,
        scope=RoleScope.COMPANY,
        description="Full tenant admin",
    )

    user = User(
        id=uuid4(),
        organisation_unit_id=uuid4(),
        role_id=admin_role.id,
        name="Abebe Admin",
        email="admin@cbe.et",
        status=UserStatus.ACTIVE,
    )
    user.role = admin_role

    identity = UserIdentity(
        id=uuid4(),
        user_id=user.id,
        identity_provider_id=uuid4(),
        provider_user_id=user.email,
        password_hash=hash_password("SuperSecret123!"),
    )

    user_repo.users[user.email] = user
    identity_repo.identities[user.id] = identity

    return user_repo, identity_repo, token_repo, user


@pytest.mark.asyncio
async def test_tenant_admin_login_success() -> None:
    user_repo, identity_repo, token_repo, _ = create_test_fixtures()

    use_case = TenantAdminLogin(
        user_repository=user_repo,
        identity_repository=identity_repo,
        refresh_token_repository=token_repo,
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        jwt_secret_key="super-secret-test-key-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )

    result = await use_case.execute(
        TenantLoginRequest(email="admin@cbe.et", password="SuperSecret123!"),
        subdomain="cbe",
    )

    assert result.user.email == "admin@cbe.et"
    assert result.user.role == "admin"
    assert result.access_token is not None
    assert result.refresh_token is not None
    assert result.current_generation == 1
    assert result.family_id in token_repo.tokens
    assert len(user_repo.last_login_updates) == 1


@pytest.mark.asyncio
async def test_tenant_admin_login_rejects_wrong_password() -> None:
    user_repo, identity_repo, token_repo, _ = create_test_fixtures()

    use_case = TenantAdminLogin(
        user_repository=user_repo,
        identity_repository=identity_repo,
        refresh_token_repository=token_repo,
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        jwt_secret_key="super-secret-test-key-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )

    with pytest.raises(TenantAuthenticationFailedError):
        await use_case.execute(
            TenantLoginRequest(email="admin@cbe.et", password="WrongPassword!"),
            subdomain="cbe",
        )


@pytest.mark.asyncio
async def test_tenant_login_regular_user_succeeds_with_member_role() -> None:
    user_repo, identity_repo, token_repo, user = create_test_fixtures()
    # Change role to author
    user.role = Role(
        id=uuid4(),
        name=SystemRole.AUTHOR,
        scope=RoleScope.OWN_UNIT,
    )

    use_case = TenantAdminLogin(
        user_repository=user_repo,
        identity_repository=identity_repo,
        refresh_token_repository=token_repo,
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        jwt_secret_key="super-secret-test-key-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )

    result = await use_case.execute(
        TenantLoginRequest(email="admin@cbe.et", password="SuperSecret123!"),
        subdomain="cbe",
    )

    assert result.user.role == "author"
    assert result.user.is_admin is False


@pytest.mark.asyncio
async def test_tenant_admin_login_rejects_disabled_user() -> None:
    user_repo, identity_repo, token_repo, user = create_test_fixtures()
    user.status = UserStatus.DISABLED

    use_case = TenantAdminLogin(
        user_repository=user_repo,
        identity_repository=identity_repo,
        refresh_token_repository=token_repo,
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        jwt_secret_key="super-secret-test-key-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )

    with pytest.raises(TenantUserDisabledError):
        await use_case.execute(
            TenantLoginRequest(email="admin@cbe.et", password="SuperSecret123!"),
            subdomain="cbe",
        )


@pytest.mark.asyncio
async def test_tenant_refresh_token_rotation() -> None:
    user_repo, _, token_repo, user = create_test_fixtures()

    family_id = uuid4()
    raw_secret = "initial_refresh_token_secret"
    secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

    await token_repo.store_refresh_token(
        family_id=family_id,
        user_id=user.id,
        secret_hash=secret_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )

    use_case = TenantRefreshTokenUseCase(
        user_repository=user_repo,
        refresh_token_repository=token_repo,
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        jwt_secret_key="super-secret-test-key-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )

    result = await use_case.execute(
        TenantRefreshRequest(family_id=family_id, count=1, refresh_token=raw_secret),
        subdomain="cbe",
    )

    assert result.current_generation == 2
    assert result.access_token is not None
    assert result.refresh_token != raw_secret


@pytest.mark.asyncio
async def test_tenant_refresh_token_theft_detection_revokes_family() -> None:
    user_repo, _, token_repo, user = create_test_fixtures()

    family_id = uuid4()
    raw_secret = "initial_refresh_token_secret"
    secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

    await token_repo.store_refresh_token(
        family_id=family_id,
        user_id=user.id,
        secret_hash=secret_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )

    use_case = TenantRefreshTokenUseCase(
        user_repository=user_repo,
        refresh_token_repository=token_repo,
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        jwt_secret_key="super-secret-test-key-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )

    # Present mismatched secret (theft attempt)
    with pytest.raises(TenantRefreshTokenInvalidError):
        await use_case.execute(
            TenantRefreshRequest(
                family_id=family_id, count=1, refresh_token="wrong_secret"
            ),
            subdomain="cbe",
        )

    # Token family must now be revoked
    record = await token_repo.get_refresh_token(family_id)
    assert record is not None
    assert record.revoked_at is not None


@pytest.mark.asyncio
async def test_tenant_logout() -> None:
    _, _, token_repo, _ = create_test_fixtures()
    family_id = uuid4()
    token_repo.tokens[family_id] = TenantRefreshTokenRecord(
        family_id=family_id,
        user_id=uuid4(),
        current_generation=1,
        secret_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked_at=None,
    )

    use_case = TenantLogout(refresh_token_repository=token_repo)
    await use_case.execute(TenantLogoutRequest(family_id=family_id))

    record = await token_repo.get_refresh_token(family_id)
    assert record is not None
    assert record.revoked_at is not None
