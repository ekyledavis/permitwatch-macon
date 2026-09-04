#!/usr/bin/env python3
"""
send_alerts.py - Match freshly-scraped permit items against saved alert
subscriptions and email the matches via Resend.

Run this AFTER mbpz_scraper.py has written a fresh public/permitwatch_data.json.
It is safe to run repeatedly: state (which items/events have already been
alerted on) is tracked in scraper/alert_state.json so re-runs don't re-send.

Requires env vars:
  POSTGRES_URL     - Postgres connection string (subscribers table lives here;
                      same database the /api/subscribe endpoint writes to)
  RESEND_API_KEY   - Resend API key for sending email
  RESEND_FROM_EMAIL - optional, defaults to Resend's shared testing sender,
                      which only delivers to the address that created the
                      Resend account until a custom sending domain is
                      verified there.

Dependencies: pip install psycopg2-binary requests
"""
import os, re, json, math, logging
from datetime import datetime, timedelta, timezone

import requests
import psycopg2
import psycopg2.extras

DATA_FILE = "public/permitwatch_data.json"
STATE_FILE = "scraper/alert_state.json"
HEARING_REMINDER_WINDOW_HOURS = 48

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("alerts")


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            log.warning("Couldn't parse %s, starting fresh", path)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def haversine_miles(lat1, lng1, lat2, lng2):
    R = 3958.8  # Earth radius, miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def fetch_subscribers(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id                     SERIAL PRIMARY KEY,
                email                  TEXT NOT NULL UNIQUE,
                address                TEXT NOT NULL,
                lat                    DOUBLE PRECISION,
                lng                    DOUBLE PRECISION,
                radius_miles           NUMERIC NOT NULL DEFAULT 0.5,
                intown_only            BOOLEAN NOT NULL DEFAULT TRUE,
                phone                  TEXT,
                alert_new_filing       BOOLEAN NOT NULL DEFAULT TRUE,
                alert_status_change    BOOLEAN NOT NULL DEFAULT TRUE,
                alert_hearing_reminder BOOLEAN NOT NULL DEFAULT TRUE,
                alert_demolition       BOOLEAN NOT NULL DEFAULT TRUE,
                alert_new_comment      BOOLEAN NOT NULL DEFAULT FALSE,
                created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        conn.commit()
        cur.execute("SELECT * FROM subscribers")
        return cur.fetchall()


def event_types_for_item(item, prev_state):
    """Returns a set of event-type strings that apply to this item right now."""
    events = set()
    is_new = prev_state is None
    if is_new:
        events.add("new_filing")
        if item.get("request_type") == "Demolition Permit":
            events.add("demolition")
    elif prev_state.get("status") != item.get("status"):
        events.add("status_change")

    hearing_reminded = bool(prev_state and prev_state.get("hearing_reminded"))
    if not hearing_reminded and item.get("hearing"):
        try:
            hearing_dt = datetime.fromisoformat(item["hearing"])
            if hearing_dt.tzinfo is None:
                hearing_dt = hearing_dt.replace(tzinfo=timezone.utc)
            hours_until = (hearing_dt - datetime.now(timezone.utc)).total_seconds() / 3600
            if 0 <= hours_until <= HEARING_REMINDER_WINDOW_HOURS:
                events.add("hearing_reminder")
        except ValueError:
            pass

    return events


EVENT_TO_FLAG = {
    "new_filing": "alert_new_filing",
    "status_change": "alert_status_change",
    "hearing_reminder": "alert_hearing_reminder",
    "demolition": "alert_demolition",
}


def subscriber_matches(sub, item):
    if sub["intown_only"] and not item.get("intown"):
        return False
    if sub["lat"] is not None and sub["lng"] is not None and item.get("lat") is not None and item.get("lng") is not None:
        distance = haversine_miles(sub["lat"], sub["lng"], item["lat"], item["lng"])
        if distance > float(sub["radius_miles"]):
            return False
    # If either side lacks coordinates, fall back to the intown_only check above only.
    return True


