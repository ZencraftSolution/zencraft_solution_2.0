# Load testing

## Never run this against production

`Enquirer` submits the contact form. Against production that creates real records, sends real
email to your team, and burns the rate limit for whatever IP you run it from — which on Render
is shared, so you would be locking out real visitors.

Point it at a staging service with its own database. If you have no staging service, run it
against your own machine (`python manage.py runserver`) and treat the numbers as relative.

## Running it

```bash
pip install locust

# A browser dashboard at http://localhost:8089, where you set the numbers by hand.
locust -f loadtest/locustfile.py --host https://zencraft-staging.onrender.com

# Or a fixed run with no browser, which is what you want in a terminal or a pipeline.
locust -f loadtest/locustfile.py --host https://zencraft-staging.onrender.com \
       --headless --users 50 --spawn-rate 5 --run-time 5m --csv loadtest/results
```

`--users 50` is a reasonable first number for a Render starter instance running two gunicorn
workers with four threads each. Start lower than you think and climb: the point is to find where
it bends, not to prove a number you picked first.

## The two profiles

| Profile | Share of users | What it does | Writes? |
| --- | --- | --- | --- |
| `Reader` | 80% | Home, service pages, case studies, pricing, articles, jobs | No |
| `Enquirer` | 20% | Contact form, estimator, search | Yes |

The weighting is a guess at how a small agency site is actually used. Change it to match your
analytics once you have some.

## What to watch

| Number | Where | What it means |
| --- | --- | --- |
| p95 response time | Locust | The slow end of what a real visitor feels. Under 800 ms for a page is comfortable. |
| Failures | Locust | Anything above zero needs explaining before the numbers mean anything. |
| 429 responses | Locust, by endpoint | The rate limiter doing its job. Expected on `POST /contact/` under load. |
| CPU and memory | Render dashboard | A worker running out of memory shows up as failures, not as slowness. |
| Database connections | Render dashboard | `CONN_MAX_AGE=60` holds connections open; a small plan runs out before CPU does. |
| Log volume | Render logs | JSON logs at this rate are not free. |

## Reading a result

- **Response times climb but failures stay at zero** — you are at the instance's limit.
  More workers or a bigger instance.
- **Failures appear with no slowdown** — something is erroring rather than queueing. Look at the
  logs for the request ID of a failed request.
- **`/healthz/` slows down with everything else** — the database or the cache is the limit, not
  the application.
- **`POST /contact/` returns 429 quickly** — expected. The limit is 5 per 15 minutes per IP, and
  every simulated user shares one address.

## What this does not measure

Payment gateways are not exercised: the sandbox endpoints belong to eSewa, Khalti and Stripe,
and hammering them is both rude and meaningless. CV uploads are also left out, because they
would fill the private bucket with rubbish. Both are worth testing by hand before launch.
