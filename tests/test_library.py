"""Integrity tests exercise history, quota, identities and interrupted publication."""
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
from pypdf import PdfWriter

from paper_daily.config import new_profile
from paper_daily.library import (normalize_arxiv, normalize_doi, prepare, publish,
                                scan_existing, update_pool, validate_library)


def profile(count=2):
    p = new_profile("Contact manipulation", "library", count=count)
    p["confirmation"]["status"] = "confirmed"
    return p


def paper(tmp_path, number=1, category="published"):
    path = tmp_path / f"source {number}.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": f"Paper {number}"})
    with path.open("wb") as stream:
        writer.write(stream)
    return {
        "title": f"Paper {number}: contact / control?",
        "authors": [f"Researcher {number}"],
        "doi": f"10.1234/paper{number}", "arxiv_id": f"2610.{number:05d}",
        "category": category, "official_url": "https://example.org/paper",
        "publication_status": "published", "source_pdf": str(path),
        "version": "accepted manuscript", "evidence_level": "fulltext",
        "score": {"relevance": 33, "evidence": 23, "inspiration": 18, "novelty": 8, "representative": 4, "reproducibility": 4},
        "score_reason": "Evidence and fit were independently assessed.",
        "selection_reason": "Complements the research question.",
        "sections": {k: f"Grounded {k} analysis, p. 1." for k in ("abstract", "problem", "mechanism", "novelty", "evidence", "limitations", "relevance", "microexperiment", "reading")},
        "sources": [{"url": "https://example.org/paper", "role": "publication"}, {"url": "https://arxiv.org/list/cs.RO/recent", "role": "discovery"}],
        "discovery_source": "arxiv", "first_announced_date": "2026-10-08",
    }


def test_identifier_normalization():
    assert normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert normalize_arxiv("https://arxiv.org/pdf/2610.12345v3.pdf") == "2610.12345"
    assert normalize_arxiv("arXiv:math.OC/0601001v2") == "math.oc/0601001"
    for value in ("../abc", "not-a-doi"):
        with pytest.raises(ValueError):
            normalize_doi(value)


def test_prepared_profile_and_rescored_total(tmp_path):
    root = tmp_path / "library"
    item = paper(tmp_path)
    p = profile(1)
    p["language"] = "en"
    p["timezone"] = "America/New_York"
    p["project"]["research_question"] = "Which assumptions change decisions?"
    result = prepare(root, "2026-10-10", [item], p)
    preview = Path(result["overview"]).read_text(encoding="utf-8")
    assert "Which assumptions change decisions?" in preview
    assert "America/New_York" in preview
    assert "Author abstract, faithfully paraphrased" in preview
    assert "90/100" in preview
    publish(root, "2026-10-10", [item], p)
    item["score"]["evidence"] += 1
    update_pool(root, [item])
    ledger = json.loads((root / "registry.json").read_text(encoding="utf-8"))
    assert ledger["papers"][0]["score_total"] == sum(item["score"].values()) == 91
    assert ledger["papers"][0]["recommended_dates"] == ["2026-10-10"]
    assert validate_library(root)["ok"]
    ledger["papers"][0]["score_total"] = 1
    (root / "registry.json").write_text(json.dumps(ledger), encoding="utf-8")
    assert not validate_library(root)["ok"]


def test_prepare_does_not_recommend_and_weekend_publish_is_idempotent(tmp_path):
    root = tmp_path / "中文 library"
    items = [paper(tmp_path, n) for n in (1, 2)]
    prepared = prepare(root, "2026-10-10", items)
    assert prepared["recommended"] == 0
    draft = Path(prepared["overview"]).read_text(encoding="utf-8")
    assert "DRAFT / 预备资料" in draft
    assert "尚未正式推荐" in draft
    assert "[PDF]" in draft
    ledger = json.loads((root / "registry.json").read_text(encoding="utf-8"))
    assert all(not p["recommended_dates"] for p in ledger["papers"])
    p = profile()
    first = publish(root, "2026-10-10", items, p)
    assert first["status"] == "published" and first["pdfs"] == 2
    assert publish(root, "2026-10-10", items, p)["status"] == "unchanged"
    result = validate_library(root, "2026-10-10", p)
    assert result["ok"], result
    assert result["pdfs_checked"] == 2
    assert not result["external_urls_checked"]
    assert "Grounded mechanism" in (root / "2026-10-10/00_overview.md").read_text(encoding="utf-8")
    assert all(not any(c in path.name for c in ':?') for path in (root / "2026-10-10").glob("*.pdf"))
    with pytest.raises(ValueError, match="Previously owned"):
        publish(root, "2026-10-11", items, p)