def render_email(subscriber_matches_by_item):
    rows = []
    for item, events in subscriber_matches_by_item:
        labels = {
            "new_filing": "New filing",
            "status_change": "Status changed",
            "hearing_reminder": "Hearing in the next 48 hours",
            "demolition": "Demolition permit",
        }
        tag = ", ".join(labels[e] for e in events if e in labels)
        rows.append(
            f'<li style="margin-bottom:12px;"><strong>{tag}</strong> &mdash; '
            f'{item.get("address","")}<br>'
            f'{item.get("request_type","")} &middot; {item.get("status","")}<br>'
            f'<a href="{item.get("hearing_url","")}">{item.get("hearing_title","View details")}</a></li>'
        )
    return (
        "<div style=\"font-family:sans-serif;\">"
        "<h2>PermitWatch Macon &mdash; Alert</h2>"
        f"<ul style=\"padding-left:18px;\">{''.join(rows)}</ul>"
        "<p style=\"color:#777;font-size:12px;\">You're receiving this because you subscribed to "
        "permit alerts at PermitWatch Macon.</p>"
        "</div>"
    )


def send_email(api_key, from_email, to_email, subject, html):
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": "Bearer {}".format(api_key), "Content-Type": "application/json"},
        json={"from": from_email, "to": [to_email], "subject": subject, "html": html},
        timeout=15,
    )
    if r.status_code >= 300:
        log.warning("Resend send to %s failed (%s): %s", to_email, r.status_code, r.text[:300])
        return False
    return True


def run():
    postgres_url = os.environ.get("POSTGRES_URL") or os.environ.get("NILEDB_POSTGRES_URL")
    resend_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "PermitWatch <onboarding@resend.dev>")

    if not postgres_url:
        log.warning("No POSTGRES_URL configured; skipping alert dispatch.")
        return
    if not resend_key:
        log.warning("No RESEND_API_KEY configured; skipping alert dispatch.")
        return

    data = load_json(DATA_FILE, None)
    if not data:
        log.error("No %s found; nothing to check.", DATA_FILE)
        return
    items = data.get("items", [])

    state = load_json(STATE_FILE, {})

    if not state:
        # Cold start: no baseline exists yet (first run ever, or the workflow
        # wrote a placeholder {} because secrets weren't configured before).
        # Every item would otherwise look "new", which would blast every
        # subscriber with the entire scraped backlog. Instead, just record
        # today's state as the baseline and send nothing this run.
        baseline = {
            item["id"]: {"status": item.get("status"), "hearing_reminded": True}
            for item in items
        }
        save_json(STATE_FILE, baseline)
        log.info("No alert baseline existed yet; recorded %d item(s) as the starting point. Nothing sent this run.", len(baseline))
        return

    new_state = dict(state)

    # Figure out which events apply to which items, before touching subscribers.
    item_events = []
    for item in items:
        events = event_types_for_item(item, state.get(item["id"]))
        prev = state.get(item["id"], {})
        hearing_reminded = prev.get("hearing_reminded", False) or ("hearing_reminder" in events)
        new_state[item["id"]] = {"status": item.get("status"), "hearing_reminded": hearing_reminded}
        if events:
            item_events.append((item, events))

    if not item_events:
        log.info("No new/changed items this run; no alerts to send.")
        save_json(STATE_FILE, new_state)
        return

    conn = psycopg2.connect(postgres_url)
    try:
        subscribers = fetch_subscribers(conn)
    finally:
        conn.close()
    log.info("%d subscriber(s), %d item(s) with events this run", len(subscribers), len(item_events))

    sent_count = 0
    for sub in subscribers:
        matched = []
        for item, events in item_events:
            if not subscriber_matches(sub, item):
                continue
            relevant_events = {e for e in events if sub.get(EVENT_TO_FLAG[e])}
            if relevant_events:
                matched.append((item, relevant_events))
        if not matched:
            continue
        subject = "PermitWatch: {} update{} near you".format(len(matched), "s" if len(matched) != 1 else "")
        html = render_email(matched)
        if send_email(resend_key, from_email, sub["email"], subject, html):
            sent_count += 1
            log.info("Sent alert to %s (%d item%s)", sub["email"], len(matched), "s" if len(matched) != 1 else "")

    log.info("Done. Sent %d alert email(s).", sent_count)
    save_json(STATE_FILE, new_state)


if __name__ == "__main__":
    # Alert dispatch is best-effort: a bug or outage here (bad DB URL, Resend
    # hiccup, etc.) must never take down the weekly scrape-and-commit that
    # already works reliably, so nothing escapes this as an uncaught exception.
    try:
        run()
    except Exception:
        log.exception("Alert dispatch failed; continuing without sending alerts.")
