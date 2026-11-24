#!/usr/bin/env python3
"""Keep Bhakti articles free of social promotions; invite private reader feedback."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EMAIL = "srini.presents@gmail.com"
START = "<!-- reader-feedback:start -->"
END = "<!-- reader-feedback:end -->"
NOTE = """<!-- reader-feedback:start -->
<div class="bhakti-reader-feedback" style="box-sizing:border-box;max-width:820px;margin:26px auto 32px;padding:22px 24px;border:1px solid #dec8aa;border-radius:12px;background:#fff8ed;color:#321f2a;font:16px/1.65 system-ui,-apple-system,'Segoe UI',sans-serif">
  <strong style="display:block;font:700 25px/1.25 Georgia,serif;margin-bottom:8px">Share your thoughts</strong>
  <p style="margin:0 0 13px">If an article touched your heart, or you have a suggestion, reflection or correction, I would love to hear from you.</p>
  <a href="mailto:srini.presents@gmail.com?subject=Bhakti%20reader%20feedback" style="display:inline-block;max-width:100%;overflow-wrap:anywhere;padding:10px 14px;border-radius:6px;background:#973f2c;color:white;text-decoration:none;font-weight:700">Write to me · srini.presents@gmail.com</a>
  <p style="margin:14px 0 0;font-size:14px">New to the dots and lines in our Sanskrit (ā, ṛ, ṣ, ṃ)? See <a href="/how-to-read-iast/" style="color:#973f2c;font-weight:700">How to read IAST</a>.</p>
</div>
<!-- reader-feedback:end -->"""
social = re.compile(r'<div\s+class=["\']follow["\'][^>]*>.*?</div>', re.I | re.S)
existing = re.compile(re.escape(START) + r'.*?' + re.escape(END) + r'\n?', re.S)
changed = count = 0
for p in ROOT.rglob("index.html"):
    if any(part.startswith(".") for part in p.relative_to(ROOT).parts):
        continue
    s = p.read_text(encoding="utf-8")
    has_promo_nav = '<a href="https://srinipresents.com/">Srini Presents</a>' in s
    has_social = bool(social.search(s))
    has_article = '<section class="page"' in s or "class='page'" in s
    has_trail = "<!-- bhaktitrail:auto -->" in s
    if not has_social and not has_promo_nav and not (has_article and has_trail):
        continue
    count += 1
    new = social.sub("", s)
    new = re.sub(r'\s*<a href="https://srinipresents\.com/">Srini Presents</a>', "", new)
    new = existing.sub("", new)
    if has_trail and (has_social or has_article):
        new = new.replace("<!-- bhaktitrail:auto -->", NOTE + "\n<!-- bhaktitrail:auto -->", 1)
    elif has_social:
        new = new.replace("</body>", NOTE + "\n</body>", 1)
    if new != s:
        p.write_text(new, encoding="utf-8")
        changed += 1
print(f"Bhakti feedback: inspected {count} articles, updated {changed}")
