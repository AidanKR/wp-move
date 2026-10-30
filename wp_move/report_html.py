"""Render report.json as one self-contained HTML page (no external assets, all text escaped)."""
from __future__ import annotations

from html import escape

CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#78716c;--card:#fff;--line:#e7e5e4;--ok:#15803d;--warn:#b45309;--bad:#b91c1c}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--card:#292524;--line:#44403c;--ok:#4ade80;--warn:#fbbf24;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 64px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 8px}
.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-top:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.card b{display:block;font-size:24px;font-variant-numeric:tabular-nums}.card span{color:var(--muted);font-size:13px}
.ok b{color:var(--ok)}.warn b{color:var(--warn)}.bad b{color:var(--bad)}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);border-radius:10px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);font-size:13px;vertical-align:top}
th{color:var(--muted);font-weight:600}td.n{text-align:right;font-variant-numeric:tabular-nums}code{font-size:12px;word-break:break-all}
details{margin-top:8px}summary{cursor:pointer;color:var(--muted)}
"""


def _card(label: str, value: str, level: str) -> str:
    return f'<div class="card {level}"><b>{escape(value)}</b><span>{escape(label)}</span></div>'


def _table(headers: list[str], rows: list[list], numeric: set[int] = frozenset(), limit: int = 200) -> str:
    if not rows:
        return '<p class="muted">None.</p>'
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = []
    for r in rows[:limit]:
        cells = "".join(f'<td class="n">{escape(str(c))}</td>' if i in numeric else f"<td>{escape(str(c))}</td>"
                        for i, c in enumerate(r))
        body.append(f"<tr>{cells}</tr>")
    more = f'<p class="muted">Showing {limit} of {len(rows)}. Full list in report.json.</p>' if len(rows) > limit else ""
    return f'<div class="scroll"><table><tr>{head}</tr>{"".join(body)}</table></div>{more}'


def render(r: dict) -> str:
    s = r["summary"]
    lvl = lambda bad: "bad" if bad else "ok"
    items_ok = s["items_written"] == s["items_source"]
    media_ok = s["media_written"] == s["media_source"]
    cards = [
        _card("posts & pages moved", f'{s["items_written"]} / {s["items_source"]}', lvl(not items_ok)),
        _card("media originals saved", f'{s["media_written"]} / {s["media_source"]}', lvl(not media_ok)),
        _card(f'pages under {int(s["text_threshold"] * 100)}% text kept', str(s["text_below_threshold"]),
              "warn" if s["text_below_threshold"] else "ok"),
        _card("missing image/media files", str(s["missing_media_refs"]), lvl(s["missing_media_refs"])),
        _card("broken internal links", str(s["broken_internal_links"]), lvl(s["broken_internal_links"])),
        _card("links still to old site", str(s["links_to_old_site"]), "warn" if s["links_to_old_site"] else "ok"),
        _card("links that hop through a redirect", str(s.get("links_via_redirect", 0)),
              "warn" if s.get("links_via_redirect") else "ok"),
        _card("canonicals pointing at old URLs", str(s.get("canonicals_to_old_url", 0)),
              "warn" if s.get("canonicals_to_old_url") else "ok"),
        _card("kept as HTML / dropped", f'{s["kept_html"]} / {s["dropped"]}', "warn" if s["dropped"] else "ok"),
        _card("archive URLs without target", str(s["unmapped_archives"]), "warn" if s["unmapped_archives"] else "ok"),
    ]
    parts = [
        f"<h1>wp-move report — {escape(r['site'].get('name') or '')}</h1>",
        f'<p class="muted">{escape(r["site"].get("home") or "")} · pulled {escape(r["pulled_at"])} · '
        f'{"authenticated (drafts included)" if r["authed"] else "public content only"} · '
        f'URL style {escape(str(r.get("url_style")))} · generated {escape(r["generated_at"])}</p>',
        f'<div class="grid">{"".join(cards)}</div>',
        "<h2>Counts</h2>",
        _table(["type", "status", "source", "written"],
               [[c["type"], c["status"], c["source"], c["written"]] for c in r["counts"]], {2, 3}),
        "<h2>Missing image/media files</h2>",
        _table(["page", "url"], [[m["out_path"], m["url"]] for m in r["missing_media"]]),
        "<h2>Broken internal links</h2>",
        _table(["page", "link"], [[b["out_path"], b["url"]] for b in r["broken_links"]]),
        f'<h2>Text kept per page (lowest first, threshold {int(s["text_threshold"] * 100)}%)</h2>',
        _table(["page", "status", "text kept"],
               [[p["out_path"], p["status"], f'{p["coverage"] * 100:.1f}%'] for p in r["pages"]], {2}, limit=30),
        "<h2>Links that still point at the old site</h2>",
        _table(["kind", "count"], [[k, n] for k, n in sorted(r["old_links_by_class"].items(), key=lambda x: -x[1])], {1}),
        "<details><summary>All links</summary>",
        _table(["page", "class", "url"], [[l["out_path"], l["class"], l["url"]] for l in r["old_links"]]),
        "</details>",
        "<h2>Content kept as HTML, dropped, or unrendered shortcodes</h2>",
        _table(["kind", "element", "count"], [[l["kind"], l["what"], l["count"]] for l in r["leftovers"]], {2}),
        "<h2>Images hosted elsewhere (not downloaded)</h2>",
        _table(["host", "references"], [[h, n] for h, n in r["external_image_hosts"].items()], {1}),
        "<h2>Redirects</h2>",
        f'<p>{s["published"]} published items: {s["published_unchanged_url"]} keep their old URL, '
        f'{s["published"] - s["published_unchanged_url"]} are redirected. '
        f'{s["unmapped_archives"]} category/tag archive URLs have no page in the output yet.</p>',
    ]
    if "redirect_check" in r:
        rc = r["redirect_check"]
        parts += [f'<p class="muted">Live check against {escape(rc["server"])}</p>',
                  _table(["kind", "ok", "total"], [[k, v["ok"], v["total"]] for k, v in rc["by_kind"].items()], {1, 2}),
                  _table(["kind", "old", "expected", "status", "location"],
                         [[f["kind"], f["old"], f["expected"], f["status"], f["location"]] for f in rc["failures"]])]
    parts += ["<details><summary>Archive URLs without a target</summary>",
              _table(["type", "name", "old url"], [[u["type"], u["name"], u["old_url"]] for u in r["unmapped"]]),
              "</details>"]
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>wp-move report</title>'
            f'<style>{CSS}</style></head><body><main>{"".join(parts)}</main></body></html>\n')
