"""Build Bhakti's static search and shared reading navigation from published pages."""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from seo_sync import BASE_URL, html_pages
from sync_collection_counts import GROUPS
from library_artwork import CARD_MARK, DESTINATION, HOME_TILE, PUBLIC_PREFIX, artwork_by_route, illustrate_cards, img, local_image

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "index.html"
SEARCH = ROOT / "search/index.html"
REGISTRY = ROOT / "assets/library-registry.json"
COLLECTIONS = dict(zip(GROUPS, (
    "/why-do-we/", "/gods/", "/hymns/", "/scriptures/", "/temples-of-india/", "/srividya/",
    "/festivals/", "/karnataka-cultures/",
)))
THEMES = dict(zip(GROUPS, ("why", "gods", "hymns", "scriptures", "temples", "srividya", "festivals", "tulu")))
ART = "/assets/editorial/bhakti-library/"
PAINTINGS = {
    **{path: THEMES[group] for group, path in COLLECTIONS.items()},
    "/festivals/kartika/": "kartika-banner",
    "/srividya/lalita-sahasranama/": "lalita-sahasranama",
    "/srividya/saundaryalahari/": "saundaryalahari",
    "/srividya/khadgamala/": "khadgamala",
    "/devi/devi-mahatmya/": "devi-mahatmya",
    "/hanuman/chalisa/": "hanuman-chalisa",
    "/temples-of-india/12-jyotirlingas/": "jyotirlingas",
    "/temples-of-india/pancha-kedar/": "pancha-kedar",
    "/temples-of-india/sapta-puri/": "sapta-puri",
}
CARD_PAINTINGS = {
    "/shiva/shiva-family-and-symbols/": "painted-tile-shiva-family",
    "/vishnu/dashavatara/": "painted-tile-dashavatara",
    "/devi/ashta-lakshmi/": "painted-tile-ashta-lakshmi",
    "/hanuman/stories/": "painted-tile-hanuman-stories",
    "/subramanya/": "painted-tile-subramanya",
    "/ganesha/": "painted-tile-ganesha",
    "/vishnu/bhagavad-gita/": "painted-tile-bhagavad-gita",
    "/srividya/lalita-sahasranama/": "painted-tile-lalita-sahasranama",
    "/vishnu/vishnu-sahasranama/": "painted-tile-vishnu-sahasranama",
    "/shiva/sri-rudram/": "painted-tile-sri-rudram",
    "/hanuman/chalisa/": "painted-tile-hanuman-chalisa",
    "/why-do-we/home-puja/": "painted-tile-home-puja",
    "/temples-of-india/how-to-read-a-hindu-temple/": "painted-tile-temple-architecture",
    "/festivals/deepavali/": "painted-tile-deepavali",
    "/festivals/holi/": "painted-tile-holi",
    "/tulunadu/culture/kambala/": "painted-tile-kambala",
    "/tulunadu/culture/yakshagana/": "painted-tile-yakshagana",
    "/tulunadu/temples/udupi-srikrishna/": "painted-tile-udupi",
    "/temples-of-india/karnataka/gokarna/": "painted-tile-gokarna",
    "/vishnu/garuda-purana/": "card-garuda-purana",
    "/vishnu/garuda-purana/part-a/": "card-garuda-purana-a",
    "/vishnu/garuda-purana/part-b/": "card-garuda-purana-b",
    "/temples-of-india/kerala/padmanabhaswamy/": "card-padmanabhaswamy",
    "/temples-of-india/kerala/mannarasala/": "card-mannarasala",
    "/temples-of-india/tamil-nadu/kanchipuram-varadaraja/": "card-kanchipuram-varadaraja",
    "/temples-of-india/sapta-puri/ayodhya/": "card-ayodhya",
}
PARENT_STORIES = {
    "/temples-of-india/around-mysuru/chamundeshwari/": (
        ("https://srinipresents.com/chamundi-steps/", "Who Counted Chamundi’s 1,000 Steps?"),
    ),
    "/festivals/deepavali/": (
        ("https://srinipresents.com/darkest-night/", "Why the Festival of Lights Falls on the Darkest Night"),
        ("https://srinipresents.com/diya-makers/", "The Last Diya Makers of Doora"),
    ),
    "/temples-of-india/kerala/sabarimala/": (
        ("https://srinipresents.com/sabarimala-vow/", "The 41-Day Sabarimala Vow, Decoded"),
    ),
    "/why-do-we/home-puja/": (
        ("https://srinipresents.com/mysore-agarbathi/", "Mysore Agarbathi: The Smoke That Made Mysuru Famous"),
    ),
}
START = "<!-- library:header -->"
END = "<!-- /library:header -->"
FOOT_START = "<!-- library:footer -->"
FOOT_END = "<!-- /library:footer -->"
HEADER_BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END) + "\n", re.S)
FOOTER_BLOCK = re.compile(re.escape(FOOT_START) + r".*?" + re.escape(FOOT_END) + "\n", re.S)
ART_BLOCK = re.compile(r"<!-- library:art -->.*?<!-- /library:art -->", re.S)
TITLE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.I | re.S)
BODY = re.compile(r"<body\b[^>]*>", re.I)
BODY_END = re.compile(r"</body\s*>", re.I)
REDIRECT = re.compile(r"<meta\b[^>]*\bhttp-equiv\s*=\s*['\"]?refresh", re.I)
ARCHIVE = re.compile(r'<section class="article-index"[\s\S]*?</section>')
RESULTS = re.compile(r'(<ul id="reader-results">).*?(</ul>)', re.S)
BRAND_SUFFIX = re.compile(r"\s*[·|]\s*(?:Bhakti(?:\s*[|·]\s*)?)?(?:Srini[ .]Presents|Bhakti)\s*$", re.I)


