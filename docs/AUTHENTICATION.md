# Authentication

OptionsLab uses **JWT (JSON Web Token)** bearer-token authentication. Every API route that reads or writes user-specific data requires a valid token. The web dashboard stores the token in `localStorage` and attaches it automatically to every API request.

---

## Quick start

1. Start the API and frontend.
2. Open [http://localhost:3000](http://localhost:3000) — you are redirected to `/login`.
3. Click **"Create one"** to go to `/register` and create your account.
4. After registration you are logged in automatically and redirected to the dashboard.
5. Your session lasts **24 hours**. When it expires the app redirects you to `/login`.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET_KEY` | **Recommended** | Secret used to sign tokens. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. Falls back to a hard-coded dev key if unset — **set this in production**. |

Add it to your `.env` (do not commit):

```bash
JWT_SECRET_KEY=<your-32-byte-hex-string>
```

---

## API endpoints

All auth endpoints are under the `/auth` prefix and do **not** require a token.

### `POST /auth/register`

Create a new user account.

**Request body:**
```json
{ "email": "you@example.com", "password": "atleast8chars" }
```

**Response (201):**
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

**Errors:**
- `409 Conflict` — email already registered.
- `422 Unprocessable Entity` — password shorter than 8 characters.

---

### `POST /auth/login`

Exchange credentials for a JWT.

**Request body:**
```json
{ "email": "you@example.com", "password": "yourpassword" }
```

**Response (200):**
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

**Errors:**
- `401 Unauthorized` — invalid email or password.

---

### `GET /auth/me`

Return the authenticated user's info.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{ "id": 1, "email": "you@example.com" }
```

---

## Using the token in API calls

All protected routes require the `Authorization` header:

```
Authorization: Bearer <access_token>
```

The web frontend handles this automatically. For CLI or script access:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl http://localhost:8000/user/settings \
  -H "Authorization: Bearer $TOKEN"
```

---

## Token lifetime and renewal

Tokens expire after **24 hours**. There is no refresh-token mechanism — simply log in again to get a new token.

The frontend detects expiry both client-side (by reading the `exp` claim in the JWT payload) and server-side (via the `401` response). Either way it clears the stored token and redirects to `/login`.

---

## Password security

Passwords are hashed with **bcrypt** (cost factor 12, via the `bcrypt` library) before storage. Plain-text passwords are never persisted.

The `password_hash` column in the `users` table always contains a bcrypt digest. An empty hash (`""`) is never used for real accounts.

---

## Protected routes

The following routes require authentication (401 if no valid token is provided):

| Prefix | Router | Notes |
|---|---|---|
| `GET /user/settings`, `PUT /user/settings` | user_settings | Per-user API key and broker settings |
| `DELETE /symbols/{symbol}` | contracts | Destructive data operation |
| `/lab/etrade/*` | etrade_trading | Live trading actions |
| `/lab/etrade/oauth/*` | etrade_oauth | OAuth token exchange |
| `/lab/alpaca/*` | alpaca_trading | Paper trading actions |
| `/lab/sync` | sync | Data sync trigger |
| `/lab/backtests/*` | backtests_lab | Saved backtest read/write |
| `/lab/strategy-engine/*` | strategy_engine | Forecast-based evaluation |
| `/economic/*` | economic | Macro data (per-user API keys) |
| `/forecasting/*` | forecasting | TSF runs and evaluation |
| `/research/*` | research | LLM explanations |
| `GET /auth/me` | auth | Self-info endpoint |

The following routes are intentionally **unauthenticated** (read-only, non-sensitive):

| Route | Reason |
|---|---|
| `GET /` | Health / API info |
| `GET /symbols`, `GET /contracts`, `GET /bars` | Public market data |
| `GET /strategies` | Strategy list |
| `POST /backtests/run` | Legacy backtest runner |

---

## Testing

The test suite overrides `get_current_user` with `get_default_user` for the default `client` fixture so existing tests pass without a JWT. A separate `unauthed_client` fixture tests the real JWT flow:

```python
# tests/test_api.py

@pytest.fixture
def client(fresh_storage_file):
    from api.main import app
    from api import auth_utils
    app.dependency_overrides[auth_utils.get_current_user] = auth_utils.get_default_user
    ...

@pytest.fixture
def unauthed_client(fresh_storage_file):
    # No override — real JWT validation
    ...
```

Auth-specific tests:
- `test_auth_register_and_login` — register, login, call `/auth/me`.
- `test_auth_wrong_password_returns_401`
- `test_auth_duplicate_register_returns_409`
- `test_protected_route_without_token_returns_401`
- `test_protected_route_with_valid_token`

---

## Security notes

- **Set `JWT_SECRET_KEY`** in production. The dev fallback secret is public and must not be used in any internet-facing deployment.
- **CORS** is controlled by the `ALLOWED_ORIGINS` environment variable (comma-separated list). Defaults to `"*"` for local/LAN use. In production (deployed via CDK), the `ApiStack` sets `ALLOWED_ORIGINS` to the Amplify URL automatically. For custom deployments, set `ALLOWED_ORIGINS=https://your-app.example.com` in the API environment.
- **Credential storage:** broker API keys (E\*TRADE, Alpaca, FRED, etc.) are stored as JSON in the `settings_json` column of the `users` table. They are encrypted in transit (HTTPS) but stored in plaintext in the database. Enable database-level encryption at rest or use a secrets manager for high-value deployments.
- **Multi-user:** The schema supports multiple accounts. Each user has their own `settings_json` and backtests. Share the app with team members by giving each person their own account.
