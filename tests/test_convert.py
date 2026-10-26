import unittest

from wp_move.convert import blocks_used, front_matter, html_to_markdown
from wp_move.media import MediaMap


class ConvertTest(unittest.TestCase):
    def test_basic_markdown(self):
        c = html_to_markdown("<h2>Hi</h2><p>A <strong>b</strong> <a href='https://x.test/'>c</a></p>")
        self.assertIn("## Hi", c.markdown)
        self.assertIn("**b**", c.markdown)
        self.assertIn("[c](https://x.test/)", c.markdown)
        self.assertEqual(c.leftovers, [])

    def test_iframe_kept_and_reported(self):
        c = html_to_markdown('<p>x</p><iframe src="https://v.test/e"></iframe>')
        self.assertIn('<iframe src="https://v.test/e"></iframe>', c.markdown)
        self.assertEqual(c.leftovers, [{"kind": "html", "tag": "iframe", "count": 1}])

    def test_script_dropped_and_reported(self):
        c = html_to_markdown("<p>x</p><script>alert(1)</script>")
        self.assertNotIn("alert", c.markdown)
        self.assertEqual(c.leftovers, [{"kind": "dropped", "tag": "script", "count": 1}])

    def test_unrendered_shortcode_reported(self):
        c = html_to_markdown("<p>[gallery ids=\"1,2\"] and [/caption]</p>")
        self.assertEqual(c.leftovers, [{"kind": "shortcode", "name": "gallery", "count": 1}])

    def test_image_rewrite_and_srcset_removed(self):
        mm = MediaMap("http://site.test")
        mm.add_item({"source_url": "http://site.test/wp-content/uploads/2020/01/a.jpg",
                     "media_details": {"sizes": {"m": {"source_url": "http://site.test/wp-content/uploads/2020/01/a-300x200.jpg"}}}})
        c = html_to_markdown('<img src="http://site.test/wp-content/uploads/2020/01/a-300x200.jpg" '
                             'srcset="x 1x" alt="A">', rewrite_url=mm.rewrite)
        self.assertIn("![A](/media/2020/01/a-300x200.jpg)", c.markdown)
        self.assertNotIn("srcset", c.markdown)
        self.assertEqual(c.images, ["http://site.test/wp-content/uploads/2020/01/a-300x200.jpg"])

    def test_external_image_not_rewritten(self):
        mm = MediaMap("http://site.test")
        c = html_to_markdown('<img src="https://cdn.other.test/b.png" alt="B">', rewrite_url=mm.rewrite)
        self.assertIn("![B](https://cdn.other.test/b.png)", c.markdown)

    def test_media_map_rejects_traversal(self):
        mm = MediaMap("http://site.test")
        self.assertIsNone(mm.local_path("http://site.test/wp-content/uploads/../../wp-config.php"))

    def test_leftovers_are_tallied(self):
        c = html_to_markdown("<svg></svg><p>x</p><svg></svg>")
        self.assertEqual(c.leftovers, [{"kind": "html", "tag": "svg", "count": 2}])

    def test_fallback_link_text_rewritten(self):
        mm = MediaMap("http://site.test")
        u = "http://site.test/wp-content/uploads/2020/01/a.mp3"
        c = html_to_markdown(f'<a href="{u}">{u}</a>', rewrite_url=mm.rewrite)
        self.assertNotIn("site.test", c.markdown)

    def test_api_request_links_from_dynamic_blocks(self):
        c = html_to_markdown('<a href="/wp-json/wp/v2/posts?page=1#respond">Reply</a> '
                             '<a href="/wp-json/wp/v2/posts?page=1&query-2-page=2">Next</a>')
        self.assertIn("[Reply](#respond)", c.markdown)
        self.assertIn("Next", c.markdown)
        self.assertNotIn("wp-json", c.markdown)
        self.assertEqual(c.leftovers, [{"kind": "dynamic-link", "tag": "a", "count": 1}])

    def test_sup_sub_kept_inline(self):
        c = html_to_markdown("<p>up is <sup>super</sup>script, H<sub>2</sub>O</p>")
        self.assertIn("<sup>super</sup>script, H<sub>2</sub>O", c.markdown)

    def test_blocks_used(self):
        raw = "<!-- wp:paragraph --><p>a</p><!-- /wp:paragraph --><!-- wp:core/image {\"id\":1} -->"
        self.assertEqual(blocks_used(raw), ["core/image", "paragraph"])

    def test_front_matter_quotes(self):
        fm = front_matter({"title": 'He said "hi": ok', "tags": ["a", "b"], "empty": "", "none": None})
        self.assertEqual(fm, '---\ntitle: "He said \\"hi\\": ok"\ntags: ["a", "b"]\n---\n\n')


if __name__ == "__main__":
    unittest.main()
