import os
import tempfile
import unittest

from wp_move.urls import LinkMap, build_redirects, new_path, split_link, write_files

HOME = "http://s.test"


class UrlsTest(unittest.TestCase):
    def test_split_link(self):
        self.assertEqual(split_link("http://s.test/2020/01/a/", HOME), ("/2020/01/a/", ""))
        self.assertEqual(split_link("http://s.test/?p=5", HOME), ("/", "p=5"))
        self.assertEqual(split_link("/greek/%ce%b1/", HOME), ("/greek/α/", ""))
        self.assertIsNone(split_link("https://other.test/x/", HOME))

    def test_new_path_styles(self):
        post = {"link": "http://s.test/2020/01/a/"}
        self.assertEqual(new_path("posts", post, HOME, "keep", "a", None), "/2020/01/a/")
        self.assertEqual(new_path("posts", post, HOME, "slug", "a", None), "/posts/a/")
        draft = {"link": "http://s.test/?p=9"}
        self.assertEqual(new_path("posts", draft, HOME, "keep", "d", None), "/posts/d/")
        page = {"link": "http://s.test/parent/child/"}
        self.assertEqual(new_path("pages", page, HOME, "slug", "child", "parent/child"), "/parent/child/")

    def test_link_map_rewrites_permalink_and_ids(self):
        lm = LinkMap(HOME)
        lm.add({"id": 5, "link": "http://s.test/2020/01/a/"}, "posts", "/posts/a/")
        lm.add({"id": 7, "link": "http://s.test/about/"}, "pages", "/about/")
        self.assertEqual(lm.rewrite("http://s.test/2020/01/a/#c1"), "/posts/a/#c1")
        self.assertEqual(lm.rewrite("http://s.test/2020/01/a"), "/posts/a/")
        self.assertEqual(lm.rewrite("http://s.test/?p=5"), "/posts/a/")
        self.assertEqual(lm.rewrite("http://s.test/?page_id=7"), "/about/")
        self.assertEqual(lm.rewrite("http://s.test/2020/01/a/?replytocom=3#respond"), "/posts/a/#respond")
        self.assertIsNone(lm.rewrite("http://s.test/?s=search"))
        self.assertIsNone(lm.rewrite("https://elsewhere.test/2020/01/a/"))

    def test_build_redirects(self):
        entries = [
            {"wp_id": 5, "type": "post", "status": "publish", "old_path": "/2020/01/a/", "old_query": "",
             "new_path": "/posts/a/"},
            {"wp_id": 6, "type": "post", "status": "publish", "old_path": "/2020/01/b/", "old_query": "",
             "new_path": "/2020/01/b/"},
            {"wp_id": 9, "type": "post", "status": "draft", "old_path": "/", "old_query": "p=9",
             "new_path": "/posts/d/"},
        ]
        rules = build_redirects(entries)
        pairs = {(r["from"], r["query"], r["to"]) for r in rules}
        self.assertIn(("/2020/01/a/", "", "/posts/a/"), pairs)
        self.assertNotIn(("/2020/01/b/", "", "/2020/01/b/"), pairs)  # unchanged path: no rule
        self.assertIn(("/", "p=6", "/2020/01/b/"), pairs)
        self.assertFalse(any(r["query"] == "p=9" for r in rules))  # drafts never had a public URL
        self.assertIn(("/wp-content/uploads/*", "", "/media/:splat"), pairs)

    def test_write_files_encodes_non_ascii(self):
        rules = [{"from": "/greek/α/", "query": "", "to": "/greek/α/x/", "kind": "permalink"}]
        with tempfile.TemporaryDirectory() as d:
            write_files(d, [], rules, [])
            with open(os.path.join(d, "redirects", "_redirects"), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("/greek/%CE%B1/ /greek/%CE%B1/x/ 301", text)


if __name__ == "__main__":
    unittest.main()
