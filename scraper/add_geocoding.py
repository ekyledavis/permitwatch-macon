#!/usr/bin/env python3
"""
Adds neighborhood geocoding to mbpz_scraper.py.
Uses Nominatim (free, no API key) with a local cache.
"""
import os

# The geocoding functions to inject into the scraper
GEOCODE_CODE = '''
# ── Neighborhood Geocoding ────────────────────────────────────────────────────

GEOCODE_CACHE_FILE = "scraper/geocode_cache.json"

# Street-name fallback map for known Macon corridors
STREET_NEIGHBORHOOD_MAP = [
    # Intown historic neighborhoods
    (["vineville ave", "vineville rd"],                          "Vineville"),
    (["ingleside ave", "ingleside rd"],                          "Ingleside"),
    (["college st", "college ave"],                              "College Hill"),
    (["napier ave", "beall spring", "anthony ave"],              "Beall's Hill"),
    (["huguenin ave", "huguenin heights"],                       "Huguenin Heights"),
    (["rogers ave", "rogers rd"],                                "Rogers Avenue"),
    (["highland ave", "cherokee ave", "cherokee rd"],            "Cherokee Heights"),
    (["bond st", "bond ave"],                                    "Bond Street"),
    # Downtown / Midtown
    (["cherry st", "mulberry st", "poplar st", "cotton ave",
      "first st", "second st", "third st", "fourth st",
      "fifth st", "plum st", "new st"],                         "Downtown Macon"),
    (["forsyth st", "oglethorpe st", "spring st",
      "orange st", "washington ave", "monroe st"],               "Midtown Macon"),
    # Other Macon areas
    (["riverside dr", "riverside rd"],                           "Riverside"),
    (["riverside dr", "shirley hills"],                          "Shirley Hills"),
    (["mercer university", "columbus rd"],                        "North Macon"),
    (["hartley bridge", "hartley rd"],                           "South Macon"),
    (["bass rd", "bass lake"],                                   "North Macon"),
    (["arkwright rd", "arkwright"],                              "East Macon"),
    (["eisenhower pkwy", "eisenhower"],                          "Macon Mall Area"),
    (["houston ave", "houston rd"],                              "South Macon"),
    (["gray hwy", "gray highway"],                               "East Macon"),
    (["pio nono", "pio nono ave"],                               "South Macon"),
    (["jeffersonville rd"],                                      "North Macon"),
    (["log cabin dr", "log cabin"],                              "North Macon"),
    (["zebulon rd", "zebulon"],                                  "West Macon"),
    (["broadway", "broadway ave"],                               "South Macon"),
    (["hardeman ave", "hardeman"],                               "Hardeman Avenue"),
    (["walnut st", "walnut creek"],                              "Downtown Macon"),
    (["columbus rd", "columbus st"],                             "West Macon"),
    (["fulton mill", "fulton mill rd"],                          "East Macon"),
    (["hawkinsville rd", "hawkinsville"],                        "South Macon"),
    (["anthony rd", "anthony road"],                             "Anthony Road"),
    (["interstate", "i-75", "i-16"],                             "Macon"),
]

def load_geocache():
    if os.path.exists(GEOCODE_CACHE_FILE):
        try:
            with open(GEOCODE_CACHE_FILE) as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_geocache(cache):
    os.makedirs(os.path.dirname(GEOCODE_CACHE_FILE), exist_ok=True)
    with open(GEOCODE_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def street_neighborhood(address):
    """Fast street-name based neighborhood lookup."""
    lower = address.lower()
    for streets, neighborhood in STREET_NEIGHBORHOOD_MAP:
        for street in streets:
            if street in lower:
                return neighborhood
    return None

def geocode_neighborhood(address, cache):
    """
    Look up neighborhood for a Macon address using Nominatim.
    Returns neighborhood name string.
    """
    key = address.strip().lower()
    if key in cache:
        return cache[key]

    # Try street name first (instant, no API call)
    street_result = street_neighborhood(address)

    query = "{}, Macon, GA".format(address)
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "addressdetails": 1},
            headers={"User-Agent": "PermitWatch-INA/1.0"},
            timeout=10,
        )
        results = r.json()
        time.sleep(1.1)  # Nominatim rate limit

        if results and results[0].get("address"):
            addr = results[0]["address"]
            # Try these fields in order of specificity
            neighborhood = (
                addr.get("neighbourhood") or
                addr.get("suburb") or
                addr.get("quarter") or
                addr.get("residential") or
                street_result or
                addr.get("city_district") or
                "Macon"
            )
            cache[key] = neighborhood
            save_geocache(cache)
            return neighborhood
    except Exception as e:
        log.warning("Geocode failed for %s: %s", address, e)
        time.sleep(1.1)

    # Fall back to street name match
    result = street_result or "Macon"
    cache[key] = result
    save_geocache(cache)
    return result

'''

