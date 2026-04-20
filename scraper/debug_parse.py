#!/usr/bin/env python3
"""
debug_parse.py - tests the parse logic on actual page text
"""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
URL = "https://mbpz.org/uncategorized/04-13-2026-hearing-agenda/"

r = requests.get(URL, headers=HEADERS, timeout=20)
soup = BeautifulSoup(r.text, "html.parser")
full_text = soup.get_text(separator="\n")
lines = full_text.split("\n")

print("Total lines:", len(lines))
print()

parcel_lines = []
for line in lines:
    if "Parcel" in line and re.search(r"[A-Z]\d{3}-\d{4}", line):
        parcel_lines.append(line)

print("Lines with 'Parcel' and parcel number:", len(parcel_lines))
print()

for i, line in enumerate(parcel_lines[:3]):
    print("=== LINE {} ===".format(i))
    print("RAW repr:", repr(line[:200]))
    print()
    # Test clean
    cleaned = line.replace("\xa0", " ").replace("\u00a0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    print("CLEANED:", repr(cleaned[:200]))
    print()
    # Test regex match
    starts = re.match(r"Parcel\s+Number", cleaned, re.IGNORECASE)
    print("Matches 'Parcel Number':", starts is not None)
    # Test pipe split
    parts = [p.strip() for p in cleaned.split("|")]
    print("Parts after split:", len(parts))
    for j, p in enumerate(parts):
        print("  Part {}: {}".format(j, repr(p)))
    print()
