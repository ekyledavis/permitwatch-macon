#!/usr/bin/env python3
"""
mbpz_to_permitwatch.py
──────────────────────
Transforms mbpz_hearings.json (output of mbpz_scraper.py) into
permitwatch_data.json — the format consumed by the PermitWatch React app.

Usage:
    python3 mbpz_to_permitwatch.py
    python3 mbpz_to_permitwatch.py --in mbpz_hearings.json --out permitwatch_data.json

What this does:
  • Maps MBPZ request types → PermitWatch display types
  • Attempts geocoding via Nominatim (free, no API key needed)
  • Flags Intown Macon items
  • Initialises empty reactions + comments arrays
  • Caches geocode results in geocode_cache.json to avoid repeat lookups
"""

import re
import json
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("loader")

GEOCODE_URL   = "https://nominatim.openstreetmap.org/search"
GEOCODE_CACHE = Path("geocode_cache.json")
GEOCODE_DELAY = 1.1   # Nominatim rate limit: 1 req/sec
MACON_LAT     = 32.840
MACON_LNG     = -83.632

# Default fallback lat/lng for items we can't geocode
# (spread slightly so pins don't overlap on the map)
import hashlib

def fallback_coords(address: str):
    """Deterministic jitter around Macon centre for ungeocodable addresses."""
    h = int(hashlib.md5(address.encode()).hexdigest()[:8], 16)
    lat = MACON_LAT + ((h % 200) - 100) * 0.0003
    lng = MACON_LNG + ((h % 300) - 150) * 0.0003
    return round(lat, 5), round(lng, 5)


# ── Type mapping ──────────────────────────────────────────────────────────────

TYPE_DISPLAY = {
    "Certificate of Appropriateness": "Historic Preservation",
    "Conditional Use":                "Conditional Use",
    "Rezoning":                       "Rezoning",
    "Variance":                       "Variance Request",
    "Special Exception":              "Special Exception",
    "Violation / Revocation":         "Violation / Revocation",
    "Subdivision":                    "Subdivision",
    "Annexation":                     "Annexation",
    "Text Amendment":                 "Text Amendment",
    "Planned Development":            "Planned Development",
    "Other":                          "Other",
}

TYPE_ICON = {
    "Historic Preservation":  "🏛️",
    "Conditional Use":        "📋",
    "Rezoning":               "🔀",
    "Variance Request":       "📐",
    "Special Exception":      "⚡",
    "Violation / Revocation": "⚠️",
    "Subdivision":            "📏",
    "Annexation":             "🗺️",
    "Text Amendment":         "📝",
    "Planned Development":    "🏗️",
    "Other":                  "📄",
}


# ── Status mapping ────────────────────────────────────────────────────────────

def infer_status(item: dict) -> str:
    """
    Map MBPZ post_type + status_note to a PermitWatch status string.
    """
    note = (item.get("status_note") or "").lower()
    ptype = (item.get("post_type") or "").lower()

    if "withdrawn" in note:
        return "Withdrawn"
    if "continued" in note or "tabled" in note:
        return "Continued"
    if "result" in ptype:
        return "Decision Issued"
    if "draft" in ptype:
        return "Pending Hearing"
    if "agenda" in ptype:
        return "Pending Hearing"
    if "design review" in ptype:
        return "Pending Hearing"
    return "Under Review"


# ── Geocoding ─────────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if GEOCODE_CACHE.exists():
        with open(GEOCODE_CACHE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(GEOCODE_CACHE, "w") as f:
        json.dump(cache, f, indent=2)


def geocode(address: str, cache: dict) -> tuple[float, float]:
    """
    Look up lat/lng for a Macon, GA address.
    Returns (lat, lng) — falls back to jittered Macon centre on failure.
    """
    key = address.strip().lower()
    if key in cache:
        return cache[key]["lat"], cache[key]["lng"]

    query = f"{address}, Macon, GA"
    try:
        r = requests.get(
            GEOCODE_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "PermitWatch-INA/1.0"},
            timeout=10,
        )
        results = r.json()
        time.sleep(GEOCODE_DELAY)

        if results:
            lat = float(results[0]["lat"])
            lng = float(results[0]["lon"])
            cache[key] = {"lat": lat, "lng": lng}
            save_cache(cache)
            log.info(f"  Geocoded: {address} → {lat:.5f}, {lng:.5f}")
            return lat, lng
    except Exception as e:
        log.warning(f"  Geocode failed for '{address}': {e}")
        time.sleep(GEOCODE_DELAY)

    lat, lng = fallback_coords(address)
    cache[key] = {"lat": lat, "lng": lng, "fallback": True}
    save_cache(cache)
    log.info(f"  Fallback coords for: {address}")
    return lat, lng


# ── Neighbourhood tagging ─────────────────────────────────────────────────────

