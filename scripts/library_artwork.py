"""Reuse the linked works' own illustrations in discovery and article cards."""
import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "assets/editorial/linked-works"
PUBLIC_PREFIX = "/assets/editorial/linked-works/"
PAINTED_PREFIX = "/assets/editorial/bhakti-library/painted-tile-"
CARD_MARK = re.compile(r"<!-- library:card -->.*?<!-- /library:card -->", re.S)
TILE = re.compile(
    r'<a\b[^>]*\bhref="(/[^"#?]+/)(?:#[^"]*)?"[^>]*>\s*<div\b[^>]*\bclass="tile-art"[^>]*>',
    re.I,
)
HOME_TILE = re.compile(r'<a href="(/[^"#?]+/)" data-library-card>')
COVER = re.compile(r'<(?P<tag>figure|div)\b[^>]*\bclass="cover-art"[^>]*>(.*?)</(?P=tag)>', re.S)
IMAGE = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"', re.I)
SVG = re.compile(r"<svg\b.*?</svg>", re.S)
LEGACY_SVG = re.compile(r'<svg\b(?=[^>]*\bclass="(?:[^"]*\s)?(?:coverart|hero)(?:\s[^"]*)?")[^>]*>.*?</svg>', re.S)
ILLUSTRATION = re.compile(r'<svg\b(?=[^>]*\brole="img")(?=[^>]*\baria-label="[^"]+")[^>]*>.*?</svg>', re.S)
OG = re.compile(r'<meta\b[^>]*\bproperty="og:image"[^>]*\bcontent="([^"]+)"', re.I)


def local_image(value):
    url = urlsplit(value)
    path = url.path
    if url.netloc not in ("", "bhakti.srinipresents.com") or not path.startswith("/"):
        return None
    if (ROOT / path.lstrip("/")).is_file() and path.lower().endswith((".avif", ".webp", ".jpg", ".jpeg", ".png", ".svg")):
        return path
    return None


def vector_asset(route, vector, generated):
    svg = vector[0]
    if "xmlns=" not in svg.partition(">")[0]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    try:
        ElementTree.fromstring(svg)
    except ElementTree.ParseError:
        return None
    key = hashlib.sha256(route.encode("utf-8")).hexdigest()[:16] + ".svg"
    generated[key] = svg + "\n"
    return PUBLIC_PREFIX + key


def cover_asset(route, source, generated):
    cover = COVER.search(source)
    if cover:
        if image := IMAGE.search(cover[2]):
            if local := local_image(image[1]):
                return local
        if (vector := SVG.search(cover[2])) and (asset := vector_asset(route, vector, generated)):
            return asset
    if hero := re.search(r'<header class="hero">.*?</header>', source, re.S):
        if image := IMAGE.search(hero[0]):
            if local := local_image(image[1]):
                return local
    if (vector := LEGACY_SVG.search(source)) and (asset := vector_asset(route, vector, generated)):
        return asset
    if (meta := OG.search(source)) and (asset := local_image(meta[1])):
        return asset
    if vector := ILLUSTRATION.search(source):
        return vector_asset(route, vector, generated)
    return None


def img(source):
    painted = source.startswith(PAINTED_PREFIX)
    return f'<img class="library-card-illustration" src="{source}" width="160" height="120" loading="lazy" decoding="async" alt=""{" data-painted-tile" if painted else ""}>'


def illustrate_cards(source, artwork, matcher=TILE):
    def show(match):
        path = artwork.get(match[1])
        return match[0] + "<!-- library:card -->" + img(path) + "<!-- /library:card -->" if path else match[0]
    return matcher.sub(show, CARD_MARK.sub("", source))


def artwork_by_route(pages, painted):
    generated = {}
    found = {}
    for route, page in pages.items():
        key = hashlib.sha256(route.encode("utf-8")).hexdigest()[:16]
        dedicated_painting = f"{PAINTED_PREFIX}{key}.webp"
        if local_image(dedicated_painting):
            found[route] = dedicated_painting
            continue
        if route in painted:
            found[route] = painted[route]
            continue
        asset = cover_asset(route, page["base"], generated)
        if asset:
            found[route] = asset
    return found, generated
