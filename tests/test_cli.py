import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT/"scripts/paper_daily.py"), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", cwd=ROOT)

    def test_onboarding_and_approval_invalidated_by_change(self):
        with tempfile.TemporaryDirectory(prefix="课题 with space ") as temp:
            profile = Path(temp)/"profile.json"
            result = self.run_cli("init", "--profile", profile, "--topic", "Climate adaptation", "--root", "library", "--language", "en")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(profile.read_text(encoding="utf-8"))["confirmation"]["status"], "draft")
            self.assertEqual(self.run_cli("scan", "--profile", profile).returncode, 1)
            result = self.run_cli("confirm", "--profile", profile)
            self.assertEqual(result.returncode, 0, result.stderr)
            check = json.loads(self.run_cli("check-profile", "--profile", profile).stdout)
            self.assertFalse(check["requires_confirmation"])
            p = json.loads(profile.read_text(encoding="utf-8"))
            p["project"]["research_question"] = "A new question"
            profile.write_text(json.dumps(p), encoding="utf-8")
            self.assertEqual(self.run_cli("scan", "--profile", profile).returncode, 1)
            result = self.run_cli("confirm", "--profile", profile)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_init_never_overwrites_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"config.json"
            path.write_text("preserve this", encoding="utf-8")
            result = self.run_cli("init", "--profile", path, "--topic", "Example", "--root", "papers")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(path.read_text(encoding="utf-8"), "preserve this")


if __name__ == "__main__":
    unittest.main()
