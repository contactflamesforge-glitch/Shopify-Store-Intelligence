import os
import tempfile
import unittest
from unittest.mock import patch

import prospecting


class ProspectingTests(unittest.TestCase):
    def test_clean_url_adds_scheme(self):
        self.assertEqual(prospecting.clean_url("example.com"), "https://example.com")

    def test_clean_url_rejects_empty(self):
        with self.assertRaises(ValueError):
            prospecting.clean_url("")

    def test_result_url_filters_social_sites(self):
        self.assertEqual(prospecting._result_url("https://instagram.com/brand"), "")
        self.assertEqual(prospecting._result_url("https://brand.example/products/a"), "https://brand.example")

    def test_discovery_diagnostics_are_defined(self):
        with patch.dict(os.environ, {"EXA_API_KEY": "", "BRAVE_SEARCH_API_KEY": ""}, clear=False):
            with patch.object(prospecting, "_ddg", return_value=[]), patch.object(prospecting, "_bing", return_value=[]):
                self.assertEqual(prospecting.discover_stores("skincare", "US", 5), [])
        self.assertTrue(prospecting.DISCOVERY_DIAGNOSTICS)

    def test_sqlite_crm_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(prospecting, "DB_PATH", os.path.join(folder, "crm.db")):
                item = {"domain": "sample.test", "url": "https://sample.test", "score": 70,
                        "emails": [], "status": "New", "notes": ""}
                prospecting.save_prospect(item)
                prospecting.update_prospect("sample.test", status="Contacted", notes="Follow up")
                loaded = prospecting.load_prospects()
                self.assertEqual(loaded[0]["status"], "Contacted")
                self.assertEqual(loaded[0]["notes"], "Follow up")


if __name__ == "__main__":
    unittest.main()
