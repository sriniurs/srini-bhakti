#!/usr/bin/env python3
"""Build the Bhakti hubs from catalog.json and add a trail to every Bhakti article.

The section has four doors (Gods, Hymns, Scriptures, Temples) and three deity
views (Śiva, Viṣṇu, Devi). Every article or series under / needs one entry
in catalog.json; this script then places its card on the right hubs.

  python3 .github/bhakti_hubs.py           rebuild hubs and trails
  python3 .github/bhakti_hubs.py --strict  also fail if any Bhakti page is uncatalogued
"""
import json
import re
import sys
from html import escape, unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAT = ROOT / 'catalog.json'

DOORS = {
    'gods': ('Gods and Goddesses', 'Who they are'),
    'hymns': ('Hymns and Mantras', 'What to chant'),
    'scriptures': ('Scriptures and Stories', 'What to read'),
    'temples': ('Temples and Tīrthas', 'Where to go'),
}
DOOR_URL = {'gods': '/gods/', 'hymns': '/hymns/',
            'scriptures': '/scriptures/', 'temples': '/temples-of-india/'}
DEITIES = {'shiva': ('Śiva', 'he'), 'vishnu': ('Viṣṇu', 'he'), 'devi': ('Devi', 'she')}


def plural(n, word):
    return f'{n} {word}' + ('' if n == 1 else 's')


GROUPS = {'circuits': 'Pan-India circuits', 'regional': 'Regional guides'}
HUBS = {'/', '/srividya/', '/festivals/', '/gods/', '/hymns/', '/scriptures/',
        '/temples-of-india/', '/shiva/', '/vishnu/', '/devi/'}

HUB_S, HUB_E = '<!-- hub:auto -->', '<!-- /hub:auto -->'
TR_S, TR_E = '<!-- bhaktitrail:auto -->', '<!-- /bhaktitrail:auto -->'
SHELF_CSS = ('<style>.shelf{max-width:1180px;margin:34px auto 6px;padding:0 18px;'
             'font:800 clamp(20px,3vw,28px)/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;color:#151515}'
             '.shelf small{display:block;font:500 15px/1.4 system-ui,sans-serif;color:#555;margin-top:4px}</style>')
TRAIL_CSS = ('<style>.bk-trail{max-width:820px;margin:28px auto 18px;padding:12px 16px;border:2px solid #09283f;'
             'border-radius:14px;background:#fffdf4;box-shadow:3px 3px 0 #09283f;'
             'font:600 15px/1.7 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#09283f}'
             '.bk-trail a{color:#09283f;text-decoration:underline;text-underline-offset:3px}'
             '.bk-trail .sep{opacity:.55;margin:0 6px}.bk-trail .also{display:block;font-weight:500}'
             '@media print{.bk-trail{display:none}}</style>')


def load():
    data = json.loads(CAT.read_text(encoding='utf-8'))
    entries = data['entries']
    seen = set()
    for e in entries:
        p = e['path']
        if not (p.startswith('/') and p.endswith('/')):
            sys.exit(f'catalog: bad path {p}')
        if p in seen:
            sys.exit(f'catalog: duplicate {p}')
        seen.add(p)
        if e['door'] not in DOORS:
            sys.exit(f'catalog: unknown door {e["door"]} for {p}')
        for d in e['deities']:
            if d not in DEITIES:
                sys.exit(f'catalog: unknown deity {d} for {p}')
        if not (ROOT / p.strip('/') / 'index.html').exists():
            sys.exit(f'catalog: no page at {p}')
    return entries


def is_redirect(f):
    return bool(re.search(r'(?i)<meta[^>]+http-equiv=["\']?refresh', f.read_text(encoding='utf-8', errors='ignore')[:3000]))


def shelf(title, sub, tiles, anchor=''):
    if not tiles:
        return ''
    a = f' id="{anchor}"' if anchor else ''
    s = f'<small>{sub}</small>' if sub else ''
    return f'<h2 class="shelf"{a}>{title}{s}</h2>\n  <ol class="tiles">\n    ' + ''.join(tiles) + '\n  </ol>\n'


def write_hub(url, body):
    f = ROOT / url.strip('/') / 'index.html'
    page = f.read_text(encoding='utf-8')
    block = HUB_S + SHELF_CSS + '\n' + body + HUB_E
    if HUB_S in page:
        new = re.sub(re.escape(HUB_S) + r'.*?' + re.escape(HUB_E), lambda m: block, page, flags=re.S)
    else:
        new = re.sub(r'<ol class="tiles">.*?</ol>', lambda m: block, page, count=1, flags=re.S)
        if new == page:
            sys.exit(f'hub {url}: no tiles list to replace')
    if new != page:
        f.write_text(new, encoding='utf-8')


def page_url(file):
    relative = file.parent.relative_to(ROOT)
    return "/" if relative == Path(".") else f"/{relative.as_posix()}/"


