# PermitWatch MBPZ Scraper
### Intown Macon Neighborhood Association

Pulls hearing agendas and results from [mbpz.org/category/hearing/](https://mbpz.org/category/hearing/)
and transforms them into data for the PermitWatch app.

---

## Files

| File | Purpose |
|------|---------|
| `mbpz_scraper.py` | Crawls mbpz.org and extracts raw hearing item data |
| `mbpz_to_permitwatch.py` | Transforms raw data → PermitWatch app format, geocodes addresses |
| `run_scraper.sh` | One-command pipeline that runs both scripts |

---

## Setup

```bash
# Install dependencies (one time)
pip install requests beautifulsoup4

# Make the shell script executable (one time)
chmod +x run_scraper.sh
```

---

## Running

```bash
# Standard run — last 12 months
./run_scraper.sh

# Shorter window (faster)
./run_scraper.sh 6

# Force fresh geocode lookup (ignore cache)
./run_scraper.sh 12 --fresh
```

Or run the scripts individually:

```bash
# 1. Scrape raw data
python3 mbpz_scraper.py --months 12 --out data/mbpz_hearings_latest.json --pretty

# 2. Transform + geocode
python3 mbpz_to_permitwatch.py \
  --in  data/mbpz_hearings_latest.json \
  --out data/permitwatch_data.json
```

---

## Output

`data/permitwatch_data.json` — array of items shaped like:

```json
{
  "id": "MBPZ-2026-04-13-Q072-0054",
  "parcels": ["Q072-0054"],
  "address": "164 Franklin St",
  "neighborhood": "Downtown Macon",
  "intown": false,
  "lat": 32.8401,
  "lng": -83.6312,
  "type": "Historic Preservation",
  "type_icon": "🏛️",
  "zoning": "HR-3",
  "description": "for design approval of signage",
  "applicant": "Williams Peters",
  "status": "Pending Hearing",
  "status_note": "",
  "submitted": "2026-04-13",
  "hearing": "2026-04-13T13:30:00",
  "hearing_title": "04/13/2026 Hearing Agenda",
  "hearing_url": "https://mbpz.org/uncategorized/04-13-2026-hearing-agenda/",
  "source_url": "https://mbpz.org/...",
  "reactions": { "support": 0, "oppose": 0, "neutral": 0 },
  "comments": []
}
```

---

## Scheduling (run automatically every week)

Add to crontab (`crontab -e`):

```
# Every Monday at 6:00 AM
0 6 * * 1 cd /path/to/permitwatch && ./run_scraper.sh >> logs/scraper.log 2>&1
```

---

## Notes

- **Geocoding** uses OpenStreetMap Nominatim (free, no API key). Results are cached
  in `geocode_cache.json` so repeat runs are fast and don't re-hit the API.
- **Rate limiting**: the scraper pauses ~1.2 seconds between page requests to be
  respectful to mbpz.org's server.
- **Intown detection** is heuristic-based on street names. You can tune the
  `INTOWN_KEYWORDS` list in `mbpz_to_permitwatch.py`.
- **Design Review Board** meetings are included alongside P&Z hearings since
  they cover historic preservation items relevant to Intown Macon.
- The scraper handles both **Hearing Agendas** and **Hearing Results** pages.
  Items from Results pages get status `"Decision Issued"`.
