# Setup — Simplify Taxes (Supabase / Postgres)

## 1. Create the Supabase project
1. Go to https://supabase.com → **New project**. Pick a name, region, and a
   strong database password (save it).
2. Once the project is ready: **Project Settings → Database → Connection string
   → URI**. Choose **Session pooler** (port `5432`) for a long-running web app.
   It looks like:
   ```
   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```

## 2. Configure environment
```bash
cp .env.example .env
```
Then edit `.env` and set at minimum:
- `SECRET_KEY` — generate one:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- `DATABASE_URL` — the Supabase URI from step 1.
- `MAIL_USERNAME` / `MAIL_PASSWORD` — a **new** Gmail App Password
  (the one previously in source control must be rotated).

> The app refuses to start if `SECRET_KEY`, `DATABASE_URL`, `MAIL_USERNAME`,
> or `MAIL_PASSWORD` are missing — this is intentional (no insecure fallbacks).

## 3. Install dependencies
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## 4. Create the database schema (Alembic migrations)
The migrations — including the **initial schema** — are already committed under
`migrations/`. Just apply them to your (empty) Supabase database:
```bash
export FLASK_APP=run.py
flask db upgrade
```
This creates all tables and the Postgres enum types. Do **not** run
`flask db migrate` on the fresh DB — the initial migration already exists and a
second one would duplicate it.

For every later model change: `flask db migrate -m "describe change"` then
`flask db upgrade`, and commit the new file in `migrations/versions/`.

## 5. Run
```bash
# 1) Redis (broker for Celery emails)
redis-server

# 2) Celery worker (separate terminal)
celery -A app.celery worker --loglevel=info

# 3) Web app
python run.py            # http://localhost:5050
```

## 6. Run the tests
The suite is self-contained — it uses a throwaway SQLite database and sets its
own environment, so it needs **no** Supabase connection or secrets:
```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```
The same two commands run automatically on every push/PR via
[.github/workflows/ci.yml](.github/workflows/ci.yml). The tests pin the
authorization boundaries (IDOR downloads, role gating, advisor–client binding,
CSRF), so a change that re-opens one of those holes will fail CI.

## Deploying to Railway

The app runs as **two long-running services** off the same repo, plus a Redis
plugin. Celery is NOT started by the web process — it's its own service.

```
web service     → gunicorn (Flask)  ─┐
worker service  → celery worker      ─┼─► Redis (Railway plugin, the broker)
                                      └─► Supabase (Postgres, external)
```

### 1. Redis
Add Railway's **Redis** plugin to the project. It exposes `REDIS_URL`.

### 2. Web service
From your GitHub repo. Start command (already in the `Procfile` as `web`):
```
FLASK_APP=run.py flask db upgrade && gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```
`flask db upgrade` applies any pending migrations on deploy. (If you run
multiple web replicas, run migrations as a one-off from the Railway shell
instead, to avoid replicas racing.)

### 3. Worker service
Add a **second service from the same repo**, and set its start command to the
`worker` line:
```
celery -A app.celery worker --loglevel=info
```
(Plain prefork pool — the `--pool=solo` workaround is only for local macOS.)

### 4. Environment variables — set on BOTH services
```
SECRET_KEY=<strong random>
DATABASE_URL=<your Supabase URI>
MAIL_USERNAME=info@taxlify.app
MAIL_PASSWORD=<gmail app password>
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
APP_ENV=production
FLASK_DEBUG=0
SERVER_NAME=<your public domain, e.g. taxlify.app>
PREFERRED_URL_SCHEME=https
```

> **`SERVER_NAME` is required** so the email tasks can build absolute
> confirmation/reset links (`url_for(_external=True)`). It must exactly match the
> domain Railway serves, or Flask will reject requests with a mismatched Host.

That's the whole deployment. reportlab (the only PDF lib) is pure-Python, so no
system packages / Nixpacks config are needed.

## Observability
- **Sentry** is optional and off by default. Set `SENTRY_DSN` in `.env` (from your
  Sentry project) to enable error alerts. PII is never sent (`send_default_pii=False`).
- **File logs** (tracebacks/debug) write to `logs/taxlify.log` (rotating). Tune with
  `LOG_LEVEL` / `LOG_DIR`. `logs/` is git-ignored.
- **Audit trail**: user actions (login, register, quote/document/return decisions,
  account deletion) are recorded in the `audit_log` table via `app/audit.py`.

## Notes
- `.env`, `uploads/`, `app/uploads/`, `logs/`, and `*.rdb` are git-ignored — never
  commit secrets or client tax documents.
- Debug mode is **off** unless `FLASK_DEBUG=1`. Never enable it in production.
- **Uploaded files**: `uploads/` is on local disk. Railway's filesystem is
  ephemeral (wiped on redeploy), so attach a **Railway Volume** (or move to
  Supabase Storage / S3) if you need uploaded documents to persist.
