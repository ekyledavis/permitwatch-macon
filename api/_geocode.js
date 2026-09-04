// Resolves a street address to {lat, lng} using OpenStreetMap's Nominatim
// search API — the same free geocoder the scraper uses. No API key needed,
// but Nominatim's usage policy requires a descriptive User-Agent and no more
// than ~1 request/second, which is fine here since this only runs once per
// subscribe/update.
async function geocodeAddress(address) {
  const query = `${address}, Macon, GA`;
  const url =
    "https://nominatim.openstreetmap.org/search?" +
    new URLSearchParams({ q: query, format: "json", limit: "1" }).toString();

  const res = await fetch(url, {
    headers: { "User-Agent": "PermitWatch-INA/1.0" },
  });
  if (!res.ok) return null;

  const results = await res.json();
  if (!results || !results.length) return null;

  const { lat, lon } = results[0];
  const parsedLat = parseFloat(lat);
  const parsedLng = parseFloat(lon);
  if (Number.isNaN(parsedLat) || Number.isNaN(parsedLng)) return null;

  return { lat: parsedLat, lng: parsedLng };
}

module.exports = { geocodeAddress };
