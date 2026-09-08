const { Pool } = require("pg");

// Nile (via Vercel Storage) exposes several connection strings; POSTGRES_URL
// and NILEDB_POSTGRES_URL both point at the same plain-Postgres endpoint.
const connectionString =
  process.env.POSTGRES_URL || process.env.NILEDB_POSTGRES_URL;

let pool;
function getPool() {
  if (!connectionString) {
    throw new Error(
      "No Postgres connection string found (expected POSTGRES_URL or NILEDB_POSTGRES_URL env var)"
    );
  }
  if (!pool) {
    pool = new Pool({
      connectionString,
      ssl: { rejectUnauthorized: false },
      max: 3,
    });
  }
  return pool;
}

let schemaReady;
async function ensureSchema() {
  if (!schemaReady) {
    schemaReady = getPool().query(`
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

      -- Email verification (double opt-in): a new subscriber gets a random
      -- confirm_token and stays unverified (verified_at IS NULL) until they
      -- click the link in their confirmation email, which clears the token
      -- and stamps verified_at. Only verified subscribers are emailed
      -- alerts (see scraper/send_alerts.py).
      ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
      ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS confirm_token TEXT;
      ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS confirm_token_expires_at TIMESTAMPTZ;
      CREATE UNIQUE INDEX IF NOT EXISTS subscribers_confirm_token_idx
        ON subscribers (confirm_token) WHERE confirm_token IS NOT NULL;

      -- One-time backfill for rows that existed before email verification
      -- was added: they were trusted under the old rules, so grandfather
      -- them in as verified rather than silently cutting off their alerts.
      -- A genuinely new signup always gets a confirm_token at insert time,
      -- so it's correctly excluded here and stays unverified until
      -- confirmed. Safe to run on every deploy: once a row is backfilled
      -- (or ever confirmed for real), this WHERE clause no longer matches it.
      UPDATE subscribers SET verified_at = created_at
        WHERE verified_at IS NULL AND confirm_token IS NULL;

      CREATE TABLE IF NOT EXISTS comments (
        id          SERIAL PRIMARY KEY,
        permit_id   TEXT NOT NULL,
        author      TEXT NOT NULL DEFAULT 'Neighbor',
        text        TEXT NOT NULL,
        sentiment   TEXT NOT NULL DEFAULT 'neutral'
                      CHECK (sentiment IN ('support','oppose','neutral')),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE INDEX IF NOT EXISTS comments_permit_id_idx ON comments (permit_id);

      -- One row per (permit, anonymous browser id): lets a visitor switch
      -- their vote without creating a real account, and without letting a
      -- single browser stuff the count by voting repeatedly.
      CREATE TABLE IF NOT EXISTS reactions (
        permit_id   TEXT NOT NULL,
        voter_id    TEXT NOT NULL,
        reaction    TEXT NOT NULL
                      CHECK (reaction IN ('support','oppose','neutral')),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (permit_id, voter_id)
      );
    `);
  }
  await schemaReady;
}

module.exports = { getPool, ensureSchema };
