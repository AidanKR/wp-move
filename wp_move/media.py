"""Media: map site upload URLs to local paths, download only files hosted on the site itself."""
from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request

from .fetch import USER_AGENT


class MediaMap:
    """URL (any size variant) -> path under media/, keyed on the path after /wp-content/uploads/."""

    def __init__(self, site: str):
        self.host = urllib.parse.urlsplit(site).netloc
        self.urls: dict[str, str] = {}
        self.originals: set[str] = set()

    def local_path(self, url: str) -> str | None:
        parts = urllib.parse.urlsplit(url)
        if parts.netloc and parts.netloc != self.host:
            return None
        marker = "/wp-content/uploads/"
        if marker not in parts.path:
            return None
        rel = urllib.parse.unquote(parts.path.split(marker, 1)[1])
        if not rel or ".." in rel.split("/"):
            return None
        return "media/" + rel

    def add_item(self, item: dict) -> None:
        src = item.get("source_url")
        if src and (lp := self.local_path(src)):
            self.urls[src] = lp
            self.originals.add(src)
        for size in ((item.get("media_details") or {}).get("sizes") or {}).values():
            u = size.get("source_url")
            if u and (lp := self.local_path(u)):
                self.urls[u] = lp

    def rewrite(self, url: str) -> str | None:
        """New site-relative URL for a site upload, else None."""
        absolute = urllib.parse.urljoin(f"http://{self.host}/", url)
        lp = self.urls.get(absolute) or self.local_path(absolute)
        if not lp:
            return None
        self.urls.setdefault(absolute, lp)
        return "/" + lp


def download(url: str, dest: str, timeout: float = 60.0) -> tuple[bool, str]:
    """Fetch url into dest (skips existing non-empty files). Returns (ok, detail)."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True, "exists"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest + ".part"
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as f:
            while chunk := resp.read(1 << 16):
                f.write(chunk)
        os.replace(tmp, dest)
        return True, "downloaded"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        return False, str(getattr(e, "reason", e))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
