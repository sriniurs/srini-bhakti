#!/usr/bin/env python3
"""Maintain crawl-friendly static article URLs and the Google sitemap.

Run: python3 scripts/seo_sync.py
Check only: python3 scripts/seo_sync.py --check
Uses only Python's standard library.
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

BASE_URL = "https://bhakti.srinipresents.com"
ROOT = Path(__file__).resolve().parents[1]
SITEMAP = ROOT / "sitemap.xml"
SKIP_TOP = {
    ".git", ".github", "node_modules", "vendor", "dist", "build",
    "_site", "__pycache__", "scripts", ".venv", "venv",
}
SKIP_URLS = {"/search/", "/404/", "/admin/"}
HEAD_START = re.compile(r"<head\b[^>]*>", re.I)
CANONICAL_TAG = re.compile(
    r"<link\b(?=[^>]*\brel\s*=\s*(['\"])canonical\1)[^>]*>", re.I
)
HREF = re.compile(r"\bhref\s*=\s*(['\"])(.*?)\1", re.I | re.S)
NOINDEX_TAG = re.compile(r"<meta\b[^>]*\bname\s*=\s*(['\"])robots\1[^>]*>", re.I)
XMLNS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def url_for(file: Path) -> str:
    parent = file.relative_to(ROOT).parent.as_posix()
    path = "/" if parent == "." else "/" + "/".join(
        quote(part, safe="-._~") for part in parent.split("/")
    ) + "/"
    return path


def html_pages() -> list[tuple[str, Path]]:
    result = []
    for file in ROOT.rglob("index.html"):
        rel = file.relative_to(ROOT)
        if any(part.startswith(".") for part in rel.parts[:-1]):
            continue
        if rel.parts[0] in SKIP_TOP:
            continue
        path = url_for(file)
        if path in SKIP_URLS:
            continue
        result.append((path, file))
    return sorted(result)


def last_modified_in_git(file: Path) -> str | None:
    """Use the committed content date, not the date the sitemap was generated."""
    try:
        process = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--",
             file.relative_to(ROOT).as_posix()],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = process.stdout.strip()
    return value if process.returncode == 0 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None


def expected_sitemap(pages: list[tuple[str, Path]]) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="' + XMLNS + '">']
    for path, file in pages:
        lastmod = last_modified_in_git(file)
        lastmod_element = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        lines.append(
            "  <url><loc>" + html.escape(BASE_URL + path)
            + "</loc>" + lastmod_element + "</url>"
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def inspect_or_fix(path: str, file: Path, write: bool) -> list[str]:
    problems = []
    source = file.read_text(encoding="utf-8")
    canonical = CANONICAL_TAG.search(source)
    expected_url = BASE_URL + path
    if not re.search(r"<title\b", source, re.I):
        problems.append(f"{path}: missing title")
    if not re.search(r'<meta\b[^>]*\bname\s*=\s*["\x27]description["\x27]', source, re.I):
        problems.append(f"{path}: missing meta description")
    if canonical:
        href_match = HREF.search(canonical.group(0))
        existing = html.unescape(href_match.group(2)) if href_match else ""
        if existing.rstrip("/") + "/" != expected_url:
            problems.append(f"{path}: canonical mismatch ({existing})")
    else:
        problems.append(f"{path}: missing canonical")
        if write:
            match = HEAD_START.search(source)
            if match:
                source = source[:match.end()] + (
                    '\n<link rel="canonical" href="' + expected_url + '">'
                ) + source[match.end():]
            else:
                problems.append(f"{path}: missing head (cannot add canonical)")
    for match in NOINDEX_TAG.finditer(source):
        tag = match.group(0)
        if "noindex" in tag.lower():
            problems.append(f"{path}: robots noindex (requires editorial review)")
    if write and not canonical and HEAD_START.search(source):
        file.write_text(source, encoding="utf-8")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Do not modify files")
    args = parser.parse_args()
    pages = html_pages()
    warnings = []
    for path, file in pages:
        warnings.extend(inspect_or_fix(path, file, write=not args.check))
    paths = [p for p, _ in pages]
    content = expected_sitemap(pages)
    old = SITEMAP.read_text(encoding="utf-8") if SITEMAP.exists() else ""
    changed = old != content
    if changed and not args.check:
        SITEMAP.write_text(content, encoding="utf-8")
    # Validate generated sitemap for XML parsing and unique canonical site URLs.
    root = ET.fromstring(content)
    locations = [item.text for item in root.iter("{" + XMLNS + "}loc")]
    assert len(locations) == len(paths) == len(set(locations))
    print(f"SEO scan: {len(paths)} crawlable HTML pages; sitemap {'needs update' if changed else 'current'}.")
    if warnings:
        for msg in warnings[:60]:
            print("SEO NOTICE:", msg)
        if len(warnings) > 60:
            print(f"SEO NOTICE: {len(warnings)-60} further notices omitted")
    if args.check and (changed or warnings):
        return 1
    if any("noindex" in w or "mismatch" in w or "missing head" in w for w in warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
