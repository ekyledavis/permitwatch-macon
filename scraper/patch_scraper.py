#!/usr/bin/env python3
"""Patches the parse_results_pdf function in mbpz_scraper.py"""
import re

with open("scraper/mbpz_scraper.py") as f:
    content = f.read()

# Find and replace the parse_results_pdf function
old_start = "def parse_results_pdf(pdf_url):"
old_end = "    log.info(\"  Parsed %d outcomes from PDF\", len(outcomes))\n    return outcomes"

start_idx = content.find(old_start)
end_idx = content.find(old_end) + len(old_end)

if start_idx == -1:
    print("ERROR: Could not find parse_results_pdf function")
    exit(1)

new_func = '''def parse_results_pdf(pdf_url):
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
                    full_text += text + "\\n"
        if not full_text.strip():
            log.warning("PDF has no extractable text: %s", pdf_url)
            return {}
        lines = [l.strip() for l in full_text.split("\\n") if l.strip()]
        # Group lines into items - each numbered item starts with "N. Parcel Number"
        groups = []
        current = []
        for line in lines:
            if re.match(r"^\\d+\\.\\s+Parcel\\s+Number", line, re.IGNORECASE):
                if current:
                    groups.append(current)
                current = [line]
            elif current:
                current.append(line)
        if current:
            groups.append(current)
        # Parse each group for parcel numbers and outcome
        for group in groups:
            parcels = re.findall(r"[A-Z]\\d{3}-\\d{4}", group[0])
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
    return outcomes'''

new_content = content[:start_idx] + new_func + content[end_idx:]

with open("scraper/mbpz_scraper.py", "w") as f:
    f.write(new_content)

print("Patched successfully!")
print("New function length:", len(new_func))

# Verify
with open("scraper/mbpz_scraper.py") as f:
    check = f.read()
print("groups in file:", "groups" in check)
print("items_text NOT in file:", "items_text" not in check)
