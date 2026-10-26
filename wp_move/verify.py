"""Compare the pulled output against the source snapshot and produce findings (report.json)."""
from __future__ import annotations

import collections
import csv
import http.client
import json
import os
import re
import urllib.parse
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from .urls import split_link

TEXT_THRESHOLD = 0.95  # share of source words that must survive in the Markdown
WORD_RE = re.compile(r"\w+", re.UNICODE)
# URLs and site paths are not prose; they change by design (rewritten links) and would skew coverage.
URL_RE = re.compile(r"https?://\S+|(?<![\w/])/[\w./%~-]+")
MD_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_ATTR_RE = re.compile(r"\b(href|src|poster)=\"([^\"]+)\"")


def _words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(URL_RE.sub(" ", text))]


def source_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup.find_all(("script", "style", "noscript")):
        t.decompose()
    return soup.get_text(" ")


def markdown_text(md: str) -> str:
    """Visible text of our Markdown: link/image targets and syntax removed, kept HTML reduced to text."""
    md = MD_LINK_RE.sub(lambda m: " " if m.group(1) else f" {m.group(2)} ", md)
    md = re.sub(r"^\s{0,3}(#{1,6}|>|-|\*|\d+\.)\s+", " ", md, flags=re.M)
    md = re.sub(r"[*_`~]", "", md)
    return BeautifulSoup(md, "html.parser").get_text(" ")


def coverage(src: str, out: str) -> float:
    """Fraction of source words (with multiplicity) present in the output."""
    a, b = collections.Counter(_words(src)), collections.Counter(_words(out))
    total = sum(a.values())
    if not total:
        return 1.0
    return sum(min(n, b[w]) for w, n in a.items()) / total


