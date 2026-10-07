"""Enforce coverage floors: one per app, and a stricter branch floor on the dangerous modules.

`coverage report --fail-under` only checks the combined total, which lets a well-tested app hide
a poorly tested one. Line coverage on its own is also not enough for code that decides about
money or access: "if the signature is valid" counts as covered when only the valid path has ever
run, which is exactly the half that does not matter.

Run after `pytest --cov` (branch = True is set in .coveragerc):

    python scripts/check_coverage.py                       # 85% per app, 90% branch elsewhere
    python scripts/check_coverage.py --floor 90 --branch-floor 95
"""
import argparse
import fnmatch
import io
import json
import sys
import tempfile
from pathlib import Path

import coverage

CRITICAL_APPS = {
    "commerce": "money: cart, checkout, payment gateways",
    "careers": "PII: applications and CV uploads",
    "dashboard": "admin access and private file serving",
    "core": "uploads, virus scanning, throttling, rate limits",
}

# Modules where a missed branch is a missed decision about money or access.
BRANCH_CRITICAL = {
    "apps/commerce/payments/*": "verifying what a payment gateway sent back",
    "apps/commerce/cart.py": "what a customer is about to be charged",
    "apps/commerce/views.py": "checkout and the payment callback",
    "apps/core/throttle.py": "the login lockout",
    "apps/core/uploads.py": "file validation and virus scanning",
    "apps/dashboard/mixins.py": "who is allowed into the dashboard",
}


def line_percentage(cov, include):
    return cov.report(include=[include], file=io.StringIO(), show_missing=False)


def branch_report(cov):
    """Per-file branch totals, from coverage's own JSON report rather than its internals."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "coverage.json"
        cov.json_report(outfile=str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
    return {name.replace("\\", "/"): entry["summary"] for name, entry in data.get("files", {}).items()}


def branch_percentage(files, pattern):
    """Of the decisions in the files matching this pattern, how many went both ways."""
    taken = possible = 0
    for name, summary in files.items():
        if not (fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(name, f"*/{pattern}")):
            continue
        possible += summary.get("num_branches", 0)
        taken += summary.get("covered_branches", 0)
    if not possible:
        return None
    return 100.0 * taken / possible


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--floor", type=float, default=85.0, help="line coverage, per app")
    parser.add_argument("--branch-floor", type=float, default=90.0, help="branch coverage, money and access code")
    args = parser.parse_args()

    cov = coverage.Coverage()
    cov.load()
    failures = []

    print(f"Per-app line coverage floor: {args.floor:.0f}%")
    for app, why in CRITICAL_APPS.items():
        pct = line_percentage(cov, f"apps/{app}/*")
        status = "ok" if pct >= args.floor else "BELOW FLOOR"
        print(f"  apps/{app:<10} {pct:5.1f}%  {status:<12} ({why})")
        if pct < args.floor:
            failures.append(f"apps/{app} line {pct:.1f}%")

    files = branch_report(cov)
    print(f"\nBranch coverage floor on money and access code: {args.branch_floor:.0f}%")
    for pattern, why in BRANCH_CRITICAL.items():
        pct = branch_percentage(files, pattern)
        if pct is None:
            print(f"  {pattern:<28}     -  no branch data (is branch = True set in .coveragerc?)")
            failures.append(f"{pattern} has no branch data")
            continue
        status = "ok" if pct >= args.branch_floor else "BELOW FLOOR"
        print(f"  {pattern:<28} {pct:5.1f}%  {status:<12} ({why})")
        if pct < args.branch_floor:
            failures.append(f"{pattern} branch {pct:.1f}%")

    if failures:
        print("\nBelow floor:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
