import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def test_copy_is_portable_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="skills 中文 ") as temp:
            command = [sys.executable, str(ROOT / "scripts/install_skill.py"), "--dest", temp]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = Path(temp) / "paper-research-daily"
            self.assertTrue((installed/"SKILL.md").is_file())
            self.assertFalse((installed/".git").exists())
            self.assertFalse((installed/".venv").exists())
            check = subprocess.run([sys.executable, str(installed/"scripts/paper_daily.py"), "doctor"],
                                   cwd=temp, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertTrue(json.loads(check.stdout)["ok"])
            second = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(second.returncode, 1)
            self.assertIn("Destination exists", second.stderr)


if __name__ == "__main__":
    unittest.main()
