# Deploying Taxlify (Railway)

The app is a standard 12-factor Flask app: **web** (gunicorn) + **worker** (Celery
worker with embedded beat) + **Redis** (broker) + **Supabase Postgres** (already
live). The repo is deploy-ready — `Procfile`, `gunicorn`, migrations-on-boot, and
`REDIS_URL` fallback are all in place. You drive the Railway side (I can't log in
to your account).

## Prerequisites
- GitHub repo: `raphirudin-cpu/taxlify.app` (pushed).
- Supabase Postgres (your existing project) — the `DATABASE_URL`.
- A Railway account.
- A working SMTP sender for confirmation emails + the weekly digest (a Gmail app
  password, or a transactional provider like Resend/SendGrid/Mailgun).

## Steps

1. **Create the project** — Railway → *New Project* → *Deploy from GitHub repo* →
   pick `taxlify.app`. Railway reads the `Procfile` and starts the **web** process.

2. **Add Redis** — in the project, *New* → *Database* → *Redis*. This creates a
   `REDIS_URL` variable you can reference from the other services.

3. **Add the worker service** — *New* → *GitHub Repo* → same repo → in its
   settings set the **Custom Start Command** to:
   ```
   celery -A app.celery worker --beat --loglevel=info
   ```
   (`--beat` runs the weekly-digest scheduler in the same process — fine for one
   worker. If you ever scale to >1 worker, split beat into its own service with
   `celery -A app.celery beat --loglevel=info` so the digest doesn't fire twice.)

4. **Set environment variables** — on **both** the web and worker services
   (use Railway *shared variables* so you set them once):

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | your Supabase connection string (the app normalizes it for psycopg2) |
   | `SECRET_KEY` | a fresh long random string |
   | `APP_ENV` | `production` |
   | `REDIS_URL` | reference the Redis service (`${{Redis.REDIS_URL}}`) — the app falls back to it for Celery |
   | `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` | your SMTP sender |
   | `MAIL_DEFAULT_SENDER` | the from-address |
   | `ANTHROPIC_API_KEY` | your key (enables AI document analysis) |
   | `SERVER_NAME` | the app's public domain (set after step 6) |
   | `PREFERRED_URL_SCHEME` | `https` |
   | `AUTO_CONFIRM_EMAIL` | `false` (real email confirmation in prod) |

5. **Persist uploads (important)** — attach a Railway **Volume** to the **web**
   service, mounted at the uploads directory:
   ```
   /app/app/uploads
   ```
   (`upload_path` = `<app package>/uploads`; on Railway the repo is at `/app`, the
   Flask package is `app/`, so uploads live at `/app/app/uploads`. Confirm the path
   in the deploy logs on first run.) **Without a volume, every client-uploaded
   document is lost on the next deploy/restart** — the container disk is ephemeral.
   The worker doesn't touch uploads, so it needs no volume.

6. **Deploy & wire the domain** — Railway builds and starts the web process, which
   runs `flask db upgrade` (applies migrations) then gunicorn. Generate a domain
   (*Settings → Networking → Generate Domain*), set `SERVER_NAME` to it, and
   redeploy so email links point at the right host.

## Post-deploy smoke test
- Open the domain → register → you should receive a confirmation email → confirm →
  log in.
- Upload a document → redeploy → confirm it's still there (verifies the volume).
- Check the worker logs show the beat scheduler started (`celery beat`).

## Known limitations / follow-ups
- **Uploads on a volume, not object storage.** The Railway volume works, but a
  single-node volume doesn't scale horizontally and isn't backed up. For real
  client documents, move storage to **Supabase Storage / S3** (a follow-up feature).
- **Email deliverability.** Gmail app passwords work for low volume; a transactional
  provider with SPF/DKIM is better for confirmation + digest emails at scale.
- **Migrations run on web boot.** If you prefer a release phase, move
  `flask db upgrade` out of the `web` Procfile line into a Railway *pre-deploy*
  command.

## Other hosts
The same `Procfile` + gunicorn setup works on Render or Fly.io — create a web
service (Procfile `web`), a background worker (Procfile `worker`), and a Redis
add-on, then set the same env vars. Only the volume/persistence UI differs.
