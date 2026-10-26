import unittest

from wp_move.pull import _page_path


class PagePathTest(unittest.TestCase):
    def test_nested_pretty_link(self):
        self.assertEqual(_page_path({"link": "http://s.test/level-1/level-2/"}, "http://s.test"), "level-1/level-2")

    def test_percent_encoded_slug_is_decoded(self):
        link = "http://s.test/greek/%ce%b5%cf%80%ce%af%cf%80%ce%b5%ce%b4%ce%bf-2/"
        self.assertEqual(_page_path({"link": link}, "http://s.test"), "greek/επίπεδο-2")

    def test_query_link_falls_back(self):
        self.assertIsNone(_page_path({"link": "http://s.test/?page_id=3"}, "http://s.test"))


if __name__ == "__main__":
    unittest.main()
