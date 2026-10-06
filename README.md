# Zencraft Solution

Corporate website, lead-generation estimator, fixed-price service store, careers portal and hidden staff dashboard for Zencraft Solution, an IT services company in Lalitpur, Nepal.

Built with Django 5.2, PostgreSQL 16, Django REST Framework, vanilla JavaScript, GSAP 3.13 (ScrollTrigger, SplitText, Flip) and Three.js.

## Quick start (Windows, local)

```powershell
# 1. Install dependencies (Python 3.10+; 3.12 recommended for production)
pip install -r requirements.txt

# 2. Create the database in PostgreSQL 16 (port 5432)
psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE zencraft_db ENCODING 'UTF8';"

# 3. Configure environment
copy .env.example .env      # then edit DATABASE_URL, SECRET_KEY, DEBUG=True for local work

# 4. Create tables and load seed content (9 services, 7 industries, 48 technologies,
#    7 case studies, 7 jobs, 6 articles, rate card, store products, estimator engine)
python manage.py migrate
python manage.py seed_zencraft

# 5. Run
python manage.py runserver
```

Open http://127.0.0.1:8000.

The local `.env` in this repository points at `postgres://postgres:root@localhost:5432/zencraft_db`.

## Staff dashboard

- URL: `/hq/` (set with `DASHBOARD_PATH`). It is not linked from any public page and is excluded from the sitemap.
- Seed login: username `admin`, password from `ADMIN_SEED_PASSWORD` in `.env`. **Change it immediately** in production.
- Every dashboard view checks `is_staff` on the server. Signed-in non-staff users get a 404. Five failed logins lock the IP out for 15 minutes.
- Includes lead and recruitment kanban boards (drag and drop), in-browser CV preview, bulk status updates, CSV export, CRUD for all content, the estimator pricing engine, exchange rate, store orders, first-party analytics with estimator drop-off by step, and an audit log.
- Recommended for production: add `django-otp` for two-factor authentication and restrict `/hq/` by IP at the proxy.

## What lives where

| Area | App | Public URL |
| --- | --- | --- |
| Home, about, contact, consultation, legal, search | `apps.core` | `/`, `/about/`, `/contact/`, `/book-consultation/` |
| Services, industries, technologies | `apps.services` | `/services/`, `/services/industries/`, `/services/technologies/` |
| Case studies | `apps.portfolio` | `/work/` |
| Engagement models, rate card, store, cart, checkout | `apps.commerce` | `/pricing/`, `/pricing/store/` |
| Project estimator | `apps.estimator` | `/estimate/` |
| Careers and applications | `apps.careers` | `/careers/` |
| Blog | `apps.blog` | `/insights/` |
| Staff dashboard | `apps.dashboard` | `/hq/` |

## Commercial model

- **Engagement models and rates** are published openly (`/pricing/`). Fixed-price figures are shown as indicative ranges only.
- **Productized services** (help desk plans, website care, audits, assessments, discovery workshop) are sold through the cart.
- **The project estimator** is the main conversion path. Coefficients live in `EstimatorConfig`, `ProjectType` and `FeatureOption` and are editable at `/hq/estimator/`.

Money is stored as `DecimalField` in NPR. USD is derived from the exchange rate in Site settings and snapshotted onto every order and estimate. NPR uses South Asian grouping (`Rs. 8,00,000`).

## Payments

`apps/commerce/payments/` defines a `PaymentGateway` interface with eSewa (ePay v2 signed form), Khalti (ePayment API), Fonepay, Stripe Checkout (USD), bank transfer and invoice.

- Set `ESEWA_SECRET_KEY`, `ESEWA_PRODUCT_CODE`, `KHALTI_SECRET_KEY` or `STRIPE_SECRET_KEY` to enable a live gateway. The `.env` ships with the public eSewa test credentials.
- A gateway without credentials uses a local sandbox simulator, available only while `DEBUG=True`.
- Replace the placeholder bank account details in `templates/commerce/order_done.html` with the company's real account before launch.

## Careers and CV privacy

- Candidates can **upload a CV** (PDF or DOCX, max 5 MB) or **fill in their CV manually** (profile, experience, education, projects).
- Uploads are validated by file contents (PDF header, DOCX zip structure), not only by extension, and then virus-scanned through `UPLOAD_SCAN_HOOK` (ClamAV by default, see below).
- CVs and requirement documents are saved under `private_media/` with random names. They have no public URL and are streamed only through staff-only views that write to the audit log.
- Schedule `python manage.py purge_applications` daily. It removes CV files and personal data from rejected applications older than `CV_RETENTION_DAYS` (default 180).