class Archive(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.depth = 0
        self.summary = None
        self.group = None
        self.members = defaultdict(list)
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == "details":
            self.depth += 1
        if tag == "summary" and self.depth == 1:
            self.summary = []
        if tag == "a" and self.group:
            url = urlsplit(dict(attrs).get("href", ""))
            if not url.netloc and url.path.startswith("/") and url.path not in self.members[self.group]:
                self.members[self.group].append(url.path)

    def handle_endtag(self, tag):
        if tag == "summary" and self.summary is not None:
            label = "".join(self.summary).split(" · ")[0].strip()
            self.group = label if label in COLLECTIONS else None
            self.summary = None
        if tag == "details":
            self.depth -= 1
            if self.depth == 0:
                self.group = None

    def handle_data(self, data):
        if self.summary is not None:
            self.summary.append(data)


class Destinations(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.paths = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        url = urlsplit(dict(attrs).get("href", ""))
        if url.netloc in ("", urlsplit(BASE_URL).netloc) and url.path.startswith("/") and url.path not in self.paths:
            self.paths.append(url.path)


def display_title(source, route):
    title = TITLE.search(source)
    if not title:
        return route.strip("/")
    return BRAND_SUFFIX.sub("", " ".join(html.unescape(title[1]).split())).strip()


def link(route, title, label="", artwork=None):
    prefix = f'<span>{html.escape(label)}</span>' if label else ""
    illustration = img(artwork[route]) if artwork and route in artwork else ""
    if illustration:
        return f'<a class="library-art-link" href="{html.escape(route)}">{illustration}<div>{prefix}{html.escape(title)}</div></a>'
    return f'<a href="{html.escape(route)}">{prefix}{html.escape(title)}</a>'


def ancestors(path):
    parts = path.strip("/").split("/")
    return ["/" + "/".join(parts[:n]) + "/" for n in range(1, len(parts))]


def load_pages():
    pages = {}
    for route, file in html_pages():
        source = file.read_text(encoding="utf-8")
        if route == "/" or REDIRECT.search(source[:7000]):
            continue
        body = CARD_MARK.sub("", ART_BLOCK.sub("", FOOTER_BLOCK.sub("", HEADER_BLOCK.sub("", source))))
        pages[route] = {"file": file, "source": source, "base": body, "title": display_title(body, route)}
    return pages


def build_registry(home, pages):
    archive = Archive(ARCHIVE.search(home)[0])
    if set(archive.members) != set(COLLECTIONS):
        raise ValueError("Homepage archive must contain the eight collection headings")
    memberships = defaultdict(list)
    for group in GROUPS:
        for route in archive.members[group]:
            if route in pages and route != COLLECTIONS[group]:
                memberships[route].append(group)
    for route in pages:
        for group, anchor in COLLECTIONS.items():
            if route.startswith(anchor) and group not in memberships[route]:
                memberships[route].append(group)
    for route in pages:
        for parent in reversed(ancestors(route)):
            if memberships[parent]:
                for group in memberships[parent]:
                    if group not in memberships[route]:
                        memberships[route].append(group)
                break
    series = {}
    for route, page in pages.items():
        if route in COLLECTIONS.values():
            continue
        children = [
            path for path in Destinations(page["base"]).paths
            if path in pages and path != route and ancestors(path)[-1:] == [route]
        ]
        if len(children) >= 2:
            series[route] = children
    registry = []
    for route, page in sorted(pages.items()):
        registry.append({
            "path": route,
            "title": page["title"],
            "collections": memberships[route],
            "kind": "collection" if route in COLLECTIONS.values() else "series" if route in series else "article",
            **({"chapters": series[route]} if route in series else {}),
        })
    return registry, series, memberships


def json_ld(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", r"\u003c")


def article_schema(route, page):
    scripts = re.findall(r'<script\b[^>]*\btype=["\x27]application/ld\+json["\x27][^>]*>(.*?)</script>', page["base"], re.I | re.S)
    if any(re.search(r'"@type"\s*:\s*"(?:Article|NewsArticle|BlogPosting)"', script) for script in scripts):
        return ""
    metadata = {}

    class Meta(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == "meta":
                values = dict(attrs)
                key = values.get("name") or values.get("property")
                if key and values.get("content"):
                    metadata.setdefault(key.lower(), values["content"].strip())

    head = re.split(r"</head\s*>", page["base"], maxsplit=1, flags=re.I)[0]
    Meta().feed(head)
    address = BASE_URL + route
    value = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": page["title"], "url": address, "mainEntityOfPage": address,
        "isPartOf": {"@id": BASE_URL + "/#website"},
        "publisher": {"@type": "Organization", "@id": "https://srinipresents.com/#organization",
                      "name": "srini.presents", "url": "https://srinipresents.com/"},
    }
    if description := metadata.get("description"):
        value["description"] = description
    if image := local_image(metadata.get("og:image", "")):
        value["image"] = BASE_URL + image
    return f'\n<script type="application/ld+json">{json_ld(value)}</script>'


def header(route, page, pages, memberships, counts, articles):
    groups = memberships[route]
    group = next((g for g, path in COLLECTIONS.items() if route.startswith(path)), groups[0] if groups else None)
    parents = [path for path in ancestors(route) if path in pages]
    crumb_routes = [COLLECTIONS[group]] if group and COLLECTIONS[group] != route else []
    crumb_routes.extend(path for path in parents if path not in crumb_routes)
    crumbs = [link("/", "Home")] + [link(path, pages[path]["title"]) for path in crumb_routes]
    crumbs.append(f'<span aria-current="page">{html.escape(page["title"])}</span>')
    trail = "".join(f"<li>{crumb}</li>" for crumb in crumbs)
    destinations = [("/", "Home"), *((path, pages[path]["title"]) for path in crumb_routes), (route, page["title"])]
    schema = json_ld({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": name, "item": BASE_URL + path}
            for index, (path, name) in enumerate(destinations, 1)
        ],
    })
    article = article_schema(route, page) if route in articles else ""
    total = f'<p class="library-collection-size">{counts[group]} published articles</p>' if group and route == COLLECTIONS[group] else ""
    theme = THEMES.get(group, "gods")
    accent = f'<i class="library-theme-{theme}" aria-hidden="true"></i>'
    return f"""{START}
<link rel="stylesheet" href="/assets/editorial/library.css">
<div class="library-reader-head">
  {accent}<a class="library-logo" href="/" aria-label="Bhakti home"><img src="/assets/editorial/lotus.svg" width="38" height="31" alt=""> <span>Bhakti<small>srini.presents</small></span></a>
  <a href="/#collections">Collections</a><a href="/search/">Search</a>
</div>
<nav class="library-crumb" aria-label="Breadcrumb"><ol>{trail}</ol></nav>
{total}<script type="application/ld+json">{schema}</script>{article}
{END}
"""


def footer(route, pages, series, memberships, artwork):
    sections = []
    if route in series and "data-library-chapter-list" not in pages[route]["base"]:
        children = "".join(f'<li>{link(path, pages[path]["title"], artwork=artwork)}</li>' for path in series[route])
        sections.append(f'<section><h2>Published chapters</h2><p>{len(series[route])} available</p><ol>{children}</ol></section>')
    elif route not in series:
        parent = next((p for p in reversed(ancestors(route)) if route in series.get(p, ())), None)
        if parent:
            works = series[parent]
            offset = works.index(route)
            before = works[offset - 1:offset] if offset else []
            after = works[offset + 1:offset + 2]
            previous = [link(p, pages[p]["title"], "Previous chapter", artwork) for p in before]
            following = [link(p, pages[p]["title"], "Next chapter", artwork) for p in after]
            sections.append('<nav aria-label="Chapter navigation">' + "".join(previous + following) + "</nav>")
        related = [p for p in Destinations(pages[route]["base"]).paths
                   if p in pages and p != route and p not in COLLECTIONS.values()
                   and p not in ancestors(route) and set(memberships[route]) & set(memberships[p])][:3]
        if related:
            sections.append('<section><h2>Related reading</h2><ul>' + "".join(
                f'<li>{link(path, pages[path]["title"], artwork=artwork)}</li>' for path in related) + "</ul></section>")
    if stories := PARENT_STORIES.get(route):
        items = "".join(f"<li>{link(url, title)}</li>" for url, title in stories)
        sections.append(f"<section><h2>Related stories from srini.presents</h2><ul>{items}</ul></section>")
    main_group = memberships[route][0] if memberships[route] else None
    if main_group and (collection := COLLECTIONS[main_group]) != route:
        sections.append(link(collection, f"Return to {main_group}"))
    extra = "\n".join(sections)
    return f"""{FOOT_START}
<footer class="library-reader-footer">
  <div class="library-reader-links">{extra}</div>
  <div class="library-reader-contact"><strong>Stay Connected</strong> <a href="mailto:srini.presents@gmail.com">srini.presents@gmail.com</a></div>
</footer>
{FOOT_END}
"""


def render_search(registry, source):
    results = []
    for entry in sorted(registry, key=lambda item: item["title"].casefold()):
        groups = "|".join(entry["collections"])
        results.append(f'<li data-collections="{html.escape(groups)}">{link(entry["path"], entry["title"])}</li>')
    return RESULTS.sub(lambda m: m[1] + "\n" + "\n".join(results) + "\n" + m[2], source, count=1)


def render_painting(route, page, artwork):
    name = PAINTINGS.get(route)
    hero = re.search(r'<header class="hero">.*?</header>', page, re.S)
    source = f"{ART}{name}.webp" if name else artwork.get(route, "")
    if hero:
        if not source.startswith(ART):
            return page
        old_art = re.search(r'<img\b[^>]*>', hero[0])
        position = hero.start() + old_art.start() if old_art else hero.end() - len("</header>")
        end = hero.start() + old_art.end() if old_art else position
        width, height = (1200, 800) if name == "kartika-banner" else (448, 448 if name else 252)
        priority = ' fetchpriority="high"'
    else:
        if not name:
            return page
        cover = re.search(r'<div class="cover-body">', page)
        if not cover:
            return page
        position = cover.end()
        end = position
        width, height = 448, 448
        priority = ""
    painting = f'<img class="library-cover-painting" src="{source}" width="{width}" height="{height}" alt=""{priority}>'
    picture = "<!-- library:art -->" + painting + "<!-- /library:art -->"
    return page[:position] + picture + page[end:]


def render_counts(home, counts):
    for group, count in counts.items():
        label = f"{count} article" + ("s" if count != 1 else "")
        marker = re.compile(r'(data-library-count="' + re.escape(html.escape(group)) + r'">)\d+ articles?')
        home, matches = marker.subn(lambda m: m[1] + label, home)
        if matches != 1:
            raise ValueError(f"Missing unique count marker for {group}")
    return home


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    home = HOME.read_text(encoding="utf-8")
    pages = load_pages()
    registry, series, memberships = build_registry(home, pages)
    articles = {entry["path"] for entry in registry if entry["kind"] == "article"}
    painted = {path: ART + name + ".webp" for path, name in (PAINTINGS | CARD_PAINTINGS).items()}
    artwork, generated = artwork_by_route(pages, painted)
    counts = {
        group: sum(group in record["collections"] and record["kind"] == "article" for record in registry)
        for group in GROUPS
    }
    changes = []

    def update(file, text, old=None):
        if old is None:
            old = file.read_text(encoding="utf-8") if file.exists() else ""
        if text != old:
            changes.append(file.relative_to(ROOT))
            if not args.check:
                file.write_text(text, encoding="utf-8", newline="\n")

    update(REGISTRY, json.dumps(registry, ensure_ascii=False, separators=(",", ":")) + "\n")
    update(HOME, illustrate_cards(render_counts(home, counts), artwork, HOME_TILE), home)
    search = SEARCH.read_text(encoding="utf-8")
    update(SEARCH, render_search(registry, search), search)
    for route, page in pages.items():
        base = page["base"]
        position = base.find("<!-- /sitenav:auto -->")
        if position >= 0:
            position += len("<!-- /sitenav:auto -->")
            if base[position:position + 1] == "\n":
                position += 1
        else:
            position = BODY.search(base).end()
        end = BODY_END.search(base).start()
        rendered = base[:position] + header(route, page, pages, memberships, counts, articles) + base[position:end]
        rendered += footer(route, pages, series, memberships, artwork) + base[end:]
        update(page["file"], illustrate_cards(render_painting(route, rendered, artwork), artwork), page["source"])

    active = {path.removeprefix(PUBLIC_PREFIX) for path in artwork.values() if path.startswith(PUBLIC_PREFIX)}
    if active and not args.check:
        DESTINATION.mkdir(parents=True, exist_ok=True)
    for key in sorted(active):
        update(DESTINATION / key, generated[key])

    print(f"Bhakti registry: {len(registry)} public pages, {len(series)} multi-page series or subcollections, {len(artwork)} nearby artwork sources.")
    if args.check and changes:
        raise SystemExit(f"{len(changes)} library files are out of sync.")


if __name__ == "__main__":
    main()
