# SimpleBank

A small REST API for bank accounts: register, log in, check your balance and history, and
send money to other users. Built with Django, Django REST Framework and PostgreSQL.

- Every new user gets an account with a unique 10-digit number and a €10,000 welcome bonus.
- Transfers cost 2.5% of the amount, at least €5.00, paid by the sender on top of the amount.
- Balances can never go wrong: transfers are atomic, row-locked and concurrency-tested, the
  database enforces the invariants, and every balance change is recorded in a ledger.

## Quick start

With Docker:

```bash
docker compose up --build
```

The API is at <http://localhost:8000/api/v1/>, with interactive docs at
<http://localhost:8000/api/docs/>.

Without Docker you need Python 3.12, [uv](https://docs.astral.sh/uv/) and PostgreSQL. The
default settings match the database that `docker compose up db` starts:

```bash
docker compose up -d db
uv sync
export DJANGO_DEBUG=true        # development mode, with a built-in secret key
uv run python manage.py migrate
uv run python manage.py runserver
```

To use other settings, copy `.env.example` to `.env`, edit it and pass it along with
`uv run --env-file .env ...`.

## Walkthrough

```bash
API=http://localhost:8000/api/v1

# Register two users; each gets an account with EUR 10,000.
curl -s -X POST $API/auth/register/ -H 'Content-Type: application/json' \
  -d '{"email": "alice@example.com", "password": "correct horse battery staple"}'
curl -s -X POST $API/auth/register/ -H 'Content-Type: application/json' \
  -d '{"email": "bob@example.com", "password": "correct horse battery staple"}'
# => {"id": 2, "email": "bob@example.com",
#     "account": {"number": "2717223670", "balance": "10000.00", "currency": "EUR"}}

# Log in as Alice.
TOKEN=$(curl -s -X POST $API/auth/token/ -H 'Content-Type: application/json' \
  -d '{"email": "alice@example.com", "password": "correct horse battery staple"}' | jq -r .access)

# Send Bob EUR 250. The fee is 6.25 (2.5%), so Alice pays 256.25.
curl -s -X POST $API/transfers/ -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: 5f1c9e0a' \
  -d '{"recipient_account": "2717223670", "amount": "250.00"}'
# => {"id": 1, "sender_account": "1224895911", "recipient_account": "2717223670",
#     "amount": "250.00", "fee": "6.25", "total": "256.25", "created_at": "..."}

# Balance and today's transactions.
curl -s $API/account/ -H "Authorization: Bearer $TOKEN"
curl -s "$API/account/transactions/?from=2026-09-28&to=2026-09-28" -H "Authorization: Bearer $TOKEN"
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register/` | Register with email and password; opens the funded account |
| `POST` | `/api/v1/auth/token/` | Log in: returns an `access` (30 min) and a `refresh` (1 day) JWT |
| `POST` | `/api/v1/auth/token/refresh/` | Exchange a refresh token for a new access token |
| `GET` | `/api/v1/account/` | Your account number, balance and currency |
| `GET` | `/api/v1/account/transactions/` | Your transactions, newest first; `from`, `to`, `limit`, `offset` |
| `POST` | `/api/v1/transfers/` | Send money to another account by its number |
| `GET` | `/api/v1/transfers/` | Transfers you sent or received |

All endpoints except registration and login require `Authorization: Bearer <access token>`.
The full OpenAPI schema is served at `/api/schema/` and rendered at `/api/docs/`.

**Money** is always a decimal string in EUR with two places, such as `"10000.00"`, so no
precision is lost to JSON floats.

**Transactions** carry `amount` (always positive), `type` (`credit` or `debit`), `kind`
(`welcome_bonus`, `transfer` or `transfer_fee`), `balance_after`, `timestamp` and, for
transfers, the `transfer` id and the `counterparty_account`.

**Date filters** `from` and `to` are inclusive and accept an ISO 8601 date-time or a plain
date. A date covers the whole day in UTC, so `?from=2026-03-01&to=2026-03-01` returns all of
1 March. Times without an offset are read as UTC.

**Errors** use DRF's format. Field errors look like `{"amount": ["..."]}`; other errors have
a `detail` message and a machine-readable `code`:

| Status | `code` | When |
| --- | --- | --- |
| 400 | – | Invalid input, unknown recipient, or a transfer to yourself |
| 401 | `not_authenticated`, `token_not_valid` | Missing, invalid or expired token |
| 404 | `not_found` | The user has no account (for example a staff user) |
| 409 | `insufficient_funds` | The balance does not cover the amount plus the fee |
| 422 | `idempotency_key_reused` | An `Idempotency-Key` was already used for a different transfer |

## Design

### Money

Amounts are `Decimal` in Python and whole cents in a `BIGINT` column. A small custom
`MoneyField` does the conversion, so application code never deals with cents or floats, and
it refuses sub-cent amounts instead of silently rounding them. The fee is
`max(round_half_up(amount * 2.5%), 5.00)`.

### Ledger

Balances live on `Account`, and every change to one is also written as an immutable
`Transaction` row that records the balance after it. A transfer creates a `Transfer` and
three ledger entries that point to it:

| Account | Type | Kind | Amount |
| --- | --- | --- | --- |
| Sender | debit | `transfer` | amount |
| Sender | debit | `transfer_fee` | fee |
| Recipient | credit | `transfer` | amount |

So each account's balance always equals its credits minus its debits, which the tests
check. The fee has its own line so users can see exactly what they paid.

### Atomic transfers

`banking.services.transfer_money` runs in a single database transaction:

1. Lock both account rows with `SELECT ... FOR UPDATE`, always in primary-key order, so two
   opposite transfers between the same accounts can never deadlock.
2. Check the balance covers amount plus fee, on the freshly locked row.
3. Update both balances, create the transfer and its three ledger entries.

Either everything is committed or nothing is. Concurrent transfers from the same account
queue on its row lock, so they cannot spend the same money twice. PostgreSQL also enforces
the rules itself with `CHECK` constraints: balances never negative, amounts positive,
sender and recipient different.

Registration is atomic the same way: the user, the account and the welcome bonus entry are
created together or not at all.

### Safe retries

A client whose transfer request times out cannot know whether the money moved. If it sends
an `Idempotency-Key` header, retrying with the same key returns the original transfer
(`200`) instead of sending the money again. The key lookup runs under the sender's row lock
and is backed by a unique constraint, so even simultaneous retries transfer exactly once.

### Layout

```
config/    settings (12-factor, from environment variables), URLs, DRF error and paging defaults
users/     custom User model with email login, registration, JWT token views
banking/   Account, Transfer and Transaction models, services, serializers, views, filters
```

Views stay thin: they validate input with serializers and call functions in
`banking/services.py` and `users/services.py`, where the business rules and transactions live.

## Development

```bash
uv run pytest               # the test suite needs PostgreSQL (see DATABASE_URL)
uv run ruff check .         # lint
uv run ruff format .        # format
uv run mypy .               # strict type checking with django-stubs
```

The tests cover the API end to end, the fee rule, the database constraints, rollback when a
transfer fails midway, and real concurrent transfers on PostgreSQL threads: they can neither
overdraw an account, deadlock, nor transfer twice for one idempotency key. Further tests
fail the build if a model change lacks a migration or the OpenAPI schema has warnings.
GitHub Actions runs linting, type checks and tests against PostgreSQL 16, and builds the
Docker image, on every push and pull request.

Configuration comes from environment variables (see `.env.example`): `DATABASE_URL`,
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG` and `DJANGO_ALLOWED_HOSTS`. The secret key also signs
the JWTs, so the app refuses to start without one unless `DJANGO_DEBUG` is on. The test
suite sets its own.

## Assumptions

- One EUR account per user. Money is sent to an account number, not an email address, as
  with an IBAN.
- The fee is charged to the sender on top of the amount; the recipient receives the full
  amount. A transfer needs a balance of at least amount plus fee.
- Staff users created with `createsuperuser` have no bank account; the admin shows accounts,
  transfers and transactions read-only, because balances only change through the services.
- Out of scope here but natural next steps: rate limiting login attempts, revoking refresh
  tokens on logout, and multiple currencies.