## Virus scanning with ClamAV (required in production)

Every CV and requirements document is streamed to a ClamAV daemon before it is saved (`apps.core.uploads.clamav_scan`).

- With `DEBUG=False`, `UPLOAD_SCAN_HOOK` defaults to `clamav_scan`. Setting it to `noop_scan` makes Django refuse to start.
- The scan **fails closed**: if the daemon is unreachable or returns an error, the upload is rejected with a "try again later" message and the error is logged.
- Local development with `DEBUG=True` defaults to `noop_scan`, so you do not need ClamAV installed to work on the site.

Set up on Ubuntu or Debian:

```bash
sudo apt-get install -y clamav-daemon clamav-freshclam
sudo systemctl stop clamav-freshclam && sudo freshclam && sudo systemctl start clamav-freshclam   # first signature download
sudo systemctl enable --now clamav-daemon
# Allow the Django user to read the socket
sudo usermod -aG clamav www-data
```

Then in `.env`:

```
UPLOAD_SCAN_HOOK=apps.core.uploads.clamav_scan
CLAMAV_UNIX_SOCKET=/var/run/clamav/clamd.ctl
```

Or, with Docker, run `docker run -d --name clamav -p 3310:3310 clamav/clamav:stable` and set `CLAMAV_HOST=127.0.0.1` and `CLAMAV_PORT=3310` (leave `CLAMAV_UNIX_SOCKET` empty). The daemon needs about 1 GB of RAM for signatures and a minute or two to load after starting.

Check it end to end with the harmless EICAR test string. Uploading a `.pdf` whose content starts with `%PDF-` followed by the EICAR string should be rejected with "The file could not be accepted by our security scan."

## Login lockout, proxies and the shared cache

Login lockouts (5 failures, 15 minutes) and every rate limit are keyed by the visitor's IP
address and stored in the cache, so both have to be configured correctly or they protect nothing.

### TRUSTED_PROXY_COUNT

Each reverse proxy in front of Django appends the address it received the request from to
`X-Forwarded-For`. Entries further left are whatever the client sent, so they cannot be trusted.
`TRUSTED_PROXY_COUNT` says how many entries to count from the right.

| Deployment | Value |
| --- | --- |
| `manage.py runserver`, or gunicorn exposed directly | `0` |
| **Render** | `1` |
| nginx or another single proxy in front of gunicorn | `1` |
| CDN (Cloudflare, Fastly) in front of Render | `2` |

**Verify it after the first deploy** rather than assuming:

1. Find your own public address at <https://ifconfig.me>.
2. Sign in to the staff dashboard from that network, then open **Audit log**.
3. Compare the IP recorded against your real one.
   - They match: the value is right.
   - A private address (`10.x.x.x`, `172.16-31.x.x`) or Render's load balancer: the value is
     **too low**, so every visitor is sharing one address. Increase it by one and redeploy.
   - An address you do not recognise that changes when you change the `X-Forwarded-For` header
     by hand: the value is **too high** and visitors can spoof it. Decrease it.

### CACHE_URL

`LocMemCache` lives inside one gunicorn worker and is wiped on restart, so an attacker could
reset a lockout by retrying until another worker answered. It is therefore used only when
`DEBUG=True`.

- **Leave `CACHE_URL` empty in production** and the database cache is used. The build command
  must run `python manage.py createcachetable`.
- **Set `CACHE_URL=redis://...`** (or `rediss://` for TLS) once you add a Redis instance. This is
  faster and is the better choice as soon as traffic grows.

A deploy check refuses to start a production deployment that is still on LocMem.

The HQ dashboard login and the Django admin login share one IP-keyed lockout
(`LOGIN_MAX_FAILURES`, default 5, over `LOGIN_LOCKOUT_SECONDS`, default 900).

## Front end and motion

