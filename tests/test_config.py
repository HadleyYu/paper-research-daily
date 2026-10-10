import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from paper_daily.config import new_profile, validate_profile, library_root, report_date, write_profile, load_profile, profile_fingerprint, is_confirmed


class ProfileTests(unittest.TestCase):
    def test_changed_standards_need_reconfirmation(self):
        p = new_profile("Example", "papers")
        p["confirmation"] = {"status": "confirmed", "profile_sha256": profile_fingerprint(p)}
        self.assertTrue(is_confirmed(p))
        p["project"]["research_question"] = "Another topic"
        self.assertFalse(is_confirmed(p))

    def test_custom_count_and_weights(self):
        p = new_profile("Climate policy", "papers", count=5, new_count=2, language="en")
        self.assertEqual(p["selection"]["published_count"], 3)
        p["selection"]["new_count"] = 4
        with self.assertRaises(ValueError):
            validate_profile(p)

    def test_path_relative_to_profile_not_cwd(self):
        with tempfile.TemporaryDirectory(prefix="研究 profile ") as temp:
            path = Path(temp) / "config.json"
            p = new_profile("Example", "资料 with spaces")
            write_profile(path, p)
            loaded = load_profile(path)
            self.assertEqual(library_root(loaded, path), Path(temp).resolve()/"资料 with spaces")
            with self.assertRaises(FileExistsError):
                write_profile(path, p)

    def test_dst_and_date_boundary(self):
        p = new_profile("Example", "papers")
        summer = datetime(2026, 7, 1, 0, 5, tzinfo=timezone.utc)
        winter = datetime(2026, 12, 1, 1, 5, tzinfo=timezone.utc)
        self.assertEqual(report_date(p, summer), "2026-07-01")
        self.assertEqual(report_date(p, winter), "2026-12-01")
        p["timezone"] = "America/New_York"
        self.assertEqual(report_date(p, summer), "2026-06-30")
        self.assertEqual(report_date(p, winter), "2026-11-30")
        with self.assertRaises(ValueError):
            report_date(p, datetime(2026, 1, 1))

    def test_profile_rejects_credential_fields(self):
        p = new_profile("Example", "papers")
        p["sources"]["api_key"] = "dummy-not-a-secret"
        with self.assertRaises(ValueError):
            validate_profile(p)

    def test_invalid_timezone_and_weights(self):
        p = new_profile("Example", "papers")
        p["timezone"] = "Not/AZone"
        with self.assertRaises(ValueError):
            validate_profile(p)
        p["timezone"] = "UTC"
        p["scoring"]["relevance"] = 99
        with self.assertRaises(ValueError):
            validate_profile(p)


if __name__ == "__main__":
    unittest.main()
