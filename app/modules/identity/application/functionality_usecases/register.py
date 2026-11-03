from uuid import UUID

from app.core.security import hash_password
from app.modules.identity.application.errors import (
    DuplicateIdentityError,
    OrgUnitUnavailableError,
)
from app.modules.identity.application.validation.auth import (
    validate_register_request,
)
from app.modules.identity.domain.identity_repository import IdentityRepository
from app.modules.identity.interface.schemas import RegisterRequest, RegisterResponse


class Register:
    def __init__(self, identity_repository: IdentityRepository) -> None:
        self._identity_repository = identity_repository

    async def execute(self, request: RegisterRequest) -> RegisterResponse:
        validated_request = validate_register_request(request)
        org_unit = await self._identity_repository.get_org_unit(
            UUID(validated_request.org_unit_id)
        )
        if org_unit is None or not org_unit.is_active:
            raise OrgUnitUnavailableError("Org unit does not exist or is inactive")

        if await self._identity_repository.get_user_by_email(validated_request.email):
            raise DuplicateIdentityError("Email or telecom ID is already registered")

        user = await self._identity_repository.create_user(
            external_id=validated_request.telecom_id,
            email=validated_request.email,
            full_name=validated_request.full_name,
            password_hash=hash_password(validated_request.password),
            org_unit_id=UUID(validated_request.org_unit_id),
        )
        if user is None:
            raise DuplicateIdentityError("Email or telecom ID is already registered")

        return RegisterResponse.model_validate(user)
