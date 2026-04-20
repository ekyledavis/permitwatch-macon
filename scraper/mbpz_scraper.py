import os
#!/usr/bin/env python3
"""
mbpz_scraper.py - Macon-Bibb P&Z hearing scraper with PDF result parsing
Compatible with Python 3.9+
Dependencies: pip install requests beautifulsoup4 pdfplumber
"""

import re, json, time, argparse, logging, io
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("WARNING: pdfplumber not installed. Run: /opt/homebrew/bin/pip3 install pdfplumber --break-system-packages")

LISTING = "https://mbpz.org/category/hearing/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

INTOWN = [
    "vineville", "ingleside", "college", "napier", "huguenin", "rogers",
    "forsyth", "washington", "monroe", "spring", "orange", "bond",
    "boulevard", "oglethorpe", "tattnall", "poplar", "mulberry", "cherry",
    "walnut", "cotton", "riverside", "first", "second", "third", "fourth",
    "beall", "holt", "coleman", "highland",
    "anthony ave", "anthony st",
]

TYPES = {
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

OUTCOME_MAP = {
    "approved":  "Approved",
    "denied":    "Denied",
    "withdrawn": "Withdrawn",
    "continued": "Continued",
    "tabled":    "Tabled",
    "no action": "No Action",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("mbpz")


def clean(t):
    t = t.replace("\xa0", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", t).strip()


def ntype(t):
    l = t.lower()
    for k, v in TYPES.items():
        if k in l:
            return v
    return "Other"


def is_intown(a):
    l = a.lower()
    return any(s in l for s in INTOWN)


def getpage(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        time.sleep(1.2)
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        log.warning("Failed %s: %s", url, e)
        return None


def parsedate(t):
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", t)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except:
            return None
    return None


def find_pdf_url(results_page_url):
    """Find the PDF download link on a Hearing Results page."""
    soup = getpage(results_page_url)
    if not soup:
        return None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower() and "hearing-results" in href.lower():
            return href
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower() and "download" in a.get_text().lower():
            return href
    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower():
            return a["href"]
    return None


def parse_results_pdf(pdf_url):
    if not PDF_SUPPORT:
        return {}
    outcomes = {}
    try:
        r = requests.get(pdf_url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        time.sleep(1.0)
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        if not full_text.strip():
            log.warning("PDF has no extractable text: %s", pdf_url)
            return {}
        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
        # Group lines into items - each numbered item starts with "N. Parcel Number"
        groups = []
        current = []
        for line in lines:
            if re.match(r"^\d+\.\s+Parcel\s+Number", line, re.IGNORECASE):
                if current:
                    groups.append(current)
                current = [line]
            elif current:
                current.append(line)
        if current:
            groups.append(current)
        # Parse each group for parcel numbers and outcome
        for group in groups:
            parcels = re.findall(r"[A-Z]\d{3}-\d{4}", group[0])
            if not parcels:
                continue
            # Join all lines in this item and check last 80 chars for outcome
            full = " ".join(group)
            full_lower = full.lower()
            outcome = None
            for keyword, status in OUTCOME_MAP.items():
                if keyword in full_lower[-80:]:
                    outcome = status
                    break
            # Also check last line standalone (e.g. "WITHDRAWN BY STAFF")
            if not outcome and len(group) > 1:
                last = group[-1].lower().strip()
                for keyword, status in OUTCOME_MAP.items():
                    if keyword in last:
                        outcome = status
                        break
            if outcome:
                for parcel in parcels:
                    outcomes[parcel] = outcome
                    log.info("    %s -> %s", parcel, outcome)
    except Exception as e:
        log.warning("Failed to parse PDF %s: %s", pdf_url, e)
    log.info("  Parsed %d outcomes from PDF", len(outcomes))
    return outcomes


def build_outcomes_lookup(results_posts):
    """Build master lookup of {parcel_number: outcome} from all Results PDFs."""
    all_outcomes = {}
    for post in results_posts:
        log.info("Getting outcomes: %s", post["title"])
        pdf_url = find_pdf_url(post["url"])
        if not pdf_url:
            log.warning("  No PDF found for %s", post["url"])
            continue
        log.info("  PDF: %s", pdf_url)
        outcomes = parse_results_pdf(pdf_url)
        all_outcomes.update(outcomes)
    log.info("Total outcomes in lookup: %d", len(all_outcomes))
    return all_outcomes


def get_hearing_links(cutoff):
    """Paginate through listing and collect all hearing post links."""
    all_posts = {}
    for page in range(1, 50):
        url = LISTING if page == 1 else "{}?page={}".format(LISTING, page)
        log.info("Page %d", page)
        soup = getpage(url)
        if not soup:
            break
        found_on_page = 0
        hit_cutoff = False
        for a in soup.find_all("a", href=True):
            title = clean(a.get_text(strip=True))
            href = a["href"]
            if "mbpz.org/uncategorized/" not in href:
                continue
            if not re.search(r"\d{2}[/\-]\d{2}[/\-]\d{4}", title):
                continue
            d = parsedate(title)
            if not d:
                continue
            furl = urljoin("https://mbpz.org", href)
            if furl not in all_posts:
                if d < cutoff:
                    log.info("Cutoff at: %s", title)
                    hit_cutoff = True
                    break
                l = title.lower()
                if "result" in l:
                    ptype = "Hearing Result"
                elif "draft" in l:
                    ptype = "Draft Agenda"
                elif "design review" in l:
                    ptype = "Design Review Board"
                else:
                    ptype = "Hearing Agenda"
                all_posts[furl] = {"title": title, "url": furl, "date": d.strftime("%Y-%m-%d"), "post_type": ptype}
                log.info("  Found: %s", title)
                found_on_page += 1
        if hit_cutoff:
            break
        if found_on_page == 0:
            log.info("No new posts on page %d, done.", page)
            break
    result = list(all_posts.values())
    log.info("%d posts found total", len(result))
    return result



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

def scrape_detail(post, outcomes_lookup=None, geocache=None):
    """Scrape a single hearing page, applying PDF outcomes where available."""
    log.info("Scraping: %s", post["title"])
    soup = getpage(post["url"])
    if not soup:
        return []

    lines = [clean(l) for l in soup.get_text(separator="\n").split("\n")]
    nonempty = [l for l in lines if l]
    items = []
    seen = set()

    for idx, line in enumerate(nonempty):
        if not re.match(r"^Parcel\s+Number\s+[A-Z]", line, re.IGNORECASE):
            continue
        nxt = nonempty[idx + 1] if idx + 1 < len(nonempty) else ""
        combined = line + " " + nxt if nxt.startswith("|") else line
        parts = [clean(p) for p in combined.split("|")]
        if len(parts) < 3:
            continue
        parcels = re.findall(r"[A-Z]\d{3}-\d{4}", parts[0])
        if not parcels:
            continue
        parcel = parcels[0]
        if parcel in seen:
            continue
        seen.add(parcel)

        address   = parts[1] if len(parts) > 1 else ""
        req       = parts[2] if len(parts) > 2 else ""
        desc      = parts[3] if len(parts) > 3 else ""
        zoning    = re.sub(r"\s*[Dd]istrict\s*$", "", parts[4] if len(parts) > 4 else "").strip()
        applicant = re.sub(r",?\s*applicant\s*$", "", parts[5] if len(parts) > 5 else "", flags=re.IGNORECASE).strip()

        if re.search(r"withdrawn", combined, re.IGNORECASE):
            snote = "Withdrawn"
        elif re.search(r"continued", combined, re.IGNORECASE):
            snote = "Continued"
        else:
            snote = ""

        if not address:
            continue

        # Status: PDF outcomes take priority
        if outcomes_lookup and parcel in outcomes_lookup:
            status = outcomes_lookup[parcel]
        elif "result" in post["post_type"].lower():
            status = "Decision Issued"
        elif snote == "Withdrawn":
            status = "Withdrawn"
        elif "draft" in post["post_type"].lower():
            status = "Pending Hearing"
        else:
            status = "Under Review"

        is_result  = "result" in post["post_type"].lower()
        hearing_dt = post["date"] + "T13:30:00" if not is_result else None
        item_id    = "MBPZ-{}-{}".format(post["date"], parcel)

        items.append({
            "id":            item_id,
            "parcels":       parcels,
            "address":       address,
            "request_type":  ntype(req),
            "description":   desc,
            "zoning":        zoning,
            "applicant":     applicant,
            "status_note":   snote,
            "status":        status,
            "intown":        is_intown(address),
            "neighborhood":  geocode_neighborhood(address, geocache) if geocache is not None else (street_neighborhood(address) or "Macon"),
            "hearing_date":  post["date"],
            "hearing":       hearing_dt,
            "submitted":     post["date"],
            "hearing_title": post["title"],
            "hearing_url":   post["url"],
            "post_type":     post["post_type"],
            "reactions":     {"support": 0, "oppose": 0, "neutral": 0},
            "comments":      [],
        })

    log.info("  -> %d items", len(items))
    return items


def run(months=12, out="public/permitwatch_data.json", pretty=False):
    cutoff = datetime.now() - timedelta(days=months * 30)
    log.info("Scraping from %s to today", cutoff.strftime("%Y-%m-%d"))

    posts = get_hearing_links(cutoff)
    if not posts:
        log.error("No posts found.")
        return

    results_posts = [p for p in posts if p["post_type"] == "Hearing Result"]
    log.info("Building outcomes from %d results pages...", len(results_posts))
    outcomes_lookup = build_outcomes_lookup(results_posts)

    # Load geocoding cache
    geocache = load_geocache()
    log.info("Loaded %d cached geocodes", len(geocache))

    all_items = []
    seen = set()
    for post in posts:
        for item in scrape_detail(post, outcomes_lookup, geocache):
            if item["id"] not in seen:
                seen.add(item["id"])
                all_items.append(item)

    all_items.sort(key=lambda x: x.get("hearing_date") or "", reverse=True)

    tc = {}
    for i in all_items:
        tc[i["request_type"]] = tc.get(i["request_type"], 0) + 1

    sc = {}
    for i in all_items:
        sc[i["status"]] = sc.get(i["status"], 0) + 1

    ic = sum(1 for i in all_items if i["intown"])

    output = {
        "scraped_at":       datetime.now().isoformat(),
        "source":           LISTING,
        "months_back":      months,
        "total_items":      len(all_items),
        "intown_items":     ic,
        "type_breakdown":   tc,
        "status_breakdown": sc,
        "items":            all_items,
    }

    with open(out, "w") as f:
        json.dump(output, f, indent=2 if pretty else None, ensure_ascii=False)

    log.info("-" * 50)
    log.info("Done. %d items (%d intown) -> %s", len(all_items), ic, out)
    log.info("Types:")
    for t, c in sorted(tc.items(), key=lambda x: -x[1]):
        log.info("  %s: %d", t, c)
    log.info("Statuses:")
    for s, c in sorted(sc.items(), key=lambda x: -x[1]):
        log.info("  %s: %d", s, c)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--out", default="public/permitwatch_data.json")
    p.add_argument("--pretty", action="store_true")
    a = p.parse_args()
    run(a.months, a.out, a.pretty)
