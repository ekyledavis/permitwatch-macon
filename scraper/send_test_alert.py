#!/usr/bin/env python3
"""
send_test_alert.py - Send a one-off test email to every current subscriber,
to verify the Postgres + Resend wiring end-to-end without waiting for (or
faking) a real permit change.

Completely side-effect free on the real alerting pipeline: it doesn't touch
scraper/alert_state.json or public/permitwatch_data.json, and doesn't run
any matching logic - it just fetches subscribers and emails all of them.

Requires the same env vars as send_alerts.py: POSTGRES_URL, RESEND_API_KEY,
optional RESEND_FROM_EMAIL. Run via the "Send Test Alert" workflow
(workflow_dispatch only - never runs on a schedule).
"""
import os, logging

import psycopg2

from send_alerts import fetch_subscribers, send_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("test-alert")

TEST_HTML = """
<div style="font-family:sans-serif;">
  <h2>PermitWatch Macon &mdash; Test Alert</h2>
  <p>This is a one-off test message confirming your PermitWatch alert
  subscription is wired up correctly. If you're reading this, email
  delivery works end-to-end.</p>
  <p style="color:#777;font-size:12px;">No action needed &mdash; this was
  triggered manually to verify the pipeline, not by a real permit filing.</p>
</div>
"""


def run():
    postgres_url = os.environ.get("POSTGRES_URL") or os.environ.get("NILEDB_POSTGRES_URL")
    resend_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "PermitWatch <onboarding@resend.dev>")

    if not postgres_url:
        log.error("No POSTGRES_URL configured; cannot send test alert.")
        return
    if not resend_key:
        log.error("No RESEND_API_KEY configured; cannot send test alert.")
        return

    conn = psycopg2.connect(postgres_url)
    try:
        subscribers = fetch_subscribers(conn)
    finally:
        conn.close()

    if not subscribers:
        log.warning("No subscribers in the database; nothing to test against.")
        return

    log.info("Sending test alert to %d subscriber(s)...", len(subscribers))
    for sub in subscribers:
        ok = send_email(resend_key, from_email, sub["email"], "PermitWatch: test alert", TEST_HTML)
        log.info("  %s: %s", sub["email"], "sent" if ok else "FAILED (see warning above)")


if __name__ == "__main__":
    run()
