# Frontend login and logout guide

This guide covers the browser flow for the backend's opaque, Redis-backed
session. The examples use TypeScript and the Fetch API; the same cookie and
CSRF requirements apply to other frontend frameworks.

## Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | Verify credentials, create a session, and set its cookie |
| `GET` | `/api/v1/auth/csrf` | Get the CSRF token for an existing session |
| `POST` | `/api/v1/auth/logout` | Revoke the session and clear its cookie |

The login response JSON contains a user profile and `csrf_token`. The opaque
session token is set in an `HttpOnly` cookie and is never returned to
JavaScript.

## Configure the API URL

Use the API origin and prefix appropriate to the environment:

```ts
const API_BASE_URL = "http://localhost:8000/api/v1";
```

In production, use the HTTPS API URL. Configure the backend's
`CORS_ALLOWED_ORIGINS` with the exact frontend origin (for local development,
for example, `http://localhost:7000`). Origins include scheme and port, but not
paths. Requests to login and state-changing endpoints must have an allowed
`Origin`.

The frontend and API on different localhost ports are **cross-origin** for
CORS, though they are normally same-site for cookie `SameSite` rules. Browser
requests must still include credentials. `Secure` cookies require HTTPS in
production; localhost cookie handling can vary by browser, so verify acceptance
in the browser's developer tools.

## Define response types and keep CSRF state

Keep the CSRF token in application memory (for example, React state or a
session/authentication service). Do not put the session cookie or CSRF token in
`localStorage`. The CSRF token can be fetched again after a reload while the
session cookie remains valid.

```ts
type UserProfile = {
  id: string;
  full_name: string;
  email: string;
  org_unit_id: string;
};

type LoginResponse = {
  csrf_token: string;
  user: UserProfile;
};

type CsrfResponse = {
  csrf_token: string;
};

let csrfToken: string | null = null;
```

## Log in

Send JSON credentials and set `credentials: "include"`. The browser processes
the `Set-Cookie` response and stores the HTTP-only session cookie.

```ts
export async function login(
  email: string,
  password: string,
): Promise<UserProfile> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error(`Login failed (${response.status})`);
  }

  const result: LoginResponse = await response.json();
  csrfToken = result.csrf_token;
  return result.user;
}
```

Do not try to read `Set-Cookie` from JavaScript or manually set a `Cookie`
header. The cookie is intentionally `HttpOnly`; the browser sends it
automatically on requests using `credentials: "include"`.

## Restore CSRF state after a reload

The CSRF token held in memory disappears when the page reloads. If the browser
still has a session cookie, request the token again:

```ts
export async function refreshCsrfToken(): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/csrf`, {
    method: "GET",
    credentials: "include",
  });

  if (!response.ok) {
    csrfToken = null;
    throw new Error(`Could not restore session (${response.status})`);
  }

  const result: CsrfResponse = await response.json();
  csrfToken = result.csrf_token;
  return csrfToken;
}
```

Call this during application startup when restoring a signed-in state. Treat
`401` as no valid session and show the signed-out state.

## Call protected endpoints

All browser requests that rely on the session need `credentials: "include"`.
For `POST`, `PUT`, `PATCH`, and `DELETE`, also send `X-CSRF-Token`.

```ts
export async function createSomething(payload: unknown): Promise<Response> {
  if (!csrfToken) {
    await refreshCsrfToken();
  }

  const response = await fetch(`${API_BASE_URL}/some-protected-resource`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken!,
    },
    body: JSON.stringify(payload),
  });

  if (response.status === 401) {
    csrfToken = null;
    throw new Error("Your session has expired. Please log in again.");
  }
  if (response.status === 403) {
    throw new Error("The request failed origin or CSRF validation.");
  }
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }

  return response;
}
```

If a protected request returns `401`, the session may be missing, expired, or
revoked. Clear frontend authentication state and ask the user to log in again.
A `403` on a state-changing request usually indicates an untrusted origin or a
missing/incorrect CSRF token.

## Log out

Logout is a state-changing request, so send both the session cookie
automatically and the CSRF header. The backend revokes the Redis session and
clears the cookie.

```ts
export async function logout(): Promise<void> {
  if (!csrfToken) {
    await refreshCsrfToken();
  }

  const response = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: {
      "X-CSRF-Token": csrfToken!,
    },
  });

  if (!response.ok) {
    if (response.status === 401) {
      csrfToken = null;
      throw new Error("Your session has already expired.");
    }
    if (response.status === 403) {
      throw new Error("Logout failed origin or CSRF validation.");
    }
    throw new Error(`Logout failed (${response.status})`);
  }

  csrfToken = null;
}
```

Update the UI to signed-out state after successful logout. Do not clear cookies
from JavaScript; the backend's `Set-Cookie` deletion response does that.

## Browser and backend checklist

- The frontend's exact origin is in backend `CORS_ALLOWED_ORIGINS`.
- Credentialed CORS is enabled by the backend and the frontend uses
  `credentials: "include"` for login, session restore, protected requests, and
  logout.
- The browser accepts the session cookie. Check its storage and the request's
  cookies in developer tools; JavaScript cannot inspect an HTTP-only cookie.
- Every state-changing request includes the current `X-CSRF-Token`.
- Production frontend and API use HTTPS, particularly because the session
  cookie is configured `Secure` and `SameSite=None`.
- Never log passwords, session cookies, or CSRF tokens.
