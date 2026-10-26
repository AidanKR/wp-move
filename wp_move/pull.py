"""Pull a WordPress site into Markdown + media, and record everything in .wp-move/manifest.json."""
from __future__ import annotations

import json
import os
import urllib.parse
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from .convert import blocks_used, front_matter, html_to_markdown
from .fetch import Client, fetch_site
from .media import MediaMap, download
from .urls import LinkMap, build_redirects, new_path, split_link, write_files


def _text(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text().strip()


def _field(item: dict, key: str) -> str:
    v = item.get(key) or {}
    return v.get("raw") if isinstance(v, dict) and v.get("raw") is not None else (v.get("rendered", "") if isinstance(v, dict) else v)


def _page_path(item: dict, home: str) -> str | None:
    """'parent/child' from a pretty page link, else None."""
    link = item.get("link") or ""
    if "?" in link or not link.startswith(home):
        return None
    path = urllib.parse.unquote(link[len(home):]).strip("/")
    return path or None


def pull(site: str, out: str, user: str | None = None, app_password: str | None = None,
         with_media: bool = True, url_style: str = "keep") -> dict:
    client = Client(site, user, app_password)
    snap = fetch_site(client)
    home = (snap["site"].get("home") or site).rstrip("/")
    meta_dir = os.path.join(out, ".wp-move")
    os.makedirs(meta_dir, exist_ok=True)

    users = {u["id"]: u.get("name") or u.get("slug") for u in snap["users"]}
    cats = {c["id"]: _text(c.get("name", "")) for c in snap["categories"]}
    tags = {t["id"]: _text(t.get("name", "")) for t in snap["tags"]}
    media_by_id = {m["id"]: m for m in snap["media"]}
    mm = MediaMap(site)
    for m in snap["media"]:
        mm.add_item(m)

    # Pass 1: decide every item's file and new URL, so pass 2 can rewrite internal links.
    plan, used_paths, used_urls = [], set(), set()
    links = LinkMap(home)
    for kind in ("posts", "pages"):
        for it in snap[kind]:
            slug = it.get("slug") or it.get("generated_slug") or f"untitled-{it['id']}"
            page_rel = _page_path(it, home) if kind == "pages" else None
            rel = page_rel or slug
            path = f"content/{kind}/{rel}.md"
            if path in used_paths:
                path = f"content/{kind}/{rel}-{it['id']}.md"
            used_paths.add(path)
            url = new_path(kind, it, home, url_style, slug, page_rel)
            if url in used_urls:
                url = url.rstrip("/") + f"-{it['id']}/"
            used_urls.add(url)
            if it.get("status") == "publish":
                links.add(it, kind, url)
            plan.append((kind, it, slug, path, url))

    def rewrite(u: str | None) -> str | None:
        return mm.rewrite(u) or links.rewrite(u)

    items, entries = [], []
    for kind, it, slug, path, url in plan:
        content = it.get("content") or {}
        conv = html_to_markdown(content.get("rendered", ""), rewrite_url=rewrite)
        leftovers = list(conv.leftovers)
        if content.get("protected"):
            leftovers.append({"kind": "protected", "count": 1})

        feat = media_by_id.get(it.get("featured_media") or 0)
        fm = {
            "title": _text(_field(it, "title")),
            "date": it.get("date_gmt") and it["date_gmt"] + "Z",
            "modified": it.get("modified_gmt") and it["modified_gmt"] + "Z",
            "slug": slug,
            "url": url,
            "status": it.get("status"),
            "author": users.get(it.get("author")) or (str(it["author"]) if it.get("author") else None),
            "categories": [cats.get(c, str(c)) for c in it.get("categories") or []],
            "tags": [tags.get(t, str(t)) for t in it.get("tags") or []],
            "featured_image": feat and mm.rewrite(feat.get("source_url", "")),
            "excerpt": _text(_field(it, "excerpt")) if kind == "posts" else None,
            "old_url": it.get("link"),
            "wp_id": it["id"],
        }
        dest = os.path.join(out, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(front_matter(fm) + conv.markdown)

        items.append({
            "wp_id": it["id"], "type": kind[:-1], "status": it.get("status"), "title": fm["title"],
            "old_url": it.get("link"), "out_path": path, "blocks": blocks_used(content.get("raw")),
            "leftovers": leftovers, "images": conv.images, "new_path": url,
        })
        old = split_link(it.get("link"), home)
        entries.append({"wp_id": it["id"], "type": kind[:-1], "status": it.get("status"),
                        "old_url": it.get("link"), "old_path": old and old[0], "old_query": old and old[1],
                        "new_path": url, "out_path": path})

    media_results = []
    if with_media:
        wanted = sorted(set(mm.urls.items()))
        referenced = {u for i in items for u in i["images"]}
        for url, lp in wanted:
            if url not in mm.originals and url not in referenced and \
                    urllib.parse.urljoin(home + "/", url) not in referenced:
                continue  # unused size variant
            ok, detail = download(url, os.path.join(out, "public", lp))
            media_results.append({"url": url, "local": "public/" + lp, "ok": ok, "detail": detail,
                                  "original": url in mm.originals})

    # Taxonomy archives have no page in the output yet: listed so the report can flag them.
    unmapped = [{"type": t[:-1], "id": x["id"], "name": _text(x.get("name", "")), "old_url": x.get("link")}
                for t in ("categories", "tags") for x in snap[t] if x.get("count")]
    rules = build_redirects(entries)
    redirect_counts = write_files(out, entries, rules, unmapped)

    manifest = {
        "tool": "wp-move 0.0.1",
        "pulled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "site": snap["site"], "authed": snap["authed"], "requests": snap["requests"],
        "source_counts": {k: len(snap[k]) for k in ("posts", "pages", "media", "categories", "tags", "users")},
        "url_style": url_style, "redirects": redirect_counts,
        "items": items, "media": media_results,
    }
    with open(os.path.join(meta_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    # Raw snapshot for the later verification step; user records reduced to id/name/slug.
    snap_out = {**snap, "users": [{k: u.get(k) for k in ("id", "name", "slug")} for u in snap["users"]]}
    with open(os.path.join(meta_dir, "source.json"), "w", encoding="utf-8") as f:
        json.dump(snap_out, f, ensure_ascii=False)
    return manifest
