from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(
    user_id: str,
    *,
    secret_key: str,
    algorithm: str,
    expires_seconds: int,
) -> str:
    now = datetime.now(UTC)
    expires_delta = timedelta(seconds=expires_seconds)
    payload: dict[str, Any] = {
        "sub": user_id,
        "token_use": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload,
        secret_key,
        algorithm=algorithm,
    )


def decode_access_token(
    token: str,
    *,
    secret_key: str,
    algorithm: str,
) -> dict[str, Any]:
    return jwt.decode(
        token,
        secret_key,
        algorithms=[algorithm],
    )
