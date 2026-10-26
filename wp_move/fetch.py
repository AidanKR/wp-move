"""Read-only WordPress REST API client: paginated GETs, optional Application Password auth."""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

USER_AGENT = "wp-move/0.0.1 (+https://github.com/AidanKR/wp-move)"
PER_PAGE = 100


class FetchError(RuntimeError):
    pass


@dataclass
class Client:
    site: str
    user: str | None = None
    app_password: str | None = None
    timeout: float = 30.0
    requests: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.site = self.site.rstrip("/")

    @property
    def authed(self) -> bool:
        return bool(self.user and self.app_password)

    def _get(self, path: str, params: dict | None = None) -> tuple[object, dict]:
        url = f"{self.site}/wp-json/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        if self.authed:
            token = base64.b64encode(f"{self.user}:{self.app_password}".encode()).decode()
            req.add_header("Authorization", f"Basic {token}")
        self.requests += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return json.load(resp), headers
        except urllib.error.HTTPError as e:
            body = e.read(300).decode("utf-8", "replace")
            raise FetchError(f"GET {url} -> HTTP {e.code}: {body}") from None
        except urllib.error.URLError as e:
            raise FetchError(f"GET {url} -> {e.reason}") from None

    def site_info(self) -> dict:
        data, _ = self._get("/")
        return {k: data.get(k) for k in ("name", "description", "url", "home")}

    def get_all(self, endpoint: str, **params) -> list[dict]:
        """Every item of a collection endpoint (e.g. 'wp/v2/posts'), following X-WP-TotalPages."""
        items: list[dict] = []
        page = 1
        while True:
            data, headers = self._get(endpoint, {**params, "per_page": PER_PAGE, "page": page})
            if not isinstance(data, list):
                raise FetchError(f"{endpoint}: expected a list, got {type(data).__name__}")
            items.extend(data)
            total_pages = int(headers.get("x-wp-totalpages", "1") or 1)
            if page >= total_pages or not data:
                return items
            page += 1


CONTENT_TYPES = ("posts", "pages")
TAXONOMY_TYPES = ("categories", "tags")


def fetch_site(client: Client) -> dict:
    """Snapshot everything the MVP needs. Drafts/scheduled/private come only with auth (context=edit)."""
    snap: dict = {"site": client.site_info(), "authed": client.authed}
    content_params = {"status": "any", "context": "edit"} if client.authed else {}
    for t in CONTENT_TYPES:
        snap[t] = client.get_all(f"wp/v2/{t}", **content_params)
    snap["media"] = client.get_all("wp/v2/media", **({"context": "edit"} if client.authed else {}))
    for t in TAXONOMY_TYPES:
        snap[t] = client.get_all(f"wp/v2/{t}")
    snap["users"] = client.get_all("wp/v2/users", **({"context": "edit"} if client.authed else {}))
    snap["requests"] = client.requests
    return snap
