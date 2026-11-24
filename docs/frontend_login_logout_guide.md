# Frontend bearer-token guide

The API uses short-lived JWT access tokens and rotating opaque refresh tokens. Tokens are returned in JSON; authentication does not use cookies.

## Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | Verify credentials and issue an access/refresh token pair |
| `POST` | `/api/v1/auth/refresh` | Rotate the refresh token and issue a new access token |
| `POST` | `/api/v1/auth/logout` | Revoke the refresh-token family |

Use the access token on protected API requests with `Authorization: Bearer <access-token>`. The refresh token is sent in the JSON body only to refresh or logout.

## Login and authenticated requests

```ts
const API_BASE_URL = "http://localhost:8000/api/v1";

type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
};

type UserProfile = {
  id: string;
  full_name: string;
  email: string;
  org_unit_id: string;
};

type LoginResponse = TokenPair & { user: UserProfile };

let accessToken: string | null = null;
let refreshToken: string | null = null;

export async function login(email: string, password: string): Promise<UserProfile> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error(`Login failed (${response.status})`);

  const result: LoginResponse = await response.json();
  accessToken = result.access_token;
  refreshToken = result.refresh_token;
  return result.user;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!accessToken) throw new Error("Sign-in required");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
}
```

Keep both tokens in application memory where practical. Persisting a refresh token in browser storage increases its exposure to injected scripts; use a backend-for-frontend or another secure storage strategy if reload persistence is required. Never log either token.

## Refresh and logout

Refresh before the access token expires, or after a protected request returns `401`. A successful refresh invalidates the submitted refresh token, so replace both in-memory tokens together.

```ts
export async function refreshAuth(): Promise<void> {
  if (!refreshToken) throw new Error("Sign-in required");
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    accessToken = null;
    refreshToken = null;
    throw new Error("Authentication expired; sign in again.");
  }
  const result: TokenPair = await response.json();
  accessToken = result.access_token;
  refreshToken = result.refresh_token;
}

export async function logout(): Promise<void> {
  if (refreshToken) {
    await fetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  }
  accessToken = null;
  refreshToken = null;
}
```

The API allows the configured `CORS_ALLOWED_ORIGINS` and does not enable credentialed CORS. Browser requests do not need `credentials: "include"` or CSRF headers. Configure the exact frontend origin, including scheme and port.
