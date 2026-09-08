const crypto = require("crypto");
const { getPool, ensureSchema } = require("./_db");
const { geocodeAddress } = require("./_geocode");
const { rateLimit } = require("./_rateLimit");

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const VALID_RADII = new Set(["0.25", "0.5", "1.0", "2.0"]);
const CONFIRM_TOKEN_TTL_HOURS = 24;

function baseUrl(req) {
  const proto = req.headers["x-forwarded-proto"] || "https";
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  return `${proto}://${host}`;
}

async function sendConfirmationEmail(origin, email, token) {
  const resendKey = process.env.RESEND_API_KEY;
  if (!resendKey) {
    console.error("RESEND_API_KEY not configured; cannot send confirmation email.");
    return false;
  }
  const fromEmail = process.env.RESEND_FROM_EMAIL || "PermitWatch <onboarding@resend.dev>";
  const confirmUrl = `${origin}/api/confirm?token=${encodeURIComponent(token)}`;
  const html = `
    <div style="font-family:sans-serif;">
      <h2>Confirm your PermitWatch alerts</h2>
      <p>Click below to start receiving Macon-Bibb permit alerts at this address:</p>
      <p><a href="${confirmUrl}" style="background:#4F6BFF;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none;display:inline-block;">Confirm my email</a></p>
      <p style="color:#777;font-size:12px;">If you didn't request this, you can ignore this email —
      nothing is sent to this address unless the link above is clicked.</p>
    </div>`;
  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${resendKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from: fromEmail, to: [email], subject: "Confirm your PermitWatch alerts", html }),
    });
    if (!r.ok) console.error("Resend confirmation email failed:", r.status, await r.text().catch(() => ""));
    return r.ok;
  } catch (err) {
    console.error("Failed to send confirmation email:", err);
    return false;
  }
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }

  const { allowed, retryAfterSeconds } = await rateLimit(req, "subscribe", 5, 3600); // 5/hour/IP
  if (!allowed) {
    res.setHeader("Retry-After", String(retryAfterSeconds));
    res.status(429).json({ error: "Too many subscription attempts from this network. Please try again later." });
    return;
  }

  const body = req.body || {};
  const email = String(body.email || "").trim().toLowerCase();
  const address = String(body.address || "").trim();
  const radiusMiles = VALID_RADII.has(String(body.radiusMiles))
    ? String(body.radiusMiles)
    : "0.5";
  const intownOnly = body.intownOnly !== false; // default true
  const phone = body.phone ? String(body.phone).trim() : null;
  const alerts = body.alerts || {};

  if (!EMAIL_RE.test(email)) {
    res.status(400).json({ error: "A valid email address is required." });
    return;
  }
  if (!address) {
    res.status(400).json({ error: "An address is required." });
    return;
  }

  let coords = null;
  try {
    coords = await geocodeAddress(address);
  } catch (err) {
    console.error("Geocoding failed:", err);
  }
  if (!coords) {
    res.status(422).json({
      error:
        "Couldn't locate that address. Double-check it and try again (e.g. \"423 Orange Street\").",
    });
    return;
  }

  const confirmToken = crypto.randomBytes(24).toString("hex");
  const confirmTokenExpiresAt = new Date(Date.now() + CONFIRM_TOKEN_TTL_HOURS * 3600 * 1000);

  let alreadyVerified = false;
  try {
    await ensureSchema();
    const { rows } = await getPool().query(
      `INSERT INTO subscribers
         (email, address, lat, lng, radius_miles, intown_only, phone,
          alert_new_filing, alert_status_change, alert_hearing_reminder,
          alert_demolition, alert_new_comment, confirm_token, confirm_token_expires_at, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14, now())
       ON CONFLICT (email) DO UPDATE SET
         address = EXCLUDED.address,
         lat = EXCLUDED.lat,
         lng = EXCLUDED.lng,
         radius_miles = EXCLUDED.radius_miles,
         intown_only = EXCLUDED.intown_only,
         phone = EXCLUDED.phone,
         alert_new_filing = EXCLUDED.alert_new_filing,
         alert_status_change = EXCLUDED.alert_status_change,
         alert_hearing_reminder = EXCLUDED.alert_hearing_reminder,
         alert_demolition = EXCLUDED.alert_demolition,
         alert_new_comment = EXCLUDED.alert_new_comment,
         -- Someone who already confirmed this email shouldn't be forced to
         -- reconfirm just because they updated their address/preferences;
         -- only touch the confirm token while they're still unverified.
         confirm_token = CASE WHEN subscribers.verified_at IS NULL THEN EXCLUDED.confirm_token ELSE subscribers.confirm_token END,
         confirm_token_expires_at = CASE WHEN subscribers.verified_at IS NULL THEN EXCLUDED.confirm_token_expires_at ELSE subscribers.confirm_token_expires_at END,
         updated_at = now()
       RETURNING verified_at`,
      [
        email,
        address,
        coords.lat,
        coords.lng,
        radiusMiles,
        intownOnly,
        phone,
        alerts.newFiling !== false,
        alerts.statusChange !== false,
        alerts.hearingReminder !== false,
        alerts.demolition !== false,
        alerts.newComment === true,
        confirmToken,
        confirmTokenExpiresAt,
      ]
    );
    alreadyVerified = !!(rows[0] && rows[0].verified_at);
  } catch (err) {
    console.error("Failed to save subscriber:", err);
    res.status(500).json({ error: "Something went wrong saving your preferences. Please try again." });
    return;
  }

  if (!alreadyVerified) {
    const sent = await sendConfirmationEmail(baseUrl(req), email, confirmToken);
    if (!sent) {
      res.status(502).json({
        error: "Saved your preferences, but couldn't send a confirmation email right now. Please try again shortly.",
      });
      return;
    }
  }

  res.status(200).json({ ok: true, needsConfirmation: !alreadyVerified });
};
