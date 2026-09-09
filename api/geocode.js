const { rateLimit } = require("./_rateLimit");
const { geocodeAddress } = require("./_geocode");

// Thin GET wrapper around the shared Nominatim helper, for the map tab's
// address search box. Kept server-side (rather than calling Nominatim
// directly from the browser) so we control the User-Agent/rate as Nominatim's
// usage policy requires, and so a client can't be pointed at arbitrary hosts.
module.exports = async (req, res) => {
  if (req.method !== "GET") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }

  const { allowed, retryAfterSeconds } = await rateLimit(req, "geocode", 20, 60); // 20/min/IP
  if (!allowed) {
    res.setHeader("Retry-After", String(retryAfterSeconds));
    res.status(429).json({ error: "Too many searches from this network. Please slow down." });
    return;
  }

  const address = String(req.query.address || "").trim();
  if (!address) {
    res.status(400).json({ error: "address is required." });
    return;
  }

  try {
    const result = await geocodeAddress(address);
    if (!result) {
      res.status(404).json({ error: "Couldn't find that address near Macon." });
      return;
    }
    res.status(200).json(result);
  } catch (err) {
    console.error("Failed to geocode address:", err);
    res.status(500).json({ error: "Something went wrong looking up that address." });
  }
};
