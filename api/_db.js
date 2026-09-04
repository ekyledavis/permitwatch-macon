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
    `);
  }
  await schemaReady;
}

module.exports = { getPool, ensureSchema };
