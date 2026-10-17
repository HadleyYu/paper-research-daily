"""Behavioral contracts for isolated news delivery and old paper compatibility."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import json
import subprocess
import sys
from unittest.mock import patch

import pytest
from paper_daily import watch
from paper_daily.config import new_profile, profile_fingerprint, is_confirmed, validate_profile
from paper_daily.library import publish as publish_papers, prepare as prepare_papers, validate_library
from test_library import paper


def profile(root="library"):
    p = new_profile("Reliable decision making", str(root), count=1)
    p["watch"] = {"enabled": True, "daily_limit": 3, "weekly": {"enabled": True, "weekday": 6}, "targets": [
        {"id": x, "name": x, "relevance": "Finite-data decisions", "official_urls": [f"https://example.org/{x}"]} for x in ("alpha", "beta")]}
    p["confirmation"] = {"status": "confirmed", "profile_sha256": profile_fingerprint(p)}
    return p


def event(kind="code", revision="owner/project@v1"):
    return {"kind": kind, "revision": revision, "title": "A reusable experiment release", "target_ids": ["alpha"],
            "work": {"arxiv_id": "2610.12345v2", "doi": "10.1234/example", "title": "Shared study", "authors": ["A. Example"]},
            "occurred_at": "2026-10-16T12:00:00Z", "date_evidence": "Dated official release", "first_discovered_at": "2026-10-16T13:00:00Z", "verified_at": "2026-10-16T13:30:00Z",
            "disposition": "eligible", "summary": "An agent supplied grounded summary.", "delta": "Reproducible evaluation is now available.", "relevance": "Enables a controlled comparison.", "action": "Review the setup before reproduction.", "limitations": "Not run independently.", "impact": 4, "impact_reason": "Changes the next experiment decision.",
            "sources": [{"url": "https://example.org/release", "primary": True, "supports": "Release and scope", "verified_at": "2026-10-16T13:30:00Z"}]}


def data(day="2026-10-17", events=None, status="checked"):
    cutoff = day + "T00:05:00+00:00"
    d = {"schema_version": 1, "date": day, "timezone": "Asia/Shanghai", "generated_at": cutoff,
         "coverage": [{"target_id": x, "status": status, "checked_at": cutoff, "detail": "Attempted original sources.", "sources": [f"https://example.org/{x}"]} for x in ("alpha", "beta")],
         "events": [event()] if events is None else events}
    if datetime.fromisoformat(day).weekday() == 6:
        d["weekly"] = {"status": "insufficient_evidence", "reason": "No verified seven-day route change.", "window_start": (datetime.fromisoformat(cutoff)-timedelta(days=7)).isoformat(), "window_end": cutoff, "changes": [], "questions": []}
    return d


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file() and p.relative_to(root).parts[0] != "watch"}


def test_missing_watch_does_not_mutate_profile_or_fingerprint():
    p = new_profile("Topic", "library"); old = deepcopy(p); fp = profile_fingerprint(p)
    validate_profile(p)
    assert p == old and "watch" not in p and profile_fingerprint(p) == fp
    with pytest.raises(ValueError, match="disabled"):
        watch.normalize_input(data(), "2026-10-17", p)


def test_prepare_merge_and_isolated_idempotent_publish(tmp_path):
    root = tmp_path / "中文 library"; root.mkdir()
    (root / "文献登记.json").write_text('{"papers": {"keep": "unchanged"}}', encoding="utf-8")
    (root / "2026-10-10").mkdir(); (root / "2026-10-10/history.md").write_bytes(b"history")
    p = profile(root); raw = data(); duplicate = event(); duplicate["target_ids"] = ["beta"]
    duplicate["sources"][0]["url"] = "https://example.org/another-official-page"
    raw["events"].append(duplicate)
    baseline = tree(root)
    prepared = watch.prepare(root, raw["date"], raw, p)
    assert prepared["displayed"] == 0 and prepared["candidates"] == 1
    assert not (root / "watch/registry.json").exists() and not (root / "2026-10-17").exists()
    published = watch.publish(root, raw["date"], raw, p)
    s = watch.load_snapshot(published["snapshot"], raw["date"], p)
    assert published["count"] == 1 and s["selected"][0]["target_ids"] == ["alpha", "beta"]
    assert len(s["selected"][0]["sources"]) == 2
    assert watch.publish(root, raw["date"], raw, p)["notify"] is False
    assert tree(root) == baseline
    assert watch.validate(root, raw["date"], p)["ok"]
    raw["events"][0]["summary"] = "Changed content"
    with pytest.raises(ValueError, match="different content"):
        watch.publish(root, raw["date"], raw, p)


def test_old_work_new_event_and_cross_day_dedup(tmp_path):
    p = profile(tmp_path)
    publish_papers(tmp_path, "2026-10-10", [paper(tmp_path)], p)
    saved = tree(tmp_path)
    old = event("paper", "first-publication"); old["disposition"] = "baseline"; old["reason"] = "Already known paper"
    watch.publish(tmp_path, "2026-10-17", data(events=[old, event()]), p)
    result = watch.publish(tmp_path, "2026-10-18", data("2026-10-18", [event(), event("code", "owner/project@v2")]), p)
    assert result["count"] == 1
    assert tree(tmp_path) == saved
    assert watch.validate(tmp_path, None, p)["ok"]


def test_cross_day_observations_keep_all_prior_targets_and_sources(tmp_path):
    p = profile(tmp_path); first = event(); second = event()
    second["target_ids"] = ["beta"]
    second["sources"][0]["url"] = "https://example.org/beta-release"
    watch.publish(tmp_path, "2026-10-17", data(events=[first, second]), p)
    before = json.loads((tmp_path / "watch/registry.json").read_text(encoding="utf-8"))["events"][0]
    assert watch.publish(tmp_path, "2026-10-18", data("2026-10-18", [event()]), p)["count"] == 0
    after = json.loads((tmp_path / "watch/registry.json").read_text(encoding="utf-8"))["events"][0]
    assert after["target_ids"] == before["target_ids"] == ["alpha", "beta"]
    assert after["sources"] == before["sources"] and len(after["sources"]) == 2
    assert after["displayed_dates"] == ["2026-10-17"]


def test_empty_baseline_failure_unknown_and_genuine_no_update(tmp_path):
    p = profile(tmp_path)
    texts = {}
    for status in ("baseline", "failed", "checked"):
        r = tmp_path / status
        result = watch.publish(r, "2026-10-17", data(events=[], status=status), p)
        texts[status] = Path(result["overview"]).read_text(encoding="utf-8")
        assert result["count"] == 0
    assert len(set(texts.values())) == 3
    unknown = event(); unknown.update(occurred_at=None, disposition="unknown_date", reason="Official page has no event date")
    assert watch.publish(tmp_path / "unknown", "2026-10-17", data(events=[unknown]), p)["count"] == 0
    unknown["disposition"] = "eligible"
    with pytest.raises(ValueError, match="Undated"):
        watch.prepare(tmp_path, "2026-10-17", data(events=[unknown]), p)


def test_selection_limits_and_reasons(tmp_path):
    events = [event("code", f"owner/project@v{i}") for i in range(5)]
    events[-1]["impact"] = 5
    r = watch.publish(tmp_path, "2026-10-17", data(events=events), profile(tmp_path))
    s = json.loads(Path(r["snapshot"]).read_text(encoding="utf-8"))
    assert r["count"] == 3 and s["selected"][0]["revision"].endswith("v4")
    assert len(s["decisions"]) == 2


def test_interrupted_watch_transaction_recovers(tmp_path):
    p = profile(tmp_path); original = watch._atomic; crashed = False
    def fail(path, *args, **kwargs):
        nonlocal crashed
        if Path(path) == tmp_path / "watch/registry.json" and not crashed:
            crashed = True
            raise OSError("Interrupted after folder publication")
        return original(path, *args, **kwargs)
    with patch.object(watch, "_atomic", side_effect=fail):
        with pytest.raises(OSError):
            watch.publish(tmp_path, "2026-10-17", data(), p)
    assert not watch.validate(tmp_path, "2026-10-17", p)["ok"]
    assert watch.publish(tmp_path, "2026-10-17", data(), p)["status"] == "unchanged"
    assert watch.validate(tmp_path, "2026-10-17", p)["ok"]


def test_local_sunday_window_and_no_unfounded_routes(tmp_path):
    p = profile(tmp_path); raw = data("2026-10-18")
    assert watch.prepare(tmp_path, "2026-10-18", raw, p)["displayed"] == 0
    raw.pop("weekly")
    with pytest.raises(ValueError, match="Sunday needs"):
        watch.prepare(tmp_path, "2026-10-18", raw, p)
    raw = data(); raw["weekly"] = data("2026-10-18")["weekly"]
    with pytest.raises(ValueError, match="Sundays"):
        watch.prepare(tmp_path, "2026-10-17", raw, p)
    raw = data("2026-10-18"); raw["weekly"]["window_start"] = "2026-10-10T00:00:00Z"
    with pytest.raises(ValueError, match="seven days"):
        watch.prepare(tmp_path, "2026-10-18", raw, p)


def test_snapshot_before_papers_and_integrity(tmp_path):
    p = profile(tmp_path); raw = data()
    result = watch.publish(tmp_path, "2026-10-17", raw, p)
    updates = watch.load_snapshot(result["snapshot"], "2026-10-17", p)
    item = paper(tmp_path)
    prepare_papers(tmp_path, "2026-10-17", [item], p, updates=updates)
    publish_papers(tmp_path, "2026-10-17", [item], p, updates=updates)
    text = (tmp_path / "2026-10-17/00_overview.md").read_text(encoding="utf-8")
    assert text.index("重点团队动态") < text.index("今日论文") < text.index(item["title"])
    assert publish_papers(tmp_path, "2026-10-17", [item], p, updates=updates)["status"] == "unchanged"
    assert validate_library(tmp_path, "2026-10-17", p)["ok"]
    updates["selected"][0]["summary"] = "Changed"
    Path(result["snapshot"]).write_text(json.dumps(updates), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        watch.load_snapshot(result["snapshot"], "2026-10-17", p)


@pytest.mark.parametrize("wrapper", [None, "papers", "candidates"])
def test_cli_old_inputs_and_news_failure_does_not_block(tmp_path, wrapper):
    root = tmp_path / "library"; p = profile(root)
    path = tmp_path / "profile.json"; path.write_text(json.dumps(p), encoding="utf-8")
    items = [paper(tmp_path)]; source = tmp_path / "input.json"
    source.write_text(json.dumps({wrapper: items} if wrapper else items), encoding="utf-8")
    cli = Path(__file__).resolve().parents[1] / "scripts/paper_daily.py"
    command = [sys.executable, str(cli), "publish", "--profile", str(path), "--input", str(source), "--date", "2026-10-17", "--updates", str(tmp_path / "missing.json")]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["updates_error"]
    assert validate_library(root, "2026-10-17", p)["ok"]


def test_missing_coverage_duplicate_conflict_and_lock(tmp_path):
    p = profile(tmp_path); d = data(); d["coverage"].pop()
    with pytest.raises(ValueError, match="every configured target"):
        watch.prepare(tmp_path, d["date"], d, p)
    d = data(); second = event(); second["occurred_at"] = "2026-10-16T11:00:00Z"; d["events"].append(second)
    with pytest.raises(ValueError, match="disagree"):
        watch.prepare(tmp_path, d["date"], d, p)
    (tmp_path / "watch").mkdir(); (tmp_path / "watch/.watch.lock").write_text("running", encoding="utf-8")
    with pytest.raises(RuntimeError, match="locked"):
        watch.prepare(tmp_path, "2026-10-17", data(), p)
