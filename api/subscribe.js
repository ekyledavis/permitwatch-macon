const { getPool, ensureSchema } = require("./_db");
const { geocodeAddress } = require("./_geocode");

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const VALID_RADII = new Set(["0.25", "0.5", "1.0", "2.0"]);

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
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

  try {
    await ensureSchema();
    await getPool().query(
      `INSERT INTO subscribers
         (email, address, lat, lng, radius_miles, intown_only, phone,
          alert_new_filing, alert_status_change, alert_hearing_reminder,
          alert_demolition, alert_new_comment, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12, now())
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
         updated_at = now()`,
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
      ]
    );
  } catch (err) {
    console.error("Failed to save subscriber:", err);
    res.status(500).json({ error: "Something went wrong saving your preferences. Please try again." });
    return;
  }

  res.status(200).json({ ok: true });
};
