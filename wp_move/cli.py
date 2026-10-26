"""wp-move command line."""
from __future__ import annotations

import argparse
import collections
import os
import sys

from .fetch import FetchError
from .pull import pull
from .verify import write_report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wp-move", description="Move a WordPress site you own to Markdown.")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("pull", help="fetch posts, pages and media into an output folder")
    pp.add_argument("site", help="site root URL, e.g. https://example.com")
    pp.add_argument("--out", default="out", help="output folder (default: out)")
    pp.add_argument("--no-media", action="store_true", help="skip downloading media files")
    pp.add_argument("--url-style", choices=("keep", "slug"), default="keep",
                    help="keep: new URLs reuse the old permalinks (default); slug: /posts/<slug>/ and /<page>/")
    rp = sub.add_parser("report", help="re-check an output folder and write report.html / report.json")
    rp.add_argument("--out", default="out", help="output folder produced by pull (default: out)")
    rp.add_argument("--server", help="also request old URLs on this server (running the generated redirects)")
    args = p.parse_args(argv)

    if args.cmd == "report":
        return _print_report(write_report(args.out, args.server), args.out)

    # Credentials only from the environment, never from arguments (they would land in shell history).
    user = os.environ.get("WPMOVE_USER")
    app_password = os.environ.get("WPMOVE_APP_PASSWORD")
    try:
        m = pull(args.site, args.out, user, app_password, with_media=not args.no_media,
                 url_style=args.url_style)
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    status = collections.Counter((i["type"], i["status"]) for i in m["items"])
    left = collections.Counter()
    for i in m["items"]:
        for l in i["leftovers"]:
            left[l["kind"]] += l["count"]
    files = {r["local"] for r in m["media"]}
    files_ok = {r["local"] for r in m["media"] if r["ok"]}
    print(f"site: {m['site'].get('name')} ({'authenticated' if m['authed'] else 'public only'})")
    print("source:", ", ".join(f"{k}={v}" for k, v in m["source_counts"].items()))
    print("written:", ", ".join(f"{t}/{s}={n}" for (t, s), n in sorted(status.items())))
    print(f"media: {len(files_ok)}/{len(files)} files ok ({len(m['media'])} URLs)")
    print("leftovers:", dict(left) or "none")
    r = m["redirects"]
    print(f"redirects ({m['url_style']}): {r['path_rules']} path rules, {r['query_rules']} query rules, "
          f"{r['unmapped']} archive URLs without a target")
    print(f"manifest: {os.path.join(args.out, '.wp-move', 'manifest.json')}")
    return _print_report(write_report(args.out), args.out)


def _print_report(r: dict, out: str) -> int:
    s = r["summary"]
    print(f"report: items {s['items_written']}/{s['items_source']}, media {s['media_written']}/{s['media_source']}, "
          f"text<{int(s['text_threshold'] * 100)}%: {s['text_below_threshold']}, missing media: {s['missing_media_refs']}, "
          f"broken links: {s['broken_internal_links']}, links to old site: {s['links_to_old_site']}")
    if "redirect_check" in r:
        rc = r["redirect_check"]
        ok = sum(v["ok"] for v in rc["by_kind"].values())
        total = sum(v["total"] for v in rc["by_kind"].values())
        print(f"redirects on {rc['server']}: {ok}/{total} ok")
    print(f"report: {os.path.join(out, 'report.html')}")
    hard_fail = s["items_written"] != s["items_source"] or s["media_written"] != s["media_source"] \
        or s["missing_media_refs"] or s["broken_internal_links"]
    return 2 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
