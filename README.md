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
- Uploads are validated by file contents (PDF header, DOCX zip structure), not only by extension, and pass through `UPLOAD_SCAN_HOOK` so a virus scanner can be plugged in.
- CVs and requirement documents are saved under `private_media/` with random names. They have no public URL and are streamed only through staff-only views that write to the audit log.
- Schedule `python manage.py purge_applications` daily. It removes CV files and personal data from rejected applications older than `CV_RETENTION_DAYS` (default 180).

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

## Deployment checklist

1. `DEBUG=False`, a long random `SECRET_KEY`, real `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
2. PostgreSQL with backups. Keep `private_media/` on persistent, backed-up storage outside the web root.
3. `python manage.py collectstatic`, then serve `staticfiles/` with WhiteNoise or Nginx.
4. Run behind Nginx with HTTPS. HSTS, secure cookies and SSL redirect switch on automatically when `DEBUG=False`.
5. Configure SMTP through `EMAIL_URL` (SendGrid or Mailgun) and set `INTERNAL_NOTIFY_EMAIL`.
6. Use Redis for `CACHES` so rate limits are shared across workers.
7. Change the admin password, enable two-factor authentication and schedule `purge_applications`.
8. Replace seed statistics, testimonials, bank details and team data with verified company information.
