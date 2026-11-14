# JWT access and refresh-token flow

The identity module issues short-lived JWT access tokens and opaque refresh tokens. Access tokens are validated from the `Authorization: Bearer` header; refresh tokens are stored only as SHA-256 digests in PostgreSQL.

## Components

- `app/routers/identity.py` exposes login, refresh, logout, and registration endpoints.
- `app/modules/identity/application/functionality_usecases/login.py` validates credentials and issues the initial token pair.
- `app/modules/identity/application/functionality_usecases/refresh_tokens.py` rotates refresh tokens.
- `app/modules/identity/application/functionality_usecases/authenticate_access_token.py` validates access JWTs and checks that the account is active.
- `app/modules/identity/domain/refresh_token_repository.py` defines refresh-token persistence operations.
- `app/modules/identity/infrastructure/sqlalchemy_refresh_token_repository.py` persists token digests and revocation state.
- `migrations/versions/0004_identity_refresh_tokens.py` creates the refresh-token table.

## Login

`POST /api/v1/auth/login` accepts an email and password. On successful verification, the response contains `access_token`, `refresh_token`, `token_type`, `expires_in`, and the user profile. The access token expires after `ACCESS_TOKEN_TTL_SECONDS` (15 minutes by default). The refresh token expires after `REFRESH_TOKEN_TTL_SECONDS` (30 days by default).

The refresh token is cryptographically random. Only its SHA-256 digest is stored with its user, token-family ID, expiry, and revocation timestamp. Access JWTs are not stored in the database.

## Request authentication

Protected routes require `Authorization: Bearer <access_token>`. The JWT signature, expiration, and access-token purpose are validated, then the user is checked for an active status. Cookie authentication, session lookup, and CSRF validation are not used.

## Refresh rotation and logout

`POST /api/v1/auth/refresh` accepts `{ "refresh_token": "..." }`. The matching database row is locked during rotation. A valid token is revoked and replaced with a fresh random token in the same family; the response returns a new access/refresh pair. Reusing an already-revoked or expired token is rejected.

`POST /api/v1/auth/logout` accepts the current refresh token and revokes every token in its family. Access JWTs already issued remain valid until their short expiry; logout does not maintain a server-side access-token denylist.

## Configuration

Set `SECRET_KEY` to a high-entropy secret and keep `ALGORITHM` restricted to the configured algorithm (HS256 by default). `ACCESS_TOKEN_TTL_SECONDS` and `REFRESH_TOKEN_TTL_SECONDS` control token lifetimes. Apply the Alembic migration before deploying the new endpoints.