def _body(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return text.split("\n---\n", 1)[1] if text.startswith("---\n") else text


def _links(md: str) -> list[tuple[str, str]]:
    """(kind, url) for Markdown links/images and href/src attributes in kept HTML."""
    found = [("image" if m.group(1) else "link", m.group(3)) for m in MD_LINK_RE.finditer(md)]
    for m in HTML_ATTR_RE.finditer(md):
        found.append(("image" if m.group(1) in ("src", "poster") else "link", m.group(2)))
    return found


def classify_old_link(path: str) -> str:
    if path.startswith(("/wp-admin", "/wp-login")):
        return "admin"
    if path.startswith(("/wp-comments-post", "/comments/")) or "/feed" in path:
        return "comments-or-feed"
    if path.startswith(("/category/", "/tag/", "/author/")):
        return "taxonomy-archive"
    if re.fullmatch(r"/\d{4}/(\d{2}/(\d{2}/)?)?", path if path.endswith("/") else path + "/"):
        return "date-archive"
    if path in ("", "/"):
        return "home"
    return "other"


def check_server(out: str, server: str, rows: list[dict], limit: int | None = None) -> dict:
    """Request old URLs on a server running the generated redirects; expect 301 to the new path."""
    host = urllib.parse.urlsplit(server).netloc
    cases = []
    for r in rows:
        if r["status"] != "publish":
            continue
        if not r["old_query"] and r["old_path"] != r["new_path"]:
            cases.append(("permalink", r["old_path"], r["new_path"]))
        cases.append(("post-id", f"/?p={r['wp_id']}", r["new_path"]))
        if r["type"] == "page":
            cases.append(("page-id", f"/?page_id={r['wp_id']}", r["new_path"]))
    results = collections.defaultdict(lambda: [0, 0])
    failures = []
    for kind, old, new in cases[:limit]:
        conn = http.client.HTTPConnection(host, timeout=10)
        try:
            conn.request("GET", urllib.parse.quote(old, safe="/?=&%"))
            resp = conn.getresponse()
            loc = urllib.parse.unquote(urllib.parse.urlsplit(resp.getheader("Location") or "").path)
            ok = resp.status == 301 and loc == new
            status = resp.status
        except OSError as e:
            ok, status, loc = False, str(e), ""
        finally:
            conn.close()
        results[kind][0] += ok
        results[kind][1] += 1
        if not ok:
            failures.append({"kind": kind, "old": old, "expected": new, "status": status, "location": loc})
    return {"server": server, "by_kind": {k: {"ok": v[0], "total": v[1]} for k, v in results.items()},
            "failures": failures}


def verify(out: str, server: str | None = None) -> dict:
    meta = os.path.join(out, ".wp-move")
    with open(os.path.join(meta, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    with open(os.path.join(meta, "source.json"), encoding="utf-8") as f:
        source = json.load(f)
    home = (manifest["site"].get("home") or source["site"].get("url") or "").rstrip("/")
    with open(os.path.join(out, "redirects", "url-map.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # 1. Counts: every source item has a file on disk.
    by_id = {(i["type"], i["wp_id"]): i for i in manifest["items"]}
    counts = []
    for kind in ("posts", "pages"):
        t = kind[:-1]
        per_status = collections.Counter(x.get("status") for x in source[kind])
        for status, n in sorted(per_status.items()):
            written = sum(1 for x in source[kind] if x.get("status") == status
                          and (i := by_id.get((t, x["id"]))) and os.path.exists(os.path.join(out, i["out_path"])))
            counts.append({"type": t, "status": status, "source": n, "written": written})
    originals = [m for m in manifest["media"] if m.get("original")]
    media_files_ok = sum(1 for m in originals if os.path.exists(os.path.join(out, m["local"])))
    counts.append({"type": "media", "status": "original", "source": len(source["media"]), "written": media_files_ok})

    # 2-4. Per item: text coverage, links and images.
    new_paths = {r["new_path"].rstrip("/") or "/" for r in rows}
    site_host = urllib.parse.urlsplit(home).netloc
    pages, missing_media, broken_links, old_links, external_images = [], [], [], [], collections.Counter()
    src_by_id = {(k[:-1], x["id"]): x for k in ("posts", "pages") for x in source[k]}
    for item in manifest["items"]:
        path = os.path.join(out, item["out_path"])
        if not os.path.exists(path):
            pages.append({**_item_head(item), "coverage": 0.0, "missing_file": True})
            continue
        md = _body(path)
        src = src_by_id.get((item["type"], item["wp_id"]), {})
        content = src.get("content") or {}
        cov = 1.0 if content.get("protected") else coverage(source_text(content.get("rendered", "")), markdown_text(md))
        pages.append({**_item_head(item), "coverage": round(cov, 4)})
        for kind, url in _links(md):
            u = urllib.parse.urlsplit(url)
            if u.scheme in ("mailto", "tel", "data", "javascript") or url.startswith("#"):
                continue
            if not u.netloc and url.startswith("/"):
                p = urllib.parse.unquote(u.path)
                if p.startswith("/media/"):
                    if not os.path.exists(os.path.join(out, "public", p.lstrip("/"))):
                        missing_media.append({**_item_head(item), "url": url})
                elif (p.rstrip("/") or "/") not in new_paths and kind == "link":
                    broken_links.append({**_item_head(item), "url": url})
            elif u.netloc == site_host:
                parts = split_link(url, home)
                old_links.append({**_item_head(item), "url": url, "kind": kind,
                                  "class": classify_old_link(parts[0] if parts else u.path)})
            elif kind == "image" and u.netloc:
                external_images[u.netloc] += 1

    # 5. Leftovers (kept HTML, dropped tags, shortcodes) and block names.
    leftovers = collections.Counter()
    for i in manifest["items"]:
        for l in i["leftovers"]:
            leftovers[(l["kind"], l.get("tag") or l.get("name") or "")] += l["count"]

    # 6. Redirect coverage: every published item is either at its old path or has rules.
    published = [r for r in rows if r["status"] == "publish"]
    unchanged = sum(1 for r in published if not r["old_query"] and r["old_path"] == r["new_path"])
    with open(os.path.join(out, "redirects", "unmapped.json"), encoding="utf-8") as f:
        unmapped = json.load(f)

    low = [p for p in pages if p["coverage"] < TEXT_THRESHOLD]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "site": manifest["site"], "authed": manifest["authed"], "url_style": manifest.get("url_style"),
        "pulled_at": manifest["pulled_at"],
        "summary": {
            "items_source": sum(c["source"] for c in counts if c["type"] != "media"),
            "items_written": sum(c["written"] for c in counts if c["type"] != "media"),
            "media_source": len(source["media"]), "media_written": media_files_ok,
            "text_below_threshold": len(low), "text_threshold": TEXT_THRESHOLD,
            "missing_media_refs": len(missing_media), "broken_internal_links": len(broken_links),
            "links_to_old_site": len(old_links),
            "kept_html": sum(n for (k, _), n in leftovers.items() if k == "html"),
            "dropped": sum(n for (k, _), n in leftovers.items() if k == "dropped"),
            "shortcodes": sum(n for (k, _), n in leftovers.items() if k == "shortcode"),
            "published": len(published), "published_unchanged_url": unchanged,
            "unmapped_archives": len(unmapped),
        },
        "counts": counts,
        "pages": sorted(pages, key=lambda p: p["coverage"]),
        "missing_media": missing_media,
        "broken_links": broken_links,
        "old_links_by_class": dict(collections.Counter(l["class"] for l in old_links)),
        "old_links": old_links,
        "external_image_hosts": dict(external_images.most_common()),
        "leftovers": [{"kind": k, "what": w, "count": n} for (k, w), n in leftovers.most_common()],
        "unmapped": unmapped,
    }
    if server:
        report["redirect_check"] = check_server(out, server, rows)
    return report


def _item_head(item: dict) -> dict:
    return {"wp_id": item["wp_id"], "type": item["type"], "status": item["status"],
            "title": item["title"], "out_path": item["out_path"], "new_path": item.get("new_path")}


def write_report(out: str, server: str | None = None) -> dict:
    from .report_html import render

    report = verify(out, server)
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "report.html"), "w", encoding="utf-8") as f:
        f.write(render(report))
    return report
