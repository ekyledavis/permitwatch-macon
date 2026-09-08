# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PermitWatch is a React app for the Intown Macon Neighborhood Association that
tracks Macon-Bibb County Planning & Zoning (MBPZ) permit applications — list,
map, hearing calendar, and email/SMS alert-preference views. It's a static
frontend (Create React App) backed by two independent, loosely-coupled
pieces: a weekly Python scraper that produces the permit data file, and a
small set of Vercel serverless functions + Postgres for the "live" parts
(comments, reactions, alert subscriptions).

## Commands

```bash
npm install       # install JS deps
npm start         # dev server (comments/reactions/subscribe need /api/* — see below)
npm run build     # production build → build/ (Vercel deploys this)
npm test          # react-scripts test
```

Scraper (run from repo root):

```bash
pip install requests beautifulsoup4 pdfplumber psycopg2-binary
python scraper/mbpz_scraper.py --months 12 --out public/permitwatch_data.json
python scraper/send_alerts.py       # needs POSTGRES_URL + RESEND_API_KEY env vars
python scraper/send_test_alert.py   # manual one-off test send to all subscribers
```

`npm start` alone won't exercise `/api/*` locally (those are Vercel
serverless functions, not part of the CRA dev server) — use `vercel dev` if
you need to test comments/reactions/subscribe end-to-end, and set
`POSTGRES_URL`/`NILEDB_POSTGRES_URL` (and `RESEND_API_KEY` for alerts) either
way.

## Architecture

**Three parts that only communicate through a data file and a database —
no shared code between them:**

1. **`src/App.jsx`** — the entire frontend UI (list/map/calendar/alerts
   views) in one file, inline-styled, no CSS framework. The map is a
   hand-drawn SVG (`MapView`), not a real map library, with hardcoded
   road/river/neighborhood geometry calibrated to Macon's lat/lng bounds.
   On mount it `fetch("/permitwatch_data.json")` for the permit list
   (falling back to a hardcoded `FALLBACK_DATA` array if that fails), then
   per-permit `fetch("/api/permit-activity?permitId=...&voterId=...")` for
   live comments/reactions. Voting/commenting POST to `/api/reactions` and
   `/api/comments`; the alerts view POSTs to `/api/subscribe`. An anonymous
   `voterId` (and remembered comment author name) is generated once and
   kept in `localStorage` so a visitor can change their vote without an
   account, without a server-side login system.

2. **`api/`** — Vercel serverless functions (Node, `module.exports = async
   (req, res) => {...}`), the backend for the "live" community features:
   - `_db.js` — shared Postgres pool (Nile via Vercel Storage;
     `POSTGRES_URL` or `NILEDB_POSTGRES_URL`) and `ensureSchema()`, which
     idempotently creates/migrates `subscribers`, `comments`, `reactions`
     on first use via `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD
     COLUMN IF NOT EXISTS` — there's no separate migration step or tool.
   - `_geocode.js` — shared Nominatim geocoding helper (same free,
     no-API-key service the scraper uses).
   - `_rateLimit.js` — shared Postgres-backed fixed-window rate limiter
     (table `rate_limits`, keyed by `endpoint:ip:windowStart`); every
     write endpoint below calls it and returns 429 + `Retry-After` when
     over its limit. It's meant to blunt casual spam/vote-stuffing, not
     defend against a determined attacker rotating IPs.
   - `comments.js` (POST, insert), `reactions.js` (POST, upsert one
     `(permit_id, voter_id)` row and return updated counts),
     `permit-activity.js` (GET, combined comments + reaction counts +
     the caller's own reaction for one permit), `subscribe.js` (POST,
     geocode + upsert an alert subscription by email — see verification
     note below), `confirm.js` (GET, the link a subscriber clicks in
     their confirmation email; renders a small HTML page, not JSON).
   Any of these will 500 if `POSTGRES_URL`/`NILEDB_POSTGRES_URL` isn't set.

   **Subscriber email verification (double opt-in)**: `subscribe.js`
   never emails alerts to an address on the strength of a form submission
   alone. A new subscriber gets a random `confirm_token` and stays
   unverified (`verified_at IS NULL`) until they click the emailed link,
   which `confirm.js` uses to stamp `verified_at` and clear the token.
   `scraper/send_alerts.py`'s `fetch_subscribers()` only selects
   `verified_at IS NOT NULL` rows, so unconfirmed signups are silently
   excluded from alerts rather than erroring. Subscribers who existed
   before this feature were grandfathered in as verified by a one-time
   backfill in `ensureSchema()` (matched on having no `confirm_token`,
   since a real new signup always gets one) — don't remove that backfill
   without checking it's already run in production. Sending the
   confirmation email itself needs `RESEND_API_KEY` (and optionally
   `RESEND_FROM_EMAIL`) set as a **Vercel** environment variable — this is
   separate from the same-named GitHub Actions secret the scraper uses,
   since `subscribe.js` runs on Vercel, not in CI.

3. **`scraper/`** — Python, unrelated to the Node toolchain.
   - `mbpz_scraper.py` is the whole pipeline in one script: crawls
     `mbpz.org/category/hearing/`, parses hearing agenda/results pages
     (including PDF results via `pdfplumber`), geocodes addresses
     (cached in `scraper/geocode_cache.json`), tags neighborhood/`intown`
     status from the `INTOWN` street list, and writes
     **directly to `public/permitwatch_data.json`** in the shape the app
     consumes. **`mbpz_to_permitwatch.py` is dead code** — an older
     separate transform stage that nothing invokes anymore (the workflow
     and scraper both bypass it); don't assume it's part of the live
     pipeline.
   - `send_alerts.py` runs after the scraper: matches the freshly-scraped
     data against subscribers in Postgres, tracks which
     items/events have already been emailed in `scraper/alert_state.json`
     (so reruns don't re-send), and sends via the Resend API.
     `send_test_alert.py` is a manual-only variant for sending one test
     email pass to all subscribers.

**Data contract**: `public/permitwatch_data.json` (`{ items: [...],
scraped_at, ... }`) is the handoff from the scraper to the frontend; each
item's `id` is also the join key (`permit_id`) for the `comments` and
`reactions` tables in Postgres. Type/status/icon maps live independently in
`src/App.jsx` (`STATUS_CONFIG`, `TYPE_ICONS`) and `scraper/mbpz_scraper.py`
(`TYPES`) — keep them in sync when adding a new permit type or status.

**Automation** (`.github/workflows/`):
- `scraper.yml` — weekly (Mon 8am UTC) + manual dispatch. Runs the scraper,
  then `send_alerts.py` (`continue-on-error: true` so an alerting bug never
  blocks the data commit), then commits `public/permitwatch_data.json`,
  `scraper/geocode_cache.json`, and `scraper/alert_state.json` and pushes.
  Because a run can take 10+ minutes (PDF parsing, geocoding), the push step
  rebases onto `origin/main` and retries (up to 3 attempts) if another push
  landed on `main` during the run. Needs `POSTGRES_URL` and
  `RESEND_API_KEY` repo secrets for the alert step to actually send.
- `send-test-alert.yml` — manual-only trigger for `send_test_alert.py`.

**Deployment**: Vercel (`vercel.json`, standard CRA build). The `api/`
functions and the scraper's alert step both need `POSTGRES_URL`/
`NILEDB_POSTGRES_URL` and (for alerts) `RESEND_API_KEY` configured as
environment variables/secrets in both Vercel and GitHub Actions.
