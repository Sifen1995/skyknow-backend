from dataclasses import dataclass

import jwt

from app.core.security import decode_access_token
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.identity_repository import IdentityRepository


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str


class AuthenticateAccessToken:
    def __init__(
        self,
        identity_repository: IdentityRepository,
        jwt_secret_key: str,
        jwt_algorithm: str,
    ) -> None:
        self._identity_repository = identity_repository
        self._jwt_secret_key = jwt_secret_key
        self._jwt_algorithm = jwt_algorithm

    async def execute(self, access_token: str) -> AuthenticatedUser | None:
        try:
            payload = decode_access_token(
                access_token,
                secret_key=self._jwt_secret_key,
                algorithm=self._jwt_algorithm,
            )
        except jwt.InvalidTokenError:
            return None

        user_id = payload.get("sub")
        if payload.get("token_use") != "access" or not isinstance(user_id, str):
            return None

        user = await self._identity_repository.get_user_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            return None
        return AuthenticatedUser(user_id=str(user.id))