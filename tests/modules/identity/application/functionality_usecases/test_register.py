from uuid import UUID, uuid4

import pytest

from app.modules.identity.application.errors import (
    DuplicateIdentityError,
    OrgUnitUnavailableError,
)
from app.modules.identity.application.functionality_usecases import (
    register as register_module,
)
from app.modules.identity.application.functionality_usecases.register import Register
from app.modules.identity.application.validation.auth import IdentityInputError
from app.modules.identity.domain.models import OrgUnit, User
from app.modules.identity.interface.schemas import RegisterRequest
from tests.modules.identity.fakes import FakeIdentityRepository


def make_org_unit(*, is_active: bool = True) -> OrgUnit:
    return OrgUnit(
        id=uuid4(),
        label="test",
        name="Test unit",
        path="test",
        is_active=is_active,
    )


def make_user(email: str, org_unit_id: UUID) -> User:
    return User(
        id=uuid4(),
        email=email,
        full_name="Test Person",
        org_unit_id=org_unit_id,
    )


def make_request(org_unit_id: str) -> RegisterRequest:
    return RegisterRequest(
        full_name="  Test Person  ",
        telecom_id="  telecom-123  ",
        email="  person@example.com  ",
        password="strong-password",
        org_unit_id=org_unit_id,
    )


@pytest.mark.asyncio
async def test_register_creates_user_with_normalized_values_and_hashed_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_unit = make_org_unit()
    created_user = make_user("person@example.com", org_unit.id)
    repository = FakeIdentityRepository(
        org_unit=org_unit,
        created_user=created_user,
    )
    monkeypatch.setattr(register_module, "hash_password", lambda _: "hashed-password")

    response = await Register(repository).execute(make_request(str(org_unit.id)))

    assert response.id == created_user.id
    assert response.email == "person@example.com"
    assert repository.looked_up_emails == ["person@example.com"]
    assert repository.created_user_values == {
        "external_id": "telecom-123",
        "email": "person@example.com",
        "full_name": "Test Person",
        "password_hash": "hashed-password",
        "org_unit_id": org_unit.id,
    }


@pytest.mark.asyncio
async def test_register_rejects_existing_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_unit = make_org_unit()
    existing_user = make_user("person@example.com", org_unit.id)
    repository = FakeIdentityRepository(user=existing_user, org_unit=org_unit)
    monkeypatch.setattr(register_module, "hash_password", lambda _: "hashed-password")

    with pytest.raises(DuplicateIdentityError):
        await Register(repository).execute(make_request(str(org_unit.id)))

    assert repository.created_user_values is None


@pytest.mark.asyncio
@pytest.mark.parametrize("org_unit", [None, make_org_unit(is_active=False)])
async def test_register_rejects_missing_or_inactive_org_unit(
    org_unit: OrgUnit | None,
) -> None:
    repository = FakeIdentityRepository(org_unit=org_unit)

    with pytest.raises(OrgUnitUnavailableError):
        await Register(repository).execute(make_request(str(uuid4())))

    assert repository.looked_up_emails == []
    assert repository.created_user_values is None


@pytest.mark.asyncio
async def test_register_reports_duplicate_if_insert_loses_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_unit = make_org_unit()
    repository = FakeIdentityRepository(org_unit=org_unit, created_user=None)
    monkeypatch.setattr(register_module, "hash_password", lambda _: "hashed-password")

    with pytest.raises(DuplicateIdentityError):
        await Register(repository).execute(make_request(str(org_unit.id)))

    assert repository.created_user_values is not None


@pytest.mark.asyncio
async def test_register_rejects_invalid_org_unit_id() -> None:
    with pytest.raises(IdentityInputError):
        await Register(FakeIdentityRepository()).execute(make_request("not-a-uuid"))
