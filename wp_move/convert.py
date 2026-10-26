"""HTML -> Markdown with front matter. Anything Markdown cannot hold is kept as raw HTML and listed."""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Comment
from markdownify import MarkdownConverter

# Kept verbatim as HTML in the Markdown body (and reported).
KEEP_AS_HTML = ("iframe", "video", "audio", "embed", "object", "form", "table", "details", "svg", "canvas")
# Dropped entirely (and reported).
DROP = ("script", "style", "noscript")
SHORTCODE_RE = re.compile(r"\[(/?)([a-zA-Z][\w-]*)(\s[^\]]*)?\]")
BLOCK_RE = re.compile(r"<!--\s+wp:([a-z0-9-]+(?:/[a-z0-9-]+)?)")
PLACEHOLDER = "WPMOVEKEEP{}X"


@dataclass
class Converted:
    markdown: str
    leftovers: list[dict] = field(default_factory=list)
    images: list[str] = field(default_factory=list)  # image URLs as they appeared in the source HTML


class _Converter(MarkdownConverter):
    pass


def blocks_used(raw_content: str | None) -> list[str]:
    """Distinct block names in post_content (only present with context=edit)."""
    return sorted(set(BLOCK_RE.findall(raw_content or "")))


def html_to_markdown(html: str, rewrite_url=None) -> Converted:
    """Convert rendered post HTML. rewrite_url(url) -> new url or None (leave as is)."""
    soup = BeautifulSoup(html or "", "html.parser")
    leftovers: list[dict] = []
    images: list[str] = []

    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in soup.find_all(DROP):
        leftovers.append({"kind": "dropped", "tag": tag.name})
        tag.decompose()

    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            images.append(src)
        for attr in ("srcset", "sizes", "loading", "decoding"):
            img.attrs.pop(attr, None)
    for source in soup.find_all("source"):
        source.attrs.pop("srcset", None)

    if rewrite_url:
        for tag, attr in (("img", "src"), ("a", "href"), ("source", "src"), ("video", "src"),
                          ("audio", "src"), ("video", "poster")):
            for el in soup.find_all(tag):
                old = el.get(attr)
                new = rewrite_url(old) if old else None
                if new:
                    el[attr] = new
                    if tag == "a" and el.string and el.string.strip() == old:
                        el.string = new  # fallback links that print their own URL

    # Dynamic blocks (comment forms, query-loop paging) render links to the API request URI. A fragment
    # still works on the static page; anything else cannot, so the link is unwrapped and reported.
    for a in soup.find_all("a", href=True):
        if "/wp-json/" in a["href"]:
            frag = urllib.parse.urlsplit(a["href"]).fragment
            if frag:
                a["href"] = f"#{frag}"
            else:
                leftovers.append({"kind": "dynamic-link", "tag": "a"})
                a.unwrap()

    kept: list[str] = []
    for tag in soup.find_all(KEEP_AS_HTML):
        if tag.find_parent(KEEP_AS_HTML):
            continue
        leftovers.append({"kind": "html", "tag": tag.name})
        kept.append(str(tag))
        tag.replace_with(PLACEHOLDER.format(len(kept) - 1))

    for text in soup.find_all(string=True):
        for m in SHORTCODE_RE.finditer(text):
            if not m.group(1):
                leftovers.append({"kind": "shortcode", "name": m.group(2)})

    md = _Converter(heading_style="ATX", bullets="-", escape_underscores=False,
                    sup_symbol="<sup>", sub_symbol="<sub>").convert_soup(soup)
    for i, raw in enumerate(kept):
        md = md.replace(PLACEHOLDER.format(i), f"\n\n{raw}\n\n")
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return Converted(md, _tally(leftovers), images)


def _tally(leftovers: list[dict]) -> list[dict]:
    """One entry per (kind, tag/name) with a count, in first-seen order."""
    counts: dict[tuple, dict] = {}
    for l in leftovers:
        key = (l["kind"], l.get("tag"), l.get("name"))
        if key in counts:
            counts[key]["count"] += 1
        else:
            counts[key] = {**l, "count": 1}
    return list(counts.values())


def front_matter(fields: dict) -> str:
    """YAML front matter. Values are emitted as JSON scalars/lists, which YAML accepts verbatim."""
    lines = ["---"]
    for k, v in fields.items():
        if v is None or v == [] or v == "":
            continue
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"
