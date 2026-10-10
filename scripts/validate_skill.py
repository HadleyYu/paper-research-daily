#!/usr/bin/env python3
"""Small offline package check; behavioral correctness is tested separately."""
import re
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), "Missing YAML frontmatter"
    front, body = text[4:].split("\n---", 1)
    assert re.search(r"^name: paper-research-daily$", front, re.M), "Invalid skill name"
    assert re.search(r"^description: .+", front, re.M), "Missing description"
    assert len(text.splitlines()) < 500, "Move optional guidance to references"
    for match in re.finditer(r"\]\(([^)#]+)(?:#[^)]*)?\)", text):
        link = match.group(1)
        if not link.startswith(("https://", "http://")):
            assert (root/link).is_file(), f"Missing reference: {link}"
    for name in ("README.md", "README.zh-CN.md", "LICENSE", "NOTICE.md", "pyproject.toml",
                 "scripts/paper_daily.py", "examples/profile.example.json", "references/candidate-schema.md"):
        assert (root/name).is_file(), f"Missing package file: {name}"
    assert "<TODO>" not in body and "[TODO:" not in body, "Unfinished scaffold"
    print("Skill package structure and relative references: OK")


if __name__ == "__main__":
    main()
