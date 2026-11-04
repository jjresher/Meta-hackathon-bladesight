"""Smoke check of a running BladeSight (local or deployed): `python -m bladesight.api.smoke URL`.

Opens the health check, the fleet, one inspection, one image and the home page, and exits 1 on the
first failure. Used against the public URL after a deploy (issue #14).
"""

from __future__ import annotations

import sys
import time

import httpx


def check(client: httpx.Client, base: str = "", ui: bool = True) -> list[str]:
    """Run the checks; returns a list of failures (empty when everything passed)."""
    failures: list[str] = []

    def get(path: str, expect: str | None = None) -> httpx.Response | None:
        try:
            response = client.get(base + path)
        except httpx.HTTPError as error:
            failures.append(f"{path}: {error}")
            return None
        if response.status_code != 200:
            failures.append(f"{path}: HTTP {response.status_code}")
            return None
        if expect and expect not in response.headers.get("content-type", ""):
            failures.append(f"{path}: content-type {response.headers.get('content-type')}")
        return response

    health = get("/api/health", "json")
    if health and health.json().get("status") != "ok":
        failures.append("/api/health: status is not ok")
    fleet = get("/api/fleet", "json")
    if fleet:
        turbines = fleet.json().get("turbines", [])
        if not turbines:
            failures.append("/api/fleet: no turbines")
        else:
            inspection_id = turbines[0]["inspections"][-1]["id"]
            inspection = get(f"/api/inspections/{inspection_id}", "json")
            if inspection:
                images = inspection.json().get("images", [])
                if images:
                    get(images[0]["image_url"], "image/png")
    get("/api/work-orders", "json")
    get("/api/eval", "json")
    if ui:
        get("/", "text/html")
    return failures


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    ui = "--api-only" not in args
    args = [a for a in args if a != "--api-only"]
    if len(args) != 1:
        print("usage: python -m bladesight.api.smoke https://host [--api-only]", file=sys.stderr)
        return 2
    started = time.monotonic()
    with httpx.Client(base_url=args[0].rstrip("/"), timeout=60.0, follow_redirects=True) as client:
        failures = check(client, ui=ui)
    seconds = time.monotonic() - started
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    print(f"{'FAILED' if failures else 'OK'} in {seconds:.1f}s")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
