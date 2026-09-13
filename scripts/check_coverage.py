"""Enforce a per-app coverage floor on the highest-consequence apps.

`coverage report --fail-under` only checks the combined total, which lets a well-tested app hide a poorly
tested one. This checks each app on its own. Run after `pytest --cov`:

    python scripts/check_coverage.py            # default floor 85
    python scripts/check_coverage.py --floor 90
"""
import argparse
import io
import sys

import coverage

CRITICAL_APPS = {
    "commerce": "money: cart, checkout, payment gateways",
    "careers": "PII: applications and CV uploads",
    "dashboard": "admin access and private file serving",
    "core": "uploads, virus scanning, throttling, rate limits",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--floor", type=float, default=85.0)
    args = parser.parse_args()

    cov = coverage.Coverage()
    cov.load()
    failures = []
    print(f"Per-app coverage floor: {args.floor:.0f}%")
    for app, why in CRITICAL_APPS.items():
        pct = cov.report(include=[f"apps/{app}/*"], file=io.StringIO())
        status = "ok" if pct >= args.floor else "BELOW FLOOR"
        print(f"  apps/{app:<10} {pct:5.1f}%  {status:<12} ({why})")
        if pct < args.floor:
            failures.append(app)
    if failures:
        print(f"Coverage below {args.floor:.0f}% for: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