- `static/css/main.css`: design tokens (white, near-black and one blue accent, navy for the footer and CTA band), type scale, components.
- `static/js/main.js`: shared motion tokens (`power3.out` entrances, `power2.inOut` transitions, 0.3 / 0.6 / 1.2 s durations, 0.08 s stagger), SplitText hero headlines, scroll reveals, counters, scroll-drawn process lines, the pinned horizontal case-study gallery, Flip morph from case card to case page, testimonial crossfade, page crossfades and footer parallax.
- `static/js/hero3d.js`: Three.js node network, lazy-loaded when the hero is in view. Pixel ratio capped at 2, paused off-screen, skipped on low-end devices, with a static SVG diagram fallback.
- `prefers-reduced-motion: reduce` gives a static page: no SplitText, no pinning, no counters, instant content.
- Content is only hidden for animation after GSAP has loaded. If a CDN fails, the page stays fully readable.
- Images are loaded from Unsplash, logos from Simple Icons and Devicon. A fallback script swaps any broken image for a placeholder.

## Tests

```powershell
python manage.py test apps.core
```

22 tests cover every public page, the nine service pages' depth, the estimator (including private document upload), both application paths and fake-file rejection, cart to paid order through the sandbox, dashboard access control, kanban status API, CV access audit logging, estimator configuration and login rate limiting.

## Deploying to Render

`render.yaml` describes the whole deployment: the web service, a PostgreSQL 16 database and two
cron jobs. From the Render dashboard choose **New > Blueprint** and point it at this repository.
Every value marked `sync: false` in that file is a secret you fill in once, in the dashboard.

### The build command, and why each line is there

```
pip install -r requirements.txt
python manage.py collectstatic --noinput   # WhiteNoise serves hashed files; without this there is no CSS
python manage.py migrate --noinput         # schema, and the data migrations that carry content changes
python manage.py createcachetable          # the default cache is the database; lockouts live there
python manage.py ensure_superuser          # first admin only; a no-op afterwards
```

Leaving out `createcachetable` makes every sign-in and every form submission error, because the
rate limiter cannot reach its table. Leaving out `migrate` makes the deploy fail outright.

### Environment variables

The site refuses to start a production deployment that is quietly broken: `manage.py check
--deploy` fails with a `zencraft.E00x` code if media would be lost on redeploy, email would be
printed instead of sent, lockout counters would reset, or `SITE_URL` points at localhost. That is
deliberate, and the fix is always to set the variable below.

| Variable | What it does | Example |
| --- | --- | --- |
| `SECRET_KEY` | Signs sessions and CSRF tokens. Render can generate it. | *(generated)* |
| `DEBUG` | Must be `False` in production. | `False` |
| `ALLOWED_HOSTS` | Hostnames this site answers to. | `zencraftsolution.com,www.zencraftsolution.com,zencraft-solution.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | Origins allowed to post forms. | `https://zencraftsolution.com,https://www.zencraftsolution.com` |
| `SITE_URL` | Canonical tags, sitemap, emails, payment returns. **Must be https and not localhost.** | `https://zencraftsolution.com` |
| `DATABASE_URL` | From the Render database. | *(linked)* |
| `TRUSTED_PROXY_COUNT` | How many proxies append to `X-Forwarded-For`. **`1` on Render.** | `1` |
| `CACHE_URL` | Empty uses the database cache. Set to `redis://…` once you add Redis. | *(empty)* |
| `DASHBOARD_PATH` | Where the staff dashboard is mounted. Pick something unguessable. | `hq-7x2k/` |
| `CLOUDINARY_CLOUD_NAME` / `_API_KEY` / `_API_SECRET` | Public images. **Required**: the container disk is wiped on every deploy. | `zencraft` |
| `PRIVATE_STORAGE_BACKEND` | Where CVs live: `s3` or `local`. | `s3` |
| `PRIVATE_S3_BUCKET` | Bucket for CVs and requirement documents. | `zencraft-private` |
| `PRIVATE_S3_REGION` | Region, or `auto` for Cloudflare R2. | `auto` |
| `PRIVATE_S3_ENDPOINT_URL` | Blank for AWS; the account endpoint for R2 or Spaces. | `https://abc123.r2.cloudflarestorage.com` |
| `PRIVATE_S3_ACCESS_KEY` / `_SECRET_KEY` | Credentials for that bucket. | |
| `PRIVATE_MEDIA_PERSISTENT` | Only with `PRIVATE_STORAGE_BACKEND=local`, and only if a real disk is mounted. | `False` |
| `UPLOAD_SCAN_MODE` | `quarantine` on a plain web service, `strict` if ClamAV is reachable. | `quarantine` |
| `CLAMAV_HOST` / `CLAMAV_PORT` | The ClamAV daemon, for whichever service does the scanning. | `clamav:3310` |
| `EMAIL_URL` | SMTP connection. Without it, nothing is sent. | `smtp+tls://apikey:SG.xxx@smtp.sendgrid.net:587` |
| `DEFAULT_FROM_EMAIL` | The From address on every message. | `Zencraft Solution <hello@zencraftsolution.com>` |
| `INTERNAL_NOTIFY_EMAIL` | Where new leads and applications are announced. | `team@zencraftsolution.com` |
| `EMAIL_TIMEOUT` | Seconds before a slow mail server is given up on. | `10` |
| `STAFF_SESSION_HOURS` | How long a staff session lasts after signing in. | `8` |
| `STAFF_2FA_REQUIRED` | Enrol everyone at **HQ > Security** first, then set this. | `False` |
| `CSP_REPORT_ONLY` | `True` reports violations without blocking. Use it for one deploy, then turn it off. | `False` |
| `CSP_REPORT_URI` | Optional endpoint collecting those reports. | |
| `CAREERS_REAPPLY_DAYS` | How long before the same address may apply for a role again. | `30` |
| `CV_RETENTION_DAYS` | Unsuccessful applications are erased after this. | `180` |
| `INQUIRY_RETENTION_DAYS` | Inquiries that never became projects are erased after this. | `730` |
| `LOG_FORMAT` | `json` in production, `text` locally. | `json` |
| `SENTRY_DSN` | Optional error reporting, scrubbed of personal data. | |
| `ESEWA_*`, `KHALTI_*`, `STRIPE_SECRET_KEY` | Live payment credentials. | |
| `DJANGO_SUPERUSER_*` | The first admin account. Change the password after signing in. | |