def test_weekday_fallback_and_freshness(tmp_path):
    root = tmp_path / "library"
    items = [paper(tmp_path, n) for n in (1, 2)]
    with pytest.raises(ValueError, match="fallback_reason"):
        publish(root, "2026-10-09", items, profile())
    items[1]["category"] = "new_arxiv"
    items[1]["first_announced_date"] = "2026-09-01"
    items[1]["revision_date"] = "2026-10-09"
    with pytest.raises(ValueError, match="window"):
        publish(root, "2026-10-09", items, profile())
    items[1]["first_announced_date"] = "2026-10-08"
    items[1]["sources"][1]["url"] = "https://arxiv.org.example.org/list"
    with pytest.raises(ValueError, match="arXiv-owned"):
        publish(root, "2026-10-09", items, profile())
    items[1]["category"] = "published"
    items[1]["fallback_reason"] = "Verified official new-paper searches found no qualified unread candidates."
    assert publish(root, "2026-10-09", items, profile())["status"] == "published"


def test_existing_date_pdf_blocks_recommendation_by_hash(tmp_path):
    root = tmp_path / "library"
    old = root / "2026-01-01"
    old.mkdir(parents=True)
    item = paper(tmp_path)
    (old / "existing.pdf").write_bytes(Path(item["source_pdf"]).read_bytes())
    assert scan_existing(root)["registered"] == 1
    assert scan_existing(root)["already_known"] == 1
    with pytest.raises(ValueError, match="Previously owned"):
        publish(root, "2026-10-10", [item], profile(1))


def test_alias_merge_preserves_registry_id(tmp_path):
    root = tmp_path / "library"
    item = paper(tmp_path)
    initial = deepcopy(item)
    initial["doi"] = None
    update_pool(root, [initial])
    publish(root, "2026-10-10", [item], profile(1))
    assert validate_library(root, "2026-10-10")["ok"]
    data = json.loads((root / "2026-10-10/metadata.json").read_text(encoding="utf-8"))
    assert data["papers"][0]["id"].startswith("arxiv:")


def test_title_only_not_merge_but_overlapping_author_requires_review(tmp_path):
    root = tmp_path / "library"
    first, second = paper(tmp_path, 1), paper(tmp_path, 2)
    second["title"] = first["title"]
    result = update_pool(root, [first, second])
    assert len(result["accepted"]) == 2
    third = paper(tmp_path, 3)
    third.update(title=first["title"], authors=first["authors"])
    result = update_pool(root, [third])
    assert "Possible duplicate" in result["rejected"][0]["reason"]


def test_foreign_date_and_changed_selection_are_not_overwritten(tmp_path):
    root = tmp_path / "library"
    target = root / "2026-10-10"
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("untouched", encoding="utf-8")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        publish(root, "2026-10-10", [paper(tmp_path)], profile(1))
    assert (target / "keep.txt").read_text(encoding="utf-8") == "untouched"


def test_interrupted_commit_recovers_on_next_mutation(tmp_path):
    import paper_daily.library as lib
    root = tmp_path / "library"
    item = paper(tmp_path)
    original = lib._atomic
    failed = False
    def crash_once(path, value, **kwargs):
        nonlocal failed
        if Path(path) == root / "registry.json" and (root / ".work/publication.json").exists() and not failed:
            failed = True
            raise OSError("simulated interruption after directory commit")
        return original(path, value, **kwargs)
    with patch.object(lib, "_atomic", side_effect=crash_once):
        with pytest.raises(OSError, match="simulated"):
            publish(root, "2026-10-10", [item], profile(1))
    assert (root / ".work/publication.json").exists()
    assert publish(root, "2026-10-10", [item], profile(1))["status"] == "unchanged"
    assert not (root / ".work/publication.json").exists()
    assert validate_library(root, "2026-10-10")["ok"]


