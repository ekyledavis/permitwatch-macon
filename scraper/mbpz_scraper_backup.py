#!/usr/bin/env python3
import re, json, time, argparse, logging
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

LISTING = "https://mbpz.org/category/hearing/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
INTOWN = ["vineville","ingleside","college","napier","huguenin","rogers","forsyth","washington","monroe","spring","orange","bond","boulevard","oglethorpe","tattnall","poplar","mulberry","cherry","walnut","cotton","riverside","first","second","third","fourth","beall","holt","coleman","highland","anthony ave","anthony st"]
TYPES = {"certificate of appropriateness":"Certificate of Appropriateness","conditional use":"Conditional Use","rezoning":"Rezoning","variance":"Variance","special exception":"Special Exception","violation":"Violation / Revocation","revocation":"Violation / Revocation","subdivision":"Subdivision","annexation":"Annexation","text amendment":"Text Amendment","planned development":"Planned Development"}

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

def get_hearing_links(cutoff):
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

def scrape_detail(post):
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
        address = parts[1] if len(parts) > 1 else ""
        req = parts[2] if len(parts) > 2 else ""
        desc = parts[3] if len(parts) > 3 else ""
        zoning = re.sub(r"\s*[Dd]istrict\s*$", "", parts[4] if len(parts) > 4 else "").strip()
        applicant = re.sub(r",?\s*applicant\s*$", "", parts[5] if len(parts) > 5 else "", flags=re.IGNORECASE).strip()
        if re.search(r"withdrawn", combined, re.IGNORECASE):
            snote = "Withdrawn"
        elif re.search(r"continued", combined, re.IGNORECASE):
            snote = "Continued"
        else:
            snote = ""
        if not address:
            continue
        item_id = "MBPZ-{}-{}".format(post["date"], parcel)
        is_result = "result" in post["post_type"].lower()
        if is_result:
            status = "Decision Issued"
        elif snote == "Withdrawn":
            status = "Withdrawn"
        elif "draft" in post["post_type"].lower():
            status = "Pending Hearing"
        else:
            status = "Under Review"
        hearing_dt = post["date"] + "T13:30:00" if not is_result else None
        items.append({
            "id": item_id,
            "parcels": parcels,
            "address": address,
            "request_type": ntype(req),
            "description": desc,
            "zoning": zoning,
            "applicant": applicant,
            "status_note": snote,
            "status": status,
            "intown": is_intown(address),
            "neighborhood": "Macon",
            "hearing_date": post["date"],
            "hearing": hearing_dt,
            "submitted": post["date"],
            "hearing_title": post["title"],
            "hearing_url": post["url"],
            "post_type": post["post_type"],
            "reactions": {"support": 0, "oppose": 0, "neutral": 0},
            "comments": [],
        })
    log.info("  -> %d items", len(items))
    return items

def run(months=12, out="public/permitwatch_data.json", pretty=False):
    cutoff = datetime.now() - timedelta(days=months * 30)
    log.info("Scraping from %s", cutoff.strftime("%Y-%m-%d"))
    posts = get_hearing_links(cutoff)
    if not posts:
        log.error("No posts.")
        return
    all_items = []
    seen = set()
    for post in posts:
        for item in scrape_detail(post):
            if item["id"] not in seen:
                seen.add(item["id"])
                all_items.append(item)
    all_items.sort(key=lambda x: x.get("hearing_date") or "", reverse=True)
    tc = {}
    for i in all_items:
        tc[i["request_type"]] = tc.get(i["request_type"], 0) + 1
    ic = sum(1 for i in all_items if i["intown"])
    output = {
        "scraped_at": datetime.now().isoformat(),
        "source": LISTING,
        "months_back": months,
        "total_items": len(all_items),
        "intown_items": ic,
        "type_breakdown": tc,
        "items": all_items,
    }
    with open(out, "w") as f:
        json.dump(output, f, indent=2 if pretty else None, ensure_ascii=False)
    log.info("Done. %d items (%d intown) -> %s", len(all_items), ic, out)
    for t, c in sorted(tc.items(), key=lambda x: -x[1]):
        log.info("  %s: %d", t, c)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--out", default="public/permitwatch_data.json")
    p.add_argument("--pretty", action="store_true")
    a = p.parse_args()
    run(a.months, a.out, a.pretty)
