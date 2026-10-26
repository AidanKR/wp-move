import json
import os
import tempfile
import unittest

from wp_move.report_html import render
from wp_move.verify import classify_old_link, coverage, markdown_text, verify

HOME = "http://s.test"


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def make_out(d, body_a="Hello brave new world.", with_image=True):
    """Two posts (one with an image), one draft page, one media item."""
    source = {
        "site": {"name": "S", "home": HOME, "url": HOME},
        "posts": [
            {"id": 1, "status": "publish", "link": f"{HOME}/a/", "content": {"rendered": "<p>Hello brave new world.</p>"}},
            {"id": 2, "status": "publish", "link": f"{HOME}/b/", "content": {"rendered": "<p>See <a href='/a/'>a</a>.</p>"}},
        ],
        "pages": [{"id": 3, "status": "draft", "link": f"{HOME}/?page_id=3", "content": {"rendered": "<p>Draft</p>"}}],
        "media": [{"id": 9, "source_url": f"{HOME}/wp-content/uploads/x.jpg"}],
    }
    items = [
        {"wp_id": 1, "type": "post", "status": "publish", "title": "A", "out_path": "content/posts/a.md",
         "new_path": "/a/", "leftovers": [{"kind": "html", "tag": "iframe", "count": 2}], "images": []},
        {"wp_id": 2, "type": "post", "status": "publish", "title": "B", "out_path": "content/posts/b.md",
         "new_path": "/b/", "leftovers": [], "images": []},
        {"wp_id": 3, "type": "page", "status": "draft", "title": "D", "out_path": "content/pages/d.md",
         "new_path": "/d/", "leftovers": [], "images": []},
    ]
    manifest = {"site": source["site"], "authed": True, "url_style": "keep", "pulled_at": "2026-10-26T00:00:00+00:00",
                "items": items, "media": [{"url": f"{HOME}/wp-content/uploads/x.jpg", "local": "public/media/x.jpg",
                                           "ok": True, "original": True}]}
    _write(f"{d}/.wp-move/source.json", json.dumps(source))
    _write(f"{d}/.wp-move/manifest.json", json.dumps(manifest))
    _write(f"{d}/redirects/url-map.csv",
           "wp_id,type,status,old_url,old_path,old_query,new_path,out_path\n"
           f"1,post,publish,{HOME}/a/,/a/,,/a/,content/posts/a.md\n"
           f"2,post,publish,{HOME}/b/,/b/,,/b/,content/posts/b.md\n"
           f"3,page,draft,{HOME}/?page_id=3,/,page_id=3,/d/,content/pages/d.md\n")
    _write(f"{d}/redirects/unmapped.json", "[]")
    _write(f"{d}/content/posts/a.md", f'---\ntitle: "A"\n---\n\n{body_a}\n\n![x](/media/x.jpg)\n')
    _write(f"{d}/content/posts/b.md", '---\ntitle: "B"\n---\n\nSee [a](/a/) and [gone](/nope/) and '
                                      f'[cat]({HOME}/category/news/).\n')
    _write(f"{d}/content/pages/d.md", '---\ntitle: "D"\n---\n\nDraft\n')
    if with_image:
        _write(f"{d}/public/media/x.jpg", "jpg")


class VerifyTest(unittest.TestCase):
    def test_clean_output(self):
        with tempfile.TemporaryDirectory() as d:
            make_out(d)
            r = verify(d)
            s = r["summary"]
            self.assertEqual((s["items_source"], s["items_written"]), (3, 3))
            self.assertEqual((s["media_source"], s["media_written"]), (1, 1))
            self.assertEqual(s["missing_media_refs"], 0)
            self.assertEqual(s["text_below_threshold"], 0)
            self.assertEqual([b["url"] for b in r["broken_links"]], ["/nope/"])
            self.assertEqual(r["old_links_by_class"], {"taxonomy-archive": 1})
            self.assertEqual(s["kept_html"], 2)

    def test_deleted_image_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            make_out(d, with_image=False)
            r = verify(d)
            self.assertEqual(r["summary"]["media_written"], 0)
            self.assertEqual([m["url"] for m in r["missing_media"]], ["/media/x.jpg"])

    def test_lost_text_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            make_out(d, body_a="Hello.")
            r = verify(d)
            low = [p for p in r["pages"] if p["coverage"] < 0.95]
            self.assertEqual([p["wp_id"] for p in low], [1])

    def test_deleted_page_file_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            make_out(d)
            os.remove(f"{d}/content/posts/b.md")
            s = verify(d)["summary"]
            self.assertEqual((s["items_source"], s["items_written"]), (3, 2))

    def test_html_escapes_content(self):
        with tempfile.TemporaryDirectory() as d:
            make_out(d)
            r = verify(d)
            r["site"]["name"] = "<script>x</script>"
            self.assertNotIn("<script>x", render(r))

    def test_helpers(self):
        self.assertEqual(coverage("a b c d", "a b c d e"), 1.0)
        self.assertEqual(coverage("a b c d", "a b"), 0.5)
        self.assertEqual(coverage("see http://old.test/x/y", "see /x/y/"), 1.0)
        self.assertEqual(markdown_text("[Wind Farm](/a)[Download](/a)").split(), ["Wind", "Farm", "Download"])
        self.assertEqual(markdown_text("## Hi [there](/x/) ![img](/m.jpg) **bold**").split(), ["Hi", "there", "bold"])
        self.assertEqual(classify_old_link("/2024/02/"), "date-archive")
        self.assertEqual(classify_old_link("/wp-admin/profile.php"), "admin")


if __name__ == "__main__":
    unittest.main()
