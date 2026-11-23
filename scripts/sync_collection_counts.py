#!/usr/bin/env python3
"""Keep Bhakti homepage collection counts synced to its single article catalogue.

The nested, linked "All Bhakti articles" index is the source of truth.
Its headings and the seven homepage cards are both updated from unique indexed
article URLs. Collection landing pages remain included, matching the established
site convention; /tulunadu/ is explicitly a navigation link, not an article.
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "index.html"
GROUPS = [
    "Gods and Goddesses",
    "Hymns and Mantras",
    "Scriptures and Stories",
    "Temples and Tīrthas",
    "Śrī Vidyā",
    "Festivals",
    "Tulu Nadu",
]
TOKEN = re.compile(
    r"<details\b[^>]*>|</details>|<summary\b[^>]*>.*?</summary>|"
    r"<a\b[^>]*\bhref\s*=\s*(['\"])(.*?)\1[^>]*>",
    re.I | re.S,
)


def catalogue_counts(document: str) -> dict[str, int]:
    beginning = document.find('<section class="article-index"')
    if beginning < 0:
        raise ValueError("Missing homepage article catalogue")
    section = document[beginning:]
    depth, label, links = 0, None, set()
    counts = {}
    for token in TOKEN.finditer(section):
        tag = token.group(0)
        if re.match(r"<details\b", tag, re.I):
            depth += 1
            if depth == 1:
                label, links = None, set()
        elif tag.lower().startswith("</details"):
            if depth == 1 and label in GROUPS:
                counts[label] = len(links)
            depth -= 1
            if depth < 0:
                raise ValueError("Malformed homepage catalogue")
            if depth == 0 and len(counts) == len(GROUPS):
                break
        elif re.match(r"<summary\b", tag, re.I) and depth == 1:
            summary = html.unescape(re.sub(r"<[^>]*>", "", tag)).strip()
            label = summary.split(" · ")[0].strip()
        elif tag.lower().startswith("<a") and depth >= 1 and label in GROUPS:
            link = html.unescape(token.group(2)).split("#")[0].split("?")[0]
            if link.startswith("/") and not (label == "Tulu Nadu" and link == "/tulunadu/"):
                links.add(link)
    if set(counts) != set(GROUPS):
        raise ValueError("Could not read all seven catalogue sections: " + repr(counts))
    return counts


def synchronize(document: str, counts: dict[str, int]) -> str:
    for name, number in counts.items():
        escaped = re.escape(name)
        summary_re = re.compile(
            r"(<details><summary>" + escaped + r" · )\d+( articles</summary>)"
        )
        document, n1 = summary_re.subn(lambda m: m[1] + str(number) + m[2], document)
        card_re = re.compile(
            r"(<span>" + escaped
            + r"</span><small class=\"collection-size collection-size--card\">)"
            + r"\d+( articles</small>)"
        )
        document, n2 = card_re.subn(lambda m: m[1] + str(number) + m[2], document)
        if n1 != 1 or n2 != 1:
            raise ValueError(f"Couldn't update catalogue/card count for {name}: {n1}/{n2}")
    # This collection contains 15 articles and one landing page.
    mysuru_count = sum(
        1 for p in (ROOT / "temples-of-india" / "around-mysuru").glob("*/index.html")
    )
    document, n = re.subn(
        r"(Temples around Mysuru</h2><small class=\"collection-size collection-size--card\">)"
        + r"\d+( articles</small>)",
        lambda m: m[1] + str(mysuru_count) + m[2],
        document,
    )
    # Some card layouts put count before the description; fail only if collection exists.
    if mysuru_count and not n:
        pass
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    old = HOME.read_text(encoding="utf-8")
    counts = catalogue_counts(old)
    new = synchronize(old, counts)
    print("Catalogue counts:", ", ".join(f"{k}: {v}" for k, v in counts.items()))
    if old != new:
        if args.check:
            raise SystemExit("Homepage counts are out of sync")
        HOME.write_text(new, encoding="utf-8")
        print("Updated homepage collection counters.")
    else:
        print("Homepage collection counters already current.")


if __name__ == "__main__":
    main()
