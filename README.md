# wp-move

Move a WordPress site you own to a static site, and get a report that shows what moved, what is missing, and what broke.

Status: early work. Only the local demo source site exists so far (see [`demo/`](demo/)).

Planned MVP:
- Pull posts, pages, drafts, media, categories, and tags through the WP REST API.
- Convert to Markdown with front matter. Keep unconverted blocks and shortcodes as HTML and list them.
- Download images and rewrite their paths.
- Map old URLs to new ones and emit redirect files (`_redirects`, nginx).
- Write a verification report (`report.html` / `report.json`) with counts per type, text similarity per page, broken links and images, and redirect coverage.

Principles: the source site is read only, nothing is sent to third parties, dependencies are pinned, and credentials come only from environment variables.
