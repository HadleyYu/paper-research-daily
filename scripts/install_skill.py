#!/usr/bin/env python3
"""Copy this portable skill into an explicitly chosen agent skills directory."""
import argparse
import shutil
import sys
from pathlib import Path


def install(destination: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = destination.expanduser().resolve() / "paper-research-daily"
    if target.exists():
        raise FileExistsError("Destination exists. Keep the existing skill or move it before installing.")
    # A small allowlist excludes local profiles, paper libraries, git and secrets.
    names = ["SKILL.md", "README.md", "README.zh-CN.md", "LICENSE", "NOTICE.md",
             "pyproject.toml", "src", "scripts", "references", "agents", "examples"]
    missing = [name for name in names if not (source / name).exists()]
    if missing:
        raise ValueError("Incomplete distribution: " + ", ".join(missing))
    destination = target.parent
    destination.mkdir(parents=True, exist_ok=True)
    staging = destination / ".paper-research-daily-installing"
    staging.mkdir()  # Refuse ambiguous recovery instead of removing another run.
    try:
        for name in names:
            src, dst = source/name, staging/name
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", ".env", "*.pdf"))
            else:
                shutil.copy2(src, dst)
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path, help="The agent's skills parent directory")
    args = parser.parse_args()
    try:
        print(install(args.dest))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
