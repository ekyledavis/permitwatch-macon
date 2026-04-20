#!/usr/bin/env python3
"""
mbpz_scraper.py
───────────────
Scrapes the Macon-Bibb County Planning & Zoning site (mbpz.org/category/hearing/)
and extracts all hearing agenda items from the past 12 months.

Output: mbpz_hearings.json  (ready to load into PermitWatch)

Usage:
    python3 mbpz_scraper.py
    python3 mbpz_scraper.py --months 6          # only last 6 months
    python3 mbpz_scraper.py --out data.json     # custom output file
    python3 mbpz_scraper.py --pretty            # pretty-print JSON

Dependencies:
    pip install requests beautifulsoup4
"""

import re
import json
import time
import argparse
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ── Config ───────────────────────────────────────────────────────────────────

BASE_URL      = "https://mbpz.org"
LISTING_URL   = "https://mbpz.org/category/hearing/"
REQUEST_DELAY = 1.2          # seconds between requests (be polite)
REQUEST_TIMEOUT = 20
HEADERS = {
    "User-Agent": "PermitWatch-INA-Scraper/1.0 (Intown Macon Neighborhood Association)"
}

# Known Intown Macon streets / neighborhoods for tagging
INTOWN_STREETS = [
    "vineville", "ingleside", "college", "napier", "huguenin",
    "rogers", "forsyth", "washington", "monroe", "spring",
    "orange", "bond", "boulevard", "oglethorpe", "tattnall",
    "poplar", "mulberry", "cherry", "walnut", "cotton",
    "riverside", "first", "second", "third", "fourth",
    "beall", "anthony", "holt", "coleman", "highland",
]

