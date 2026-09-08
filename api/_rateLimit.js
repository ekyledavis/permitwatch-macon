const { getPool } = require("./_db");

// Simple fixed-window rate limiter backed by Postgres — no extra infra
// (Redis, etc.) needed since we already have a database. Each (endpoint, IP,
// window) triple gets one row; a request increments it and is allowed as
// long as the count stays at or under `limit` for that window.
//
// This is deliberately approximate, not a precise leaky-bucket: it's here to
// blunt casual spam/abuse (comment flooding, vote-stuffing by clearing
// localStorage, subscribe-bombing a stranger's inbox), not to defend against
// a determined attacker rotating IPs.

let schemaReady;
async function ensureRateLimitSchema() {
  if (!schemaReady) {
    schemaReady = getPool().query(`
      CREATE TABLE IF NOT EXISTS rate_limits (
        bucket_key TEXT PRIMARY KEY,
        count      INT NOT NULL DEFAULT 0,
        expires_at TIMESTAMPTZ NOT NULL
      );
    `);
  }
  await schemaReady;
}

function clientIp(req) {
  // Vercel sets x-forwarded-for to "client, proxy1, proxy2, ..."; the first
  // entry is the original client.
  const fwd = req.headers["x-forwarded-for"];
  if (fwd) return String(fwd).split(",")[0].trim();
  return req.socket?.remoteAddress || "unknown";
}

// Allows `limit` requests per `windowSeconds` for this request's IP, scoped
// to `endpoint`. Returns { allowed, retryAfterSeconds }.
async function rateLimit(req, endpoint, limit, windowSeconds) {
  await ensureRateLimitSchema();
  const pool = getPool();
  const ip = clientIp(req);
  const nowSeconds = Math.floor(Date.now() / 1000);
  const windowStart = Math.floor(nowSeconds / windowSeconds) * windowSeconds;
  const bucketKey = `${endpoint}:${ip}:${windowStart}`;
  const expiresAt = new Date((windowStart + windowSeconds) * 1000);

  const { rows } = await pool.query(
    `INSERT INTO rate_limits (bucket_key, count, expires_at)
     VALUES ($1, 1, $2)
     ON CONFLICT (bucket_key) DO UPDATE SET count = rate_limits.count + 1
     RETURNING count`,
    [bucketKey, expiresAt]
  );

  // Opportunistically sweep expired rows so the table doesn't grow forever,
  // without needing a separate cron job. ~1% of requests pay this small
  // extra cost; failures here are non-fatal (best-effort cleanup only).
  if (Math.random() < 0.01) {
    pool.query("DELETE FROM rate_limits WHERE expires_at < now()").catch(() => {});
  }

  const count = rows[0].count;
  const retryAfterSeconds = windowStart + windowSeconds - nowSeconds;
  return { allowed: count <= limit, retryAfterSeconds };
}

module.exports = { rateLimit, clientIp };