### Health check

Set Render's **Health Check Path** to `/healthz/`. It checks the database and the cache and
returns `{"status": "ok"}` with a 200, or 503 naming the failing component. It does nothing
heavier on purpose: a health check that calls a payment gateway takes your site offline whenever
that gateway has a bad minute.

### Scheduled jobs

| Job | Schedule | Why it matters |
| --- | --- | --- |
| `scan_quarantined_uploads --retry-errors` | every 10 minutes | Releases uploaded CVs to the hiring team. **Until it runs, a CV cannot be opened.** |
| `purge_applications` | daily | Enforces the retention periods the privacy policy promises. |

The scanning job needs ClamAV on whichever service runs it. On Render, add
`apt-get install -y clamav clamav-daemon && freshclam` to that service's build, or run ClamAV as a
separate private service and point `CLAMAV_HOST` at it.

### Moving CVs to object storage

Existing CVs are on the container disk and will not be there after the next deploy. With the
`PRIVATE_S3_*` variables set and the old disk still mounted:

```
python manage.py migrate_private_files --dry-run   # see what would move
python manage.py migrate_private_files             # copy, without deleting anything
python manage.py migrate_private_files --verify    # confirm every file arrived
```

Only then set `PRIVATE_STORAGE_BACKEND=s3` permanently and remove the disk.

### Why email is sent during the request, and not from a queue

Sending is wrapped by `apps/core/mail.py`, which never raises and always logs, and
`EMAIL_TIMEOUT` is 10 seconds against a 30 second gunicorn timeout. The worst case is that a
visitor waits a few extra seconds and the failure appears in the log with its reference, rather
than the submission being lost. At this volume a worker process, its queue and its own failure
modes would cost more than they save. Virus scanning, which really is slow and really can fail,
is already off the request path via `UPLOAD_SCAN_MODE=quarantine`.

Revisit this if the site starts sending in bulk, or if a provider's API replaces SMTP.

## Deployment checklist

1. `DEBUG=False`, a long random `SECRET_KEY`, real `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
2. PostgreSQL with backups. Keep `private_media/` on persistent, backed-up storage outside the web root.
3. `python manage.py collectstatic`, then serve `staticfiles/` with WhiteNoise or Nginx.
4. Run behind Nginx with HTTPS. HSTS, secure cookies and SSL redirect switch on automatically when `DEBUG=False`.
5. Configure SMTP through `EMAIL_URL` (SendGrid or Mailgun) and set `INTERNAL_NOTIFY_EMAIL`.
6. Use Redis for `CACHES` so rate limits are shared across workers.
7. Change the admin password, enable two-factor authentication and schedule `purge_applications`.
8. Replace seed statistics, testimonials, bank details and team data with verified company information.
