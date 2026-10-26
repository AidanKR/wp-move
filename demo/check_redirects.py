"""Request every old URL from url-map.csv against a server and check it 301s to the new path.

usage: python check_redirects.py OUT_DIR http://127.0.0.1:PORT
"""
import csv
import http.client
import sys
import urllib.parse


def expectations(out: str):
    with open(f"{out}/redirects/url-map.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["status"] != "publish":
                continue
            new = row["new_path"]
            if not row["old_query"] and row["old_path"] != new:
                yield "permalink", row["old_path"], new
            yield "post-id", f"/?p={row['wp_id']}", new
            if row["type"] == "page":
                yield "page-id", f"/?page_id={row['wp_id']}", new
    yield "uploads", "/wp-content/uploads/2008/06/windmill.jpg", "/media/2008/06/windmill.jpg"


def main(out: str, server: str) -> int:
    host = urllib.parse.urlsplit(server).netloc
    total, bad = 0, []
    by_kind: dict[str, list[int]] = {}
    for kind, old, new in expectations(out):
        conn = http.client.HTTPConnection(host, timeout=10)
        conn.request("GET", urllib.parse.quote(old, safe="/?=&%"))
        r = conn.getresponse()
        loc = urllib.parse.unquote(urllib.parse.urlsplit(r.getheader("Location") or "").path)
        conn.close()
        ok = r.status == 301 and loc == new
        total += 1
        by_kind.setdefault(kind, [0, 0])
        by_kind[kind][0] += ok
        by_kind[kind][1] += 1
        if not ok:
            bad.append((kind, old, new, r.status, loc))
    for k, (ok, n) in by_kind.items():
        print(f"{k:10} {ok}/{n} ok")
    for b in bad[:10]:
        print("FAIL", b)
    print(f"total {total - len(bad)}/{total} ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