INTOWN_KEYWORDS = [
    "vineville", "ingleside", "college", "napier", "huguenin",
    "rogers", "bond", "boulevard", "oglethorpe", "tattnall",
    "poplar", "mulberry", "cherry", "walnut", "cotton",
    "forsyth", "washington", "monroe", "spring", "orange",
    "riverside", "first", "second", "third", "fourth",
    "beall", "anthony", "holt", "coleman", "highland",
    "new", "plum", "pine", "oak", "cedar", "elm",
]

NEIGHBOURHOOD_MAP = [
    (["vineville"],                          "Vineville"),
    (["ingleside"],                          "Ingleside"),
    (["college", "coleman"],                 "College Hill"),
    (["napier", "beall", "anthony"],         "Beall's Hill"),
    (["huguenin"],                           "Huguenin Heights"),
    (["riverside", "shirley"],               "Shirley Hills"),
    (["cherry", "mulberry", "poplar",
      "walnut", "cotton", "first", "second",
      "third", "fourth", "fifth"],           "Downtown Macon"),
    (["forsyth", "washington", "bond"],      "Midtown Macon"),
    (["rogers"],                             "Rogers Avenue"),
    (["highland", "oglethorpe"],             "Cherokee Heights"),
]

def tag_neighbourhood(address: str) -> str:
    lower = address.lower()
    for keywords, name in NEIGHBOURHOOD_MAP:
        if any(kw in lower for kw in keywords):
            return name
    return "Macon"


def is_intown(address: str) -> bool:
    lower = address.lower()
    return any(kw in lower for kw in INTOWN_KEYWORDS)


# ── Main transform ────────────────────────────────────────────────────────────

def transform(in_file: str, out_file: str, skip_geocode: bool = False):
    log.info(f"Loading {in_file}")
    with open(in_file) as f:
        raw = json.load(f)

    items = raw.get("items", [])
    log.info(f"  {len(items)} raw items to transform")

    cache = load_cache()
    output_items = []

    for i, item in enumerate(items):
        address   = item.get("address", "").strip()
        req_type  = item.get("request_type", "Other")
        display_type = TYPE_DISPLAY.get(req_type, req_type)
        status    = infer_status(item)
        nbhd      = tag_neighbourhood(address)
        intown    = is_intown(address) or item.get("intown", False)

        # Geocode
        if skip_geocode:
            lat, lng = fallback_coords(address)
        else:
            lat, lng = geocode(address, cache)

        # Build the PermitWatch item
        pw_item = {
            # Identifiers
            "id":           item.get("id", f"MBPZ-{i}"),
            "parcels":      item.get("parcels", []),

            # Location
            "address":      address,
            "neighborhood": nbhd,
            "intown":       intown,
            "lat":          lat,
            "lng":          lng,

            # Application details
            "type":         display_type,
            "type_icon":    TYPE_ICON.get(display_type, "📄"),
            "zoning":       item.get("zoning", ""),
            "description":  item.get("description", ""),
            "applicant":    item.get("applicant", ""),

            # Status & dates
            "status":       status,
            "status_note":  item.get("status_note", ""),
            "submitted":    item.get("hearing_date"),   # best proxy we have
            "hearing":      item.get("hearing_date") + "T13:30:00" if item.get("hearing_date") else None,

            # Source
            "hearing_title": item.get("hearing_title", ""),
            "hearing_url":   item.get("hearing_url", ""),
            "post_type":     item.get("post_type", ""),
            "source_url":    item.get("hearing_url", ""),

            # Community features (initialised empty)
            "reactions":    {"support": 0, "oppose": 0, "neutral": 0},
            "comments":     [],
        }

        output_items.append(pw_item)

    # Summary stats
    intown_count = sum(1 for i in output_items if i["intown"])
    type_counts  = {}
    for item in output_items:
        t = item["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    output = {
        "generated_at":   datetime.now().isoformat(),
        "source":         raw.get("source", "https://mbpz.org/category/hearing/"),
        "scraped_at":     raw.get("scraped_at"),
        "months_back":    raw.get("months_back", 12),
        "total_items":    len(output_items),
        "intown_items":   intown_count,
        "type_breakdown": type_counts,
        "items":          output_items,
    }

    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log.info("─" * 50)
    log.info(f"Done → {out_file}")
    log.info(f"  Total: {len(output_items)}  |  Intown: {intown_count}")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        log.info(f"  {t}: {c}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transform MBPZ scrape → PermitWatch format")
    parser.add_argument("--in",           dest="in_file",      default="mbpz_hearings.json",    help="Input JSON from mbpz_scraper.py")
    parser.add_argument("--out",          dest="out_file",     default="permitwatch_data.json",  help="Output JSON for the app")
    parser.add_argument("--skip-geocode", dest="skip_geocode", action="store_true",              help="Skip geocoding (use fallback coords)")
    args = parser.parse_args()
    transform(in_file=args.in_file, out_file=args.out_file, skip_geocode=args.skip_geocode)
