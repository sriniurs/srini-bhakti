#!/usr/bin/env python3
"""Count the published articles linked by Bhakti's collections and series."""

import re
from functools import lru_cache
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CARD_CLASSES = {'tiles', 'bhakti-topics'}
LIST_TAGS = {'ol', 'ul'}
REDIRECT = re.compile(r'<meta[^>]+http-equiv\s*=\s*["\x27]?refresh', re.I)
SITE = 'bhakti.srinipresents.com'
SIZE = re.compile(r'<small class="collection-size(?: collection-size--card)?">.*?</small>', re.S)
LABEL = re.compile(r'<strong class="label">([^<]*)</strong>')
COUNT_WORDS = re.compile(r'\b\d+\s+(?:articles|parts|guides|chapters|forms|avatāras|days)\b', re.I)
PART = re.compile(r'<h[23][^>]*>\s*PART\s+(\d+)\b',re.I)
UTILITY_NAV = {'sr-reader-bar', 'bhakti-nav', 'bk-trail', 'bhakti-section-links', 'mysuru-jumps', 'tulu-nav'}
TULU_FESTIVALS = '/tulunadu/festivals/'


class Cards(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.lists = []
        self.routes = []
        self.fragment_links = set()
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in LIST_TAGS:
            self.lists.append(bool(CARD_CLASSES.intersection(attrs.get('class', '').split())))
        if tag == 'a' and any(self.lists):
            url = urlsplit(attrs.get('href', ''))
            if url.netloc in ('', SITE) and url.path.startswith('/'):
                if url.fragment:
                    self.fragment_links.add((url.path, url.fragment))
                else:
                    self.routes.append(url.path)

    def handle_endtag(self, tag):
        if tag in LIST_TAGS and self.lists:
            self.lists.pop()


def build_counts():
    pages, cards, inline_parts = set(), {}, {}
    festival_links = 0
    for source in ROOT.rglob('index.html'):
        parts = source.parent.relative_to(ROOT).parts
        if parts and any(part.startswith('.') for part in parts):
            continue
        markup = source.read_text(encoding='utf-8')
        if REDIRECT.search(markup[:3000]):
            continue
        route = '/' + '/'.join(parts) + '/' if parts else '/'
        pages.add(route)
        card_links = Cards(markup)
        cards[route] = card_links.routes
        if route == TULU_FESTIVALS:
            festival_links = len(card_links.fragment_links)
        parts = set(PART.findall(markup))
        if len(parts) > 1:
            inline_parts[route] = f'{len(parts)} parts in 1 article'

    @lru_cache(maxsize=None)
    def articles(route, seen=frozenset()):
        if route in seen or route == TULU_FESTIVALS:
            return frozenset()
        destinations = [target for target in cards[route] if target in pages and target != route]
        if not destinations:
            return frozenset({route})
        return frozenset().union(*(articles(target, seen | {route}) for target in destinations))

    labels = {}
    for route, targets in cards.items():
        if route in {'/', '/search/'} or not targets:
            continue
        count = len(articles(route))
        if count:
            labels[route] = f'{count} article'+ ('s' if count != 1 else '')

    part_works = (
        '/shiva/sri-rudram/', '/shiva/shiva-mahimna-stotram/', '/vishnu/vishnu-sahasranama/',
        '/vishnu/venkatesa-suprabhatam/', '/vishnu/bhaja-govindam/', '/devi/devi-mahatmya/',
        '/subramanya/', '/srividya/lalitopakhyana/',
    )
    for route in part_works:
        count = len(articles(route))
        labels[route] = f'{count} parts'
    for route, unit in (
        ('/vishnu/bhagavad-gita/', 'chapters'), ('/vishnu/dashavatara/', 'avatāras'),
        ('/devi/ashta-lakshmi/', 'forms'), ('/srividya/dasha-mahavidya/', 'guides'),
    ):
        count = len(articles(route)) - 1
        labels[route] = f'{count} {unit} + overview'
    labels.update(inline_parts)
    route = '/srividya/related-reading/'
    labels[route] = f'{len(set(cards[route]))} reading links'
    if TULU_FESTIVALS in pages and not articles(TULU_FESTIVALS):
        labels[TULU_FESTIVALS] = f'{festival_links} reading links'
    return labels, pages


class ArticleLinks(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.markup = markup
        self.line_offsets = [0, *(m.end() for m in re.finditer(r'\n', markup))]
        self.lists = []
        self.navs = []
        self.anchor = None
        self.links = []
        self.feed(markup)

    def position(self):
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get('class', '').split())
        if tag in LIST_TAGS:
            self.lists.append(bool(classes & CARD_CLASSES))
        if tag == 'nav':
            self.navs.append(bool(classes & UTILITY_NAV))
        if tag == 'a':
            self.anchor = None
            href = urlsplit(attrs.get('href', ''))
            if (any(self.navs) or href.netloc not in ('', SITE) or href.fragment
                    or not href.path.startswith('/') or href.path in {'/', '/search/'}):
                return
            self.anchor = (self.position() + len(self.get_starttag_text()),
                           href.path, any(self.lists))

    def handle_endtag(self, tag):
        if tag in LIST_TAGS and self.lists:
            self.lists.pop()
        if tag == 'nav' and self.navs:
            self.navs.pop()
        if tag == 'a' and self.anchor:
            start, route, is_card = self.anchor
            self.links.append((start, self.position(), route, is_card))
            self.anchor = None


def annotate():
    labels, pages = build_counts()
    changed = 0
    for page in ROOT.rglob('index.html'):
        parts = page.parent.relative_to(ROOT).parts
        route = '/' + '/'.join(parts) + '/' if parts else '/'
        if route not in pages:
            continue
        with page.open(encoding='utf-8', newline='') as stream:
            original = stream.read()
        clean = SIZE.sub('', original)
        for start, end, target, is_card in reversed(ArticleLinks(clean).links):
            label = labels.get(target)
            if not label and is_card and target in pages:
                label = '1 article'
            if not label:
                continue
            inner = clean[start:end]
            if is_card:
                previous = LABEL.search(inner)
                if previous and target in labels and COUNT_WORDS.search(unescape(previous[1])):
                    inner = inner[:previous.start()] + inner[previous.end():]
                title = re.search(r'</h[23]>', inner, re.I)
                at = title.end() if title else len(inner)
                badge = f'<small class="collection-size collection-size--card">{escape(label)}</small>'
                inner = inner[:at] + badge + inner[at:]
            else:
                inner += f'<small class="collection-size"> · {escape(label)}</small>'
            clean = clean[:start] + inner + clean[end:]
        if clean != original:
            with page.open('w', encoding='utf-8', newline='') as stream:
                stream.write(clean)
            changed += 1
    return changed


if __name__ == '__main__':
    print(f'Updated article counts on {annotate()} pages')