def catalogue_pages(entries, strict):
    pages = {e['path']: [] for e in entries}
    prefixes = sorted(pages, key=len, reverse=True)
    missing = []
    for file in ROOT.rglob('index.html'):
        url = page_url(file)
        if url in HUBS or is_redirect(file):
            continue
        prefix = next((p for p in prefixes if url.startswith(p)), None)
        if prefix is None:
            missing.append(url)
            continue
        match = re.search(r'<title>(.*?)</title>', file.read_text(encoding='utf-8'), re.I | re.S)
        title = ' '.join(unescape(match[1]).split()) if match else ''
        title = re.sub(r'\s*[·|—]\s*srini\.presents$', '', title, flags=re.I).strip()
        if not title:
            sys.exit(f'Bhakti article has no title: {url}')
        pages[prefix].append((url, title))
    if missing and strict:
        sys.exit('Uncatalogued Bhakti pages:\n  ' + '\n  '.join(sorted(missing)))
    for articles in pages.values():
        articles.sort(key=lambda article: [
            int(part) if part.isdigit() else part
            for part in re.split(r'(\d+)', article[0])
        ])
    return pages


def article_index(entries, pages):
    sections = []
    for door, (title, _) in DOORS.items():
        articles = [article for e in entries if e['door'] == door for article in pages[e['path']]]
        if not articles:
            continue
        links = '\n'.join(f'      <li><a href="{escape(url)}">{escape(name)}</a></li>'
                          for url, name in articles)
        sections.append(f'  <details><summary>{title} · {plural(len(articles), "article")}</summary>\n'
                        f'    <ul>\n{links}\n    </ul>\n  </details>')
    return ('<section class="article-index" aria-labelledby="all-articles">\n'
            '  <h2 class="shelf" id="all-articles">All Bhakti articles</h2>\n'
            + '\n'.join(sections) + '\n</section>\n')


def build(entries, pages):
    by = lambda door, deity=None, group=None: [e for e in entries if e['door'] == door
                                                and (deity is None or deity in e['deities'])
                                                and (group is None or e.get('group') == group)]
    tiles = lambda es: [e['tile'] for e in es]
    write_hub('/', article_index(entries, pages))

    # door pages
    for k in ('gods', 'hymns', 'scriptures'):
        body = ''
        for d, (name, _) in DEITIES.items():
            es = [e for e in by(k) if e['deities'][0] == d]
            body += shelf(name, '', tiles(es), d)
        write_hub(DOOR_URL[k], body)
    write_hub('/temples-of-india/', ''.join(shelf(g, '', tiles(by('temples', group=gk)), gk) for gk, g in GROUPS.items()))

    # deity pages
    for d, (name, pron) in DEITIES.items():
        body = (shelf(f'Who {pron} is', 'Forms, stories and symbols.', tiles(by('gods', d)), 'who')
                + shelf('Hymns and mantras', 'What to chant, verse by verse.', tiles(by('hymns', d)), 'hymns')
                + shelf('Scriptures and stories', 'Texts read in parts.', tiles(by('scriptures', d)), 'scriptures')
                + shelf('Temples', 'Where to go.', tiles(by('temples', d)), 'temples'))
        write_hub(f'/{d}/', body)


def trail_for(entry, entries):
    door = entry['door']
    t = [f'<a href="/">Bhakti</a>', f'<a href="{DOOR_URL[door]}">{DOORS[door][0]}</a>']
    also = ''
    if len(entry['deities']) == 1:
        d = entry['deities'][0]
        name, pron = DEITIES[d]
        t.append(f'<a href="/{d}/">{name}</a>')
        links = []
        for k, label in (('gods', f'who {pron} is'), ('hymns', 'hymns'), ('scriptures', 'scriptures'), ('temples', 'temples')):
            if k != door and any(e['door'] == k and d in e['deities'] for e in entries):
                anchor = {'gods': 'who'}.get(k, k)
                links.append(f'<a href="/{d}/#{anchor}">{label}</a>')
        if links:
            also = f'<span class="also">More for {name}: ' + ' · '.join(links) + '</span>'
    return (TR_S + TRAIL_CSS + '<nav class="bk-trail" aria-label="Bhakti section">'
            + '<span class="sep">›</span>'.join(t) + also + '</nav>' + TR_E + '\n')


def trails(entries, strict):
    order = sorted(entries, key=lambda e: -len(e['path']))
    missing = []
    for f in sorted(ROOT.rglob('index.html')):
        url = page_url(f)
        if url in HUBS:
            continue
        page = f.read_text(encoding='utf-8')
        if is_redirect(f):
            continue
        entry = next((e for e in order if url.startswith(e['path'])), None)
        clean = re.sub(re.escape(TR_S) + r'.*?' + re.escape(TR_E) + r'\n?', '', page, flags=re.S)
        if entry is None:
            missing.append(url)
            new = clean
        else:
            block = trail_for(entry, entries)
            m = re.search(r'<script[^>]*data-goatcounter', clean) or re.search(r'</body>', clean, re.I)
            if not m:
                continue
            new = clean[:m.start()] + block + clean[m.start():]
        if new != page:
            f.write_text(new, encoding='utf-8')
    if missing:
        print('Uncatalogued Bhakti pages (add them to catalog.json):')
        for u in missing:
            print('  ' + u)
        if strict:
            sys.exit(1)


if __name__ == '__main__':
    entries = load()
    strict = '--strict' in sys.argv
    build(entries, catalogue_pages(entries, strict))
    trails(entries, strict)
    print(f'bhakti hubs: {len(entries)} catalog entries')
