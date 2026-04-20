#!/usr/bin/env python3
"""Shows context around parcel lines to understand the structure"""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
URL = "https://mbpz.org/uncategorized/04-13-2026-hearing-agenda/"

r = requests.get(URL, headers=HEADERS, timeout=20)
soup = BeautifulSoup(r.text, "html.parser")
full_text = soup.get_text(separator="\n")
lines = [l.replace("\xa0"," ").strip() for l in full_text.split("\n")]
lines = [l for l in lines if l]  # remove empty lines

# Find first parcel line and print 10 lines of context
for i, line in enumerate(lines):
    if re.match(r"Parcel\s+Number", line, re.IGNORECASE):
        print("=== PARCEL LINE at index {} ===".format(i))
        start = max(0, i-2)
        end = min(len(lines), i+10)
        for j in range(start, end):
            marker = ">>>" if j == i else "   "
            print("{} {}: {}".format(marker, j, repr(lines[j])))
        print()
        break  # just show the first one