SCRAPE_DETAIL_OLD = '''def scrape_detail(post, outcomes_lookup=None):
    """Scrape a single hearing agenda/results page.
    outcomes_lookup: dict of {parcel: status} from PDF parsing
    """'''

SCRAPE_DETAIL_NEW = '''def scrape_detail(post, outcomes_lookup=None, geocache=None):
    """Scrape a single hearing agenda/results page.
    outcomes_lookup: dict of {parcel: status} from PDF parsing
    geocache: dict cache for neighborhood geocoding
    """'''

# Change neighborhood assignment in scrape_detail
OLD_NEIGHBORHOOD = '"neighborhood":  "Macon",'
NEW_NEIGHBORHOOD = '"neighborhood":  geocode_neighborhood(address, geocache) if geocache is not None else (street_neighborhood(address) or "Macon"),'

# Change run() to load geocache and pass it through
OLD_RUN_POSTS = '''    all_items = []
    seen = set()
    for post in posts:
        for item in scrape_detail(post, outcomes_lookup):'''

NEW_RUN_POSTS = '''    # Load geocoding cache
    geocache = load_geocache()
    log.info("Loaded %d cached geocodes", len(geocache))

    all_items = []
    seen = set()
    for post in posts:
        for item in scrape_detail(post, outcomes_lookup, geocache):'''

with open("scraper/mbpz_scraper.py") as f:
    content = f.read()

fixes = 0

# Inject geocoding code before scrape_detail function
if "geocode_neighborhood" not in content:
    insert_point = content.find("def scrape_detail(")
    if insert_point > -1:
        content = content[:insert_point] + GEOCODE_CODE + content[insert_point:]
        fixes += 1
        print("Fix 1 applied: geocoding functions injected")
    else:
        print("Fix 1 FAILED: scrape_detail not found")
else:
    print("Fix 1 skipped: geocoding already present")

# Update scrape_detail signature
if SCRAPE_DETAIL_OLD in content:
    content = content.replace(SCRAPE_DETAIL_OLD, SCRAPE_DETAIL_NEW)
    fixes += 1
    print("Fix 2 applied: scrape_detail signature updated")
else:
    print("Fix 2 skipped: signature already updated or not found")

# Update neighborhood assignment
if OLD_NEIGHBORHOOD in content:
    content = content.replace(OLD_NEIGHBORHOOD, NEW_NEIGHBORHOOD)
    fixes += 1
    print("Fix 3 applied: neighborhood geocoding in item dict")
else:
    print("Fix 3 NOT found — checking what's there...")
    for i, line in enumerate(content.split("\n")):
        if '"neighborhood"' in line:
            print(f"  Line {i+1}: {line.strip()}")

# Update run() to pass geocache
if OLD_RUN_POSTS in content:
    content = content.replace(OLD_RUN_POSTS, NEW_RUN_POSTS)
    fixes += 1
    print("Fix 4 applied: geocache loaded and passed in run()")
else:
    print("Fix 4 NOT found")

with open("scraper/mbpz_scraper.py", "w") as f:
    f.write(content)

print(f"\n{fixes} fixes applied to scraper/mbpz_scraper.py")
print("Verify: geocode_neighborhood in file:", "geocode_neighborhood" in content)
print("Verify: load_geocache in file:", "load_geocache" in content)
