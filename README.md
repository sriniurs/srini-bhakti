# Bhakti · Srini Presents

Standalone archive at https://bhakti.srinipresents.com/. Serve the repository root as static files.

After updating articles and `catalog.json`, run `python .github/bhakti_hubs.py --strict` to refresh the homepage index and article trails. Run `python scripts/library_registry.py` to refresh collection counts, search, breadcrumbs and chapter navigation. Run `python scripts/seo_sync.py` to refresh the sitemap. The SEO workflow runs the latter two steps on publication. Use their `--check` options to verify the generated files.
