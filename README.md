# wp-move

Move a WordPress site you own to a static site, and get a report that shows what moved, what is missing, and what broke.

Status: early work. `pull` and redirects work against the local demo site (see [`demo/`](demo/)); the verification report is next.

```bash
uv sync
WPMOVE_USER=... WPMOVE_APP_PASSWORD=... uv run wp-move pull https://example.com --out out --url-style keep
```

`--url-style keep` (default) reuses the old permalinks, so only `?p=` / `?page_id=` and `/wp-content/uploads/` need redirects; `slug` moves posts to `/posts/<slug>/`. Redirects are written to `out/redirects/` as `_redirects`, `nginx-maps.conf` + `nginx-server.conf`, and `url-map.csv`. The nginx files are checked against a real nginx with `demo/check_redirects.py`; the `_redirects` file has not been tested on Netlify or Cloudflare Pages yet.

Planned MVP:
- Pull posts, pages, drafts, media, categories, and tags through the WP REST API.
- Convert to Markdown with front matter. Keep unconverted blocks and shortcodes as HTML and list them.
- Download images and rewrite their paths.
- Map old URLs to new ones and emit redirect files (`_redirects`, nginx).
- Write a verification report (`report.html` / `report.json`) with counts per type, text similarity per page, broken links and images, and redirect coverage.

Principles: the source site is read only, nothing is sent to third parties, dependencies are pinned, and credentials come only from environment variables.
