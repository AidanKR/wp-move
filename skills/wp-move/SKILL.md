---
name: wp-move
description: Move a WordPress site the user owns to Markdown with wp-move, then read the verification report and tell the user what moved, what is missing, and what broke. Use when the user asks to migrate, export, or leave a WordPress site, or to check a previous wp-move output folder.
allowed-tools: Read, Bash(uvx --from git+https://github.com/AidanKR/wp-move@v0.0.1 wp-move:*)
---

# wp-move

wp-move reads a WordPress site through its REST API, writes Markdown plus media and redirect files, and checks the result against the source. This skill runs it and explains the report.

## Before running

- Only move a site the user owns or is allowed to copy. If that is unclear, ask first.
- wp-move only reads from the site. It never writes to it and sends nothing anywhere else.
- Drafts, scheduled and private posts need an Application Password. Ask the user to set it in their own shell:
  `export WPMOVE_USER=...` and `export WPMOVE_APP_PASSWORD=...`
  Never ask for the password in chat, never put it on the command line, and never print it.
- Without credentials wp-move still works and moves public content only. Say so in the summary.

## Run

```bash
uvx --from git+https://github.com/AidanKR/wp-move@v0.0.1 wp-move pull https://SITE --out OUT_DIR
```

Add `--url-style slug` only if the user wants posts under `/posts/<slug>/`. The default `keep` reuses the old permalinks.

To re-check an existing output folder:

```bash
uvx --from git+https://github.com/AidanKR/wp-move@v0.0.1 wp-move report --out OUT_DIR
```

## Read the result

Open `OUT_DIR/report.json` and report from its numbers, not from memory:

1. `summary.items_written` / `summary.items_source` and `summary.media_written` / `summary.media_source`.
2. Hard failures: `missing_media`, `broken_links`, and any counts row where `written` < `source`. The command exits with code 2 when any of these exist.
3. Pages in `pages` with `coverage` below `summary.text_threshold`, lowest first.
4. Warnings: `old_links_by_class`, `leftovers` (content kept as HTML, dropped, or shortcodes), `external_image_hosts`, `unmapped`.
5. Where the redirect files are: `OUT_DIR/redirects/`.

Point the user to `OUT_DIR/report.html` for the full view. Do not claim the migration is complete if the exit code was 2.