# Map application type keywords → normalized type labels
TYPE_MAP = {
    "certificate of appropriateness": "Certificate of Appropriateness",
    "conditional use":                "Conditional Use",
    "rezoning":                       "Rezoning",
    "variance":                       "Variance",
    "special exception":              "Special Exception",
    "violation":                      "Violation / Revocation",
    "revocation":                     "Violation / Revocation",
    "subdivision":                    "Subdivision",
    "annexation":                     "Annexation",
    "text amendment":                 "Text Amendment",
    "planned development":            "Planned Development",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mbpz")


# ── Helpers ───────────────────────────────────────────────────────────────────

def get(url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return BeautifulSoup(r.text, "html.parser")
    except requests.RequestException as e:
        log.warning(f"Failed to fetch {url}: {e}")
        return None


def parse_hearing_date(text: str) -> datetime | None:
    """
    Extract a date from strings like:
      '04/13/2026 Hearing Agenda'
      '03/23/2026 Hearing Results'
    """
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None


def normalize_type(description: str) -> str:
    """Map raw item description to a normalized application type."""
    lower = description.lower()
    for keyword, label in TYPE_MAP.items():
        if keyword in lower:
            return label
    return "Other"


def is_intown(address: str) -> bool:
    """Heuristic: flag items whose street name matches known Intown corridors."""
    lower = address.lower()
    return any(street in lower for street in INTOWN_STREETS)


def parse_item_line(raw: str) -> dict | None:
    """
    Parse a single agenda item line such as:
      'Parcel Number Q072-0054 | 164 Franklin St | Certificate of Appropriateness |
       for design approval of signage | HR-3 District | Williams Peters, applicant'

    Returns a dict or None if the line doesn't look like an agenda item.
    """
    # Must contain a parcel number pattern
    if not re.search(r"[A-Z]\d{3}-\d{4}", raw):
        return None

    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3:
        return None

    # Extract parcel number(s)
    parcel_raw = parts[0]
    parcels = re.findall(r"[A-Z]\d{3}-\d{4}", parcel_raw)

    # Address is part[1]
    address = parts[1].strip() if len(parts) > 1 else ""

    # Request type is part[2]
    request_type_raw = parts[2].strip() if len(parts) > 2 else ""
    request_type = normalize_type(request_type_raw)

    # Description is part[3] (what they want to do)
    description = parts[3].strip() if len(parts) > 3 else ""

    # Zoning district is part[4]
    zoning = parts[4].strip() if len(parts) > 4 else ""
    zoning = re.sub(r"\s*district\s*$", "", zoning, flags=re.IGNORECASE).strip()

    # Applicant is part[5]
    applicant_raw = parts[5].strip() if len(parts) > 5 else ""
    applicant = re.sub(r",?\s*applicant\s*$", "", applicant_raw, flags=re.IGNORECASE).strip()

    # Check for withdrawn / continued notices in the raw text
    status_note = ""
    if re.search(r"withdrawn", raw, re.IGNORECASE):
        status_note = "Withdrawn"
    elif re.search(r"continued", raw, re.IGNORECASE):
        status_note = "Continued"
    elif re.search(r"tabled", raw, re.IGNORECASE):
        status_note = "Tabled"

    if not address:
        return None

    return {
        "parcels":      parcels,
        "address":      address,
        "request_type": request_type,
        "description":  description,
        "zoning":       zoning,
        "applicant":    applicant,
        "status_note":  status_note,
        "intown":       is_intown(address),
    }


# ── Listing page ──────────────────────────────────────────────────────────────

def get_hearing_links(cutoff: datetime) -> list[dict]:
    """
    Paginate through mbpz.org/category/hearing/ and collect all
    hearing post URLs published after `cutoff`.

    Returns list of {title, url, date, post_type}
    """
    collected = []
    page = 1
    done = False

    while not done:
        url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"
        log.info(f"Listing page {page}: {url}")
        soup = get(url)
        if not soup:
            break

        # Posts are in <li> items with titles and links
        # The site uses a standard WordPress loop; find all post title links
        post_links = []

        # Try multiple selectors for robustness
        for selector in ["h2.entry-title a", "h3.entry-title a", ".post-title a", "article h2 a", "article h3 a"]:
            found = soup.select(selector)
            if found:
                post_links = found
                break

        # Fallback: find all links in the main content area that look like hearing posts
        if not post_links:
            main = soup.find("main") or soup.find("div", class_=re.compile(r"content|main"))
            if main:
                post_links = [
                    a for a in main.find_all("a", href=True)
                    if re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", a.get_text())
                    or re.search(r"/uncategorized/\d{2}-\d{2}-\d{4}", a["href"])
                ]

        if not post_links:
            log.warning(f"  No posts found on page {page}, stopping.")
            break

        for a in post_links:
            title = a.get_text(strip=True)
            href  = urljoin(BASE_URL, a["href"])

            # Determine post type
            lower = title.lower()
            if "result" in lower:
                post_type = "Hearing Result"
            elif "draft" in lower:
                post_type = "Draft Agenda"
            elif "agenda" in lower:
                post_type = "Hearing Agenda"
            elif "design review" in lower:
                post_type = "Design Review Board"
            else:
                post_type = "Hearing"

            date = parse_hearing_date(title)

            if date and date < cutoff:
                log.info(f"  Reached cutoff at: {title}")
                done = True
                break

            collected.append({
                "title":     title,
                "url":       href,
                "date":      date.strftime("%Y-%m-%d") if date else None,
                "post_type": post_type,
            })
            log.info(f"  Found: {title}")

        # Check if there's a next page
        next_link = soup.find("a", string=re.compile(r"next|›|»", re.IGNORECASE))
        if not next_link or done:
            break
        page += 1

    log.info(f"Total hearing posts found: {len(collected)}")
    return collected


# ── Detail page ───────────────────────────────────────────────────────────────

def scrape_hearing_detail(post: dict) -> list[dict]:
    """
    Fetch a hearing agenda/results page and extract individual application items.
    Returns a list of application dicts, each augmented with hearing metadata.
    """
    log.info(f"  Scraping detail: {post['title']}")
    soup = get(post["url"])
    if not soup:
        return []

    # Find the main content body
    content = (
        soup.find("div", class_=re.compile(r"entry-content|post-content|article-content"))
        or soup.find("article")
        or soup.find("main")
    )
    if not content:
        log.warning(f"  Could not find content area for {post['url']}")
        return []

    items = []
    raw_lines = []

    # Collect all text nodes that could be agenda items
    # Items appear in <li> tags OR as numbered paragraphs
    for li in content.find_all("li"):
        text = li.get_text(separator=" | ", strip=True)
        # Clean up extra whitespace
        text = re.sub(r"\s+", " ", text)
        raw_lines.append(text)

    # Also scan <p> tags for items that weren't in lists
    for p in content.find_all("p"):
        text = p.get_text(separator=" | ", strip=True)
        text = re.sub(r"\s+", " ", text)
        if re.search(r"[A-Z]\d{3}-\d{4}", text):
            raw_lines.append(text)

    # Deduplicate while preserving order
    seen = set()
    unique_lines = []
    for line in raw_lines:
        key = re.sub(r"\s+", " ", line).strip()
        if key not in seen:
            seen.add(key)
            unique_lines.append(line)

    for line in unique_lines:
        item = parse_item_line(line)
        if item:
            # Augment with hearing metadata
            item["hearing_date"]  = post["date"]
            item["hearing_title"] = post["title"]
            item["hearing_url"]   = post["url"]
            item["post_type"]     = post["post_type"]
            # Generate a stable ID
            parcel_slug = item["parcels"][0] if item["parcels"] else "UNKNOWN"
            item["id"] = f"MBPZ-{post['date'] or 'NODATE'}-{parcel_slug}"
            items.append(item)

    log.info(f"  → {len(items)} items extracted")
    return items


# ── Main ──────────────────────────────────────────────────────────────────────

def run(months: int = 12, out_file: str = "mbpz_hearings.json", pretty: bool = False):
    cutoff = datetime.now() - timedelta(days=months * 30)
    log.info(f"Scraping MBPZ hearings from {cutoff.strftime('%Y-%m-%d')} to today")
    log.info(f"Output: {out_file}")

    # Step 1: collect all hearing post links within the date range
    posts = get_hearing_links(cutoff)

    if not posts:
        log.error("No hearing posts found. Check connectivity or site structure.")
        return

    # Step 2: scrape each detail page
    all_items = []
    for post in posts:
        items = scrape_hearing_detail(post)
        all_items.extend(items)

    # Step 3: deduplicate by ID (same parcel can appear across multiple hearings)
    seen_ids = set()
    unique_items = []
    for item in all_items:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique_items.append(item)

    # Step 4: sort by hearing date descending
    unique_items.sort(key=lambda x: x.get("hearing_date") or "", reverse=True)

    # Step 5: summary stats
    intown_count  = sum(1 for i in unique_items if i["intown"])
    type_counts   = {}
    for item in unique_items:
        t = item["request_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    output = {
        "scraped_at":    datetime.now().isoformat(),
        "source":        LISTING_URL,
        "months_back":   months,
        "cutoff_date":   cutoff.strftime("%Y-%m-%d"),
        "total_items":   len(unique_items),
        "intown_items":  intown_count,
        "type_breakdown": type_counts,
        "items":         unique_items,
    }

    indent = 2 if pretty else None
    with open(out_file, "w") as f:
        json.dump(output, f, indent=indent, ensure_ascii=False)

    log.info("─" * 50)
    log.info(f"Done. {len(unique_items)} unique items written to {out_file}")
    log.info(f"  Intown items: {intown_count}")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        log.info(f"  {t}: {c}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape MBPZ hearing agendas")
    parser.add_argument("--months", type=int, default=12,     help="How many months back to scrape (default: 12)")
    parser.add_argument("--out",    type=str, default="mbpz_hearings.json", help="Output JSON file path")
    parser.add_argument("--pretty", action="store_true",      help="Pretty-print the output JSON")
    args = parser.parse_args()
    run(months=args.months, out_file=args.out, pretty=args.pretty)