def test_missing_pdf_abstract_mode_is_explicit(tmp_path):
    root = tmp_path / "library"
    item = paper(tmp_path)
    item.pop("source_pdf")
    item.update(evidence_level="abstract", sections={"abstract": "Faithful abstract paraphrase."}, download_reason="Publisher access unavailable.")
    item.pop("score")
    p = profile(1)
    with pytest.raises(ValueError, match="Abstract-only"):
        publish(root, "2026-10-10", [item], p)
    p["selection"]["allow_abstract_only"] = True
    publish(root, "2026-10-10", [item], p)
    overview = (root / "2026-10-10/00_overview.md").read_text(encoding="utf-8")
    assert "仅摘要级阅读" in overview and "pending/100" in overview


def test_lock_scores_and_examples(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    (root / ".paper-daily.lock").write_text("another writer", encoding="utf-8")
    with pytest.raises(RuntimeError, match="locked"):
        scan_existing(root)
    (root / ".paper-daily.lock").unlink()
    item = paper(tmp_path)
    item["example_only"] = True
    with pytest.raises(ValueError, match="example_only"):
        publish(root, "2026-10-10", [item], profile(1))
    item.pop("example_only")
    item["score"]["evidence"] = float("nan")
    with pytest.raises(ValueError, match="Score evidence"):
        publish(root, "2026-10-10", [item], profile(1))


def test_relative_pdf_unicode_filename_and_historical_count(tmp_path):
    root = tmp_path / "中文 library"
    root.mkdir()
    item = paper(root)
    item["source_pdf"] = Path(item["source_pdf"]).name
    item["title"] = "接触控制论文" * 60
    publish(root, "2026-10-10", [item], profile(1))
    assert validate_library(root, "2026-10-10", profile(8))["ok"]
    path = next((root / "2026-10-10").glob("*.pdf"))
    assert len(path.name.encode("utf-8")) < 200
    assert all((root / f"{view}.md").exists() for view in ("pool", "pending", "archive"))


def test_pool_update_cannot_erase_recommendation_history(tmp_path):
    root = tmp_path / "library"
    item = paper(tmp_path)
    publish(root, "2026-10-10", [item], profile(1))
    item.update(status="active", recommended_dates=[], selection_reason="Re-reviewed")
    update_pool(root, [item])
    entry = json.loads((root / "registry.json").read_text(encoding="utf-8"))["papers"][0]
    assert entry["status"] == "recommended"
    assert entry["recommended_dates"] == ["2026-10-10"]
    with pytest.raises(ValueError, match="Previously owned"):
        publish(root, "2026-10-11", [item], profile(1))


def test_date_selection_change_refused(tmp_path):
    root = tmp_path / "library"
    item = paper(tmp_path)
    publish(root, "2026-10-10", [item], profile(1))
    item["sections"]["mechanism"] = "An altered review must not silently overwrite the archive."
    with pytest.raises(ValueError, match="refusing to overwrite"):
        publish(root, "2026-10-10", [item], profile(1))


def test_partial_preparation_is_readable_without_publishing(tmp_path):
    root = tmp_path / "library"
    result = prepare(root, "2026-10-10", [{"title": "Unverified partial candidate", "authors": ["A. Researcher"], "sections": {"abstract": "Summary still requires full-text verification."}}])
    assert result["prepared"] == 1 and result["recommended"] == 0
    assert not (root / "2026-10-10").exists()
    text = Path(result["overview"]).read_text(encoding="utf-8")
    assert "Unverified partial candidate" in text
    assert "pending" in text
    ledger = json.loads((root / "registry.json").read_text(encoding="utf-8"))
    assert ledger["papers"][0]["recommended_dates"] == []
