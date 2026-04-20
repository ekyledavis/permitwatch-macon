#!/usr/bin/env python3
"""
diagnose.py - prints raw li tags from an MBPZ agenda page so we can see the exact structure
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "PermitWatch-INA/1.0"}
URL = "https://mbpz.org/uncategorized/04-13-2026-hearing-agenda/"

r = requests.get(URL, headers=HEADERS, timeout=20)
soup = BeautifulSoup(r.text, "html.parser")

content = (
    soup.find("div", class_="entry-content")
    or soup.find("article")
    or soup.find("main")
)

print("=== ALL LI TAGS IN CONTENT ===")
lis = content.find_all("li") if content else []
print("Total li tags found:", len(lis))
print()
for i, li in enumerate(lis):
    print("--- LI #{} ---".format(i))
    print("TEXT:", li.get_text(separator=" | ", strip=True)[:200])
    print()
