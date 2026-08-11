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

## Notes
- `.env`, `uploads/`, `app/uploads/`, and `*.rdb` are git-ignored — never commit
  secrets or client tax documents.
- Debug mode is **off** unless `FLASK_DEBUG=1`. Never enable it in production.
