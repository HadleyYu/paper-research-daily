"""CLI for deterministic operations, not an autonomous literature reviewer."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__
from .config import load_profile, library_root, new_profile, report_date, write_profile, profile_fingerprint, is_confirmed


def _emit(value, out=None):
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Research exports never overwrite the user's prior evidence implicitly.
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    else:
        print(text, end="")


def _papers(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("papers", data.get("candidates"))
    if not isinstance(data, list) or not all(isinstance(paper, dict) for paper in data):
        raise ValueError("Input must be a list of paper objects or {papers: [...]}")
    return data


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a draft research profile")
    init.add_argument("--profile", required=True)
    init.add_argument("--topic", required=True)
    init.add_argument("--root", required=True, help="Library root, relative to profile or absolute")
    init.add_argument("--language", choices=["zh-CN", "en"], default="zh-CN")
    init.add_argument("--timezone", default="Asia/Shanghai")
    init.add_argument("--count", type=int, default=8)
    init.add_argument("--new-count", type=int)
    for name in ("confirm", "check-profile", "scan", "prepare", "pool", "publish", "validate"):
        sub = commands.add_parser(name)
        sub.add_argument("--profile", required=True)
        if name in ("prepare", "pool", "publish"):
            sub.add_argument("--input", required=True)
        if name in ("prepare", "publish", "validate"):
            sub.add_argument("--date", help="YYYY-MM-DD in the report timezone")
    search = commands.add_parser("search")
    search.add_argument("--source", required=True, choices=["arxiv", "arxiv-recent", "crossref", "openalex"])
    search.add_argument("--query", required=True, help="Search text, or category for arxiv-recent")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--out")
    download = commands.add_parser("download")
    download.add_argument("--url", required=True)
    download.add_argument("--out", required=True)
    commands.add_parser("doctor", help="Check local dependencies; no network or credentials")
    return p


def main(argv=None):
    # UTF-8 output is predictable in PowerShell and redirected Windows consoles.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    try:
        command = args.command
        if command == "init":
            profile = new_profile(args.topic, args.root, language=args.language,
                                  timezone=args.timezone, count=args.count, new_count=args.new_count)
            write_profile(args.profile, profile)
            _emit({"status": "draft", "profile": str(Path(args.profile)),
                   "next": "Review the profile with the user; run confirm only after their approval."})
            return 0
        if command == "doctor":
            dependencies = {name: find_spec(name) is not None for name in ("pypdf", "tzdata")}
            zones = {}
            for name in ("America/New_York", "Asia/Shanghai"):
                try:
                    zones[name] = bool(ZoneInfo(name))
                except Exception:
                    zones[name] = False
            result = {"version": __version__, "python": sys.version.split()[0],
                      "dependencies": dependencies, "timezones": zones,
                      "ok": all(dependencies.values()) and all(zones.values())}
            _emit(result)
            return 0 if result["ok"] else 1
        if command == "search":
            from . import sources
            functions = {"arxiv": sources.arxiv_search, "arxiv-recent": sources.arxiv_recent,
                         "crossref": sources.crossref_search, "openalex": sources.openalex_search}
            papers = functions[args.source](args.query, limit=args.limit)
            _emit({"source": args.source, "query": args.query,
                   "retrieved_at": datetime.now(ZoneInfo("UTC")).isoformat(),
                   "papers": papers, "review_status": "discovered_not_verified"}, args.out)
            return 0
        if command == "download":
            from .sources import download_pdf
            _emit(download_pdf(args.url, Path(args.out)))
            return 0
        profile = load_profile(args.profile)
        if command == "check-profile":
            _emit({"ok": True, "status": profile["confirmation"]["status"],
                   "requires_confirmation": not is_confirmed(profile),
                   "library_root": str(library_root(profile, args.profile)),
                   "report_date": report_date(profile), "profile": profile})
            return 0
        if command == "confirm":
            if not is_confirmed(profile):
                profile["confirmation"] = {"status": "confirmed", "confirmed_at": datetime.now(ZoneInfo("UTC")).isoformat(),
                                           "profile_sha256": profile_fingerprint(profile)}
                write_profile(args.profile, profile, overwrite=True)
            _emit({"status": "confirmed", "note": "Records the user's decision; does not grant additional host permissions."})
            return 0
        from . import library
        root = library_root(profile, args.profile)
        date = getattr(args, "date", None)
        if command != "validate" and not is_confirmed(profile):
            raise ValueError("Profile is draft or has changed. Obtain user confirmation, then run confirm.")
        if command == "scan":
            result = library.scan_existing(root)
        elif command == "pool":
            result = library.update_pool(root, _papers(args.input))
        elif command == "prepare":
            result = library.prepare(root, date or report_date(profile), _papers(args.input), profile)
        elif command == "publish":
            result = library.publish(root, date or report_date(profile), _papers(args.input), profile)
        elif command == "validate":
            result = library.validate_library(root, date, profile)
        else:
            raise ValueError("Unknown command")
        _emit(result)
        return 1 if result.get("ok") is False else 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        # Do not print traceback, profile values, environment or request headers.
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
