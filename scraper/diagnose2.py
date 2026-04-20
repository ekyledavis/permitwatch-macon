#!/usr/bin/env python3
"""
diagnose2.py - prints raw HTML snippet from mbpz.org to see what we actually get
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
URL = "https://mbpz.org/uncategorized/04-13-2026-hearing-agenda/"

r = requests.get(URL, headers=HEADERS, timeout=20)
print("Status code:", r.status_code)
print("Content length:", len(r.text))
print()

soup = BeautifulSoup(r.text, "html.parser")

# Print all text that contains "Parcel"
print("=== LINES CONTAINING 'Parcel' ===")
full_text = soup.get_text()
lines = full_text.split("\n")
found = 0
for line in lines:
    line = line.strip()
    if "Parcel" in line and len(line) > 10:
        print(repr(line[:300]))
        found += 1
print("Total lines with Parcel:", found)
print()

# Show all tag types in content area
print("=== ALL TAGS IN ENTRY-CONTENT ===")
content = soup.find("div", class_="entry-content")
if content:
    tags = {}
    for tag in content.find_all():
        tags[tag.name] = tags.get(tag.name, 0) + 1
    for tag, count in sorted(tags.items(), key=lambda x: -x[1]):
        print("  <{}>: {}".format(tag, count))
else:
    print("No entry-content div found!")
    print("Body classes:", soup.find("body").get("class") if soup.find("body") else "none")
