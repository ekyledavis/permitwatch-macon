#!/usr/bin/env python3
"""Tests the exact join and parse logic"""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
URL = "https://mbpz.org/uncategorized/04-13-2026-hearing-agenda/"

r = requests.get(URL, headers=HEADERS, timeout=20)
soup = BeautifulSoup(r.text, "html.parser")
full_text = soup.get_text(separator="\n")

def clean(text):
    text = text.replace("\xa0", " ").replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

lines = [clean(l) for l in full_text.split("\n")]
nonempty = [l for l in lines if l]

print("Testing join logic on first 3 parcel items:")
print()

found = 0
for idx, line in enumerate(nonempty):
    if re.match(r"^Parcel\s+Number\s+[A-Z]", line, re.IGNORECASE):
        next_line = nonempty[idx+1] if idx+1 < len(nonempty) else ""
        print("Parcel line:  ", repr(line[:60]))
        print("Next line:    ", repr(next_line[:80]))
        print("Starts with |:", next_line.startswith("|"))
        combined = line + " " + next_line if next_line.startswith("|") else line
        print("Combined:     ", repr(combined[:120]))
        # Try parsing
        parts = [clean(p) for p in combined.split("|")]
        print("Parts count:  ", len(parts))
        if len(parts) > 1:
            print("  Address:    ", parts[1])
            print("  Type:       ", parts[2] if len(parts)>2 else "")
        print()
        found += 1
        if found >= 3:
            break
