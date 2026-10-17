"""Local literature ledger with conservative identity checks and recoverable publication.

No service credentials, network calls, or agent-specific dependencies are required.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import date as Date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from pypdf import PdfReader

from .render import SECTION_KEYS, render_overview

SCORE_KEYS = {"relevance", "evidence", "inspiration", "novelty", "representative", "reproducibility"}


def normalize_doi(value: str | None) -> str | None:
    value = unquote(str(value or "").strip())
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", value, flags=re.I)
    if not value:
        return None
    if not re.fullmatch(r"10\.\d{4,9}/\S+", value, flags=re.I):
        raise ValueError(f"Invalid DOI: {value}")
    return value.casefold()


def normalize_arxiv(value: str | None) -> str | None:
    value = str(value or "").strip()
    value = re.sub(r"^(?:https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/|arxiv\s*:\s*)", "", value, flags=re.I)
    value = re.sub(r"\.pdf$", "", value, flags=re.I)
    value = re.sub(r"v\d+$", "", value, flags=re.I)
    if not value:
        return None
    if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z][a-z.\-]+/\d{7})", value, flags=re.I):
        raise ValueError(f"Invalid arXiv identifier: {value}")
    return value.casefold()


def _norm(value):
    return "".join(c for c in unicodedata.normalize("NFKC", str(value)).casefold() if c.isalnum())


def _hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _date(value):
    result = Date.fromisoformat(str(value))
    if result.isoformat() != value:
        raise ValueError("Use a YYYY-MM-DD date")
    return result


def _json(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default


def _atomic(path, value, *, text=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = value if text else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    fd, name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def _lock(root):
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".paper-daily.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(f"Library is locked: {path}. If its process crashed, inspect it and remove it only after confirming no writer is running.") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "created_at": _utc()}, stream)
        _recover(root)
        yield root
    finally:
        path.unlink(missing_ok=True)


def _registry(root):
    result = _json(root / "registry.json", {"schema_version": 1, "papers": []})
    if not isinstance(result, dict) or result.get("schema_version") != 1 or not isinstance(result.get("papers"), list):
        raise ValueError("Unrecognized registry.json schema")
    return result


def _views(root, registry):
    groups = {"pool": [], "pending": [], "archive": []}
    for paper in registry["papers"]:
        status = paper.get("status")
        group = "pool" if status in {"active", "candidate", "prepared"} else "pending" if status == "awaiting_verification" else "archive"
        groups[group].append(paper)
    for name, papers in groups.items():
        _atomic(root / f"{name}.json", {"schema_version": 1, "papers": papers})
        labels = {"pool": "Active candidates / 活跃备选池", "pending": "Pending verification / 待核验池", "archive": "Archive and exclusions / 淘汰与历史记录"}
        lines = [f"# {labels[name]}", "", "| Paper | Status | Score | Reason | Entry |", "| --- | --- | --- | --- | --- |"]
        def cell(value):
            return str(value or "").replace("|", "\\|").replace("\n", " ")
        for p in papers:
            url = p.get("official_url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else f"https://arxiv.org/abs/{p['arxiv_id']}" if p.get("arxiv_id") else None)
            entry = f"[source]({url})" if url else ""
            if p.get("recommended_dates"):
                day = p["recommended_dates"][0]
                entry += f" [report]({day}/00_overview.md)"
            reason = p.get("candidate_reason") or p.get("reason") or p.get("selection_reason") or ""
            score = p.get("score_total")
            if score is None and p.get("score"):
                score = sum(v for v in p["score"].values() if isinstance(v, (int, float)))
            lines.append(f"| {cell(p['title'])} | {cell(p.get('status'))} | {score if score is not None else 'pending'} | {cell(reason)} | {entry} |")
        _atomic(root / f"{name}.md", "\n".join(lines) + "\n", text=True)
    lines = ["# Literature index / 文献总索引", "", "| Date | Report | Papers |", "| --- | --- | --- |"]
    for path in sorted(root.glob("????-??-??/metadata.json"), reverse=True):
        data = _json(path, {})
        if data.get("schema_version") == 1:
            day = path.parent.name
            lines.append(f"| {day} | [Overview / 总览]({day}/00_overview.md) | {len(data.get('papers', []))} |")
    _atomic(root / "index.md", "\n".join(lines) + "\n", text=True)


def _recover(root):
    """Finish only a journal created by this implementation; never overwrite a foreign day."""
    journal = root / ".work" / "publication.json"
    data = _json(journal)
    if not data:
        return
    _date(data["date"])
    target = root / data["date"]
    stage = root / ".work" / "transactions" / data["transaction"]
    if not re.fullmatch(r"[0-9a-f]{32}", data["transaction"]):
        raise ValueError("Invalid publication recovery journal")
    if target.exists():
        existing = _json(target / "metadata.json", {})
        if existing.get("fingerprint") != data["fingerprint"]:
            raise ValueError("Recovery refused: date directory does not match transaction")
    elif stage.exists():
        os.replace(stage, target)
    else:
        raise ValueError("Recovery requires the staged or published date directory")
    _atomic(root / "registry.json", data["registry"])
    _views(root, data["registry"])
    journal.unlink()


def _pdf(path):
    path = Path(path)
    with path.open("rb") as stream:
        if b"%PDF-" not in stream.read(1024):
            raise ValueError(f"Not a PDF: {path.name}")
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                raise ValueError(f"Encrypted PDF: {path.name}")
        except Exception as exc:
            raise ValueError(f"Unreadable encrypted PDF: {path.name}") from exc
    if not len(reader.pages):
        raise ValueError(f"PDF has no pages: {path.name}")
    text = "\n".join((page.extract_text() or "") for page in reader.pages[:3])
    return len(reader.pages), text


def _canonical(record, root=None):
    paper = json.loads(json.dumps(record))
    if "score" in paper:
        score = paper.get("score")
        if (isinstance(score, dict) and set(score) == SCORE_KEYS and
                all(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100
                    for value in score.values()) and sum(score.values()) <= 100):
            paper["score_total"] = sum(score.values())
        else:
            paper["score_total"] = None
        paper.setdefault("score_provisional", True)
    if not isinstance(paper.get("title"), str) or not paper["title"].strip():
        raise ValueError("Paper title is required")
    if not isinstance(paper.get("authors", []), list) or not all(isinstance(x, str) for x in paper.get("authors", [])):
        raise ValueError("authors must be a list of names")
    paper["doi"] = normalize_doi(paper.get("doi"))
    paper["arxiv_id"] = normalize_arxiv(paper.get("arxiv_id"))
    aliases = set(paper.get("aliases", []))
    for key in ("doi", "arxiv_id"):
        if paper.get(key):
            aliases.add(("arxiv" if key == "arxiv_id" else key) + ":" + paper[key])
    if paper.get("source_pdf"):
        path = Path(paper["source_pdf"]).expanduser()
        path = (Path(root) / path if root is not None and not path.is_absolute() else path).resolve()
        pages, _ = _pdf(path)
        paper.update(source_pdf=str(path), pdf_sha256=_hash(path), pages=pages)
    if paper.get("pdf_sha256"):
        aliases.add("sha256:" + paper["pdf_sha256"])
    paper["aliases"] = sorted(aliases)
    identity = next((a for prefix in ("doi:", "arxiv:", "sha256:") for a in sorted(aliases) if a.startswith(prefix)), None)
    paper["id"] = paper.get("id") or identity or "title:" + hashlib.sha256((_norm(paper["title"]) + ";" + ";".join(sorted(_norm(a) for a in paper.get("authors", [])))).encode()).hexdigest()[:24]
    return paper


def _match(paper, others):
    exact, possible = [], []
    for other in others:
        if paper.get("id") == other.get("id") or set(paper.get("aliases", [])) & set(other.get("aliases", [])):
            exact.append(other)
        elif _norm(paper["title"]) == _norm(other["title"]):
            overlap = {_norm(a) for a in paper.get("authors", [])} & {_norm(a) for a in other.get("authors", [])}
            if overlap:
                possible.append(other)
    if len(exact) > 1:
        raise ValueError("Candidate bridges multiple registry identities; manual identity resolution required")
    if possible and not exact:
        raise ValueError(f"Possible duplicate by title and overlapping author: {paper['title']}. Verify identity before adding.")
    return exact[0] if exact else None


def _merge(existing, paper):
    if not existing:
        return dict(paper, first_seen_at=_utc(), recommended_dates=[])
    result = dict(existing, **paper)
    result["id"] = existing["id"]
    result["aliases"] = sorted(set(existing.get("aliases", [])) | set(paper.get("aliases", [])))
    result["recommended_dates"] = existing.get("recommended_dates", [])
    result["files"] = list(existing.get("files", []))
    if existing.get("status") == "preexisting" or result["recommended_dates"]:
        result["status"] = existing["status"]
    return result


def _upsert(registry, paper):
    existing = _match(paper, registry["papers"])
    merged = _merge(existing, paper)
    if existing:
        registry["papers"][registry["papers"].index(existing)] = merged
    else:
        registry["papers"].append(merged)
    return merged


def scan_existing(root: Path) -> dict:
    """Register existing PDFs without recommending them, including unregistered date folders."""
    with _lock(root) as root:
        registry = _registry(root)
        registered_paths = {f["path"] for p in registry["papers"] for f in p.get("files", [])}
        found, errors, known = [], [], 0
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.casefold() != ".pdf" or ".work" in path.relative_to(root).parts:
                continue
            relative = path.relative_to(root).as_posix()
            if not path.resolve().is_relative_to(root):
                errors.append({"path": relative, "error": "PDF symlink points outside the library"})
                continue
            if relative in registered_paths:
                known += 1
                continue
            try:
                pages, text = _pdf(path)
                arxiv = set(re.findall(r"arXiv\s*:\s*((?:\d{4}\.\d{4,5}|[a-z][a-z.\-]+/\d{7})(?:v\d+)?)", text, re.I))
                # Text mentions can belong to cited works: record observations, never aliases.
                dois = set(re.findall(r"(?:doi\s*:\s*|https?://doi\.org/)(10\.\d{4,9}/[^\s<>]+)", text[:3000], re.I))
                paper = _canonical({"title": path.stem, "authors": [], "doi": None,
                                    "arxiv_id": None, "pdf_sha256": _hash(path), "pages": pages, "status": "preexisting",
                                    "identity_unverified": True, "observed_identifiers": {"doi": sorted(dois), "arxiv": sorted(arxiv)}})
                matched = _match(paper, registry["papers"])
                if matched:
                    merged = matched
                    known += 1
                else:
                    merged = _upsert(registry, paper)
                    found.append(merged["id"])
                merged.setdefault("files", []).append({"path": relative, "sha256": paper["pdf_sha256"]})
            except Exception as exc:
                errors.append({"path": relative, "error": str(exc)})
        _atomic(root / "registry.json", registry)
        _views(root, registry)
        return {"registered": len(found), "ids": found, "already_known": known, "errors": errors}


def _pool_update(root, records):
    registry = _registry(root)
    accepted, rejected = [], []
    for record in records:
        try:
            paper = _canonical(record, root)
            paper.setdefault("status", "active" if paper.get("evidence_level") == "fulltext" else "awaiting_verification")
            if paper["status"] not in {"active", "candidate", "prepared", "awaiting_verification", "deprioritized", "rejected", "archived"}:
                raise ValueError("Pool update cannot set preexisting/recommended status")
            accepted.append(_upsert(registry, paper))
        except (ValueError, OSError) as exc:
            rejected.append({"title": record.get("title"), "reason": str(exc)})
    _atomic(root / "registry.json", registry)
    _views(root, registry)
    return {"accepted": accepted, "rejected": rejected}


def update_pool(root: Path, records) -> dict:
    with _lock(root) as root:
        return _pool_update(root, records)


def prepare(root: Path, date: str, candidates: list[dict], profile: dict | None = None, *, updates=None) -> dict:
    _date(date)
    with _lock(root) as root:
        result = _pool_update(root, candidates)
        folder = root / ".work" / "prepared" / date
        _atomic(folder / "candidates.json", {"date": date, "prepared_at": _utc(), **result})
        preview = []
        for rank, paper in enumerate(result["accepted"], 1):
            item = dict(paper, rank=rank)
            item.setdefault("category", "candidate")
            if item.get("source_pdf"):
                source = Path(item["source_pdf"])
                try:
                    item["pdf_file"] = Path(os.path.relpath(source, folder)).as_posix()
                except ValueError:
                    # Windows cannot form a relative path between different drives.
                    item["pdf_file"] = source.as_uri()
            preview.append(item)
        header = (f"# DRAFT / 预备资料 · {date}\n\n"
                  "尚未正式推荐，不占用日报名额，也未新增推荐历史。以下为已登记候选的工作稿；数量可能不足，评分与卡片可能仍待核验。\n\n"
                  "Prepared candidates only: this is not a published daily report. No recommendation history is consumed. Counts, scores and analysis may be incomplete.\n\n")
        overview = folder / "00_prepared.md"
        if updates is not None:
            _atomic(folder / "watch_updates.json", updates)
        _atomic(overview, header + render_overview(date, preview, profile or {"language": "zh-CN"}, updates), text=True)
        return {"date": date, "prepared": len(result["accepted"]), "rejected": result["rejected"], "recommended": 0, "overview": str(overview)}


def _source_roles(paper):
    return {s.get("role") for s in paper.get("sources", []) if isinstance(s, dict) and urlparse(s.get("url", "")).scheme in {"https", "http"}}


def _check_paper(paper, day, profile):
    if paper.get("example_only"):
        raise ValueError("Synthetic example_only records cannot be published")
    if not paper.get("authors") or any(not name.strip() for name in paper["authors"]):
        raise ValueError("Verified author names are required for publication")
    if not isinstance(paper.get("version"), str) or not paper["version"].strip():
        raise ValueError("The actual version read is required for publication")
    selection = profile["selection"]
    category = paper.get("category")
    if category not in {"new_arxiv", "new", "published"}:
        raise ValueError("category must be new_arxiv, new, or published")
    roles = _source_roles(paper)
    if category == "published":
        if paper.get("publication_status") not in {"published", "online_first"} or not roles & {"publication", "official_publication"}:
            raise ValueError("Published papers require an official publication source and published/online_first status")
    else:
        source = paper.get("discovery_source")
        if source not in profile.get("sources", {}).get("new", ["arxiv"]):
            raise ValueError("New-paper discovery_source is not enabled in this profile")
        if category == "new_arxiv" or source == "arxiv":
            if not paper.get("arxiv_id") or source != "arxiv":
                raise ValueError("New arXiv papers require arxiv_id and discovery_source=arxiv")
            if not any(isinstance(s, dict) and urlparse(s.get("url", "")).hostname in {"arxiv.org", "export.arxiv.org", "rss.arxiv.org"} and s.get("role") in {"announcement", "arxiv", "discovery", "primary_publication"} for s in paper.get("sources", [])):
                raise ValueError("arXiv discovery must cite an arXiv-owned announcement/list/search source")
        elif not roles & {"announcement", "primary_publication"}:
            raise ValueError("New papers require a primary announcement/publication source")
        try:
            announced = Date.fromisoformat(paper.get("first_announced_date", ""))
        except (ValueError, TypeError) as exc:
            raise ValueError("New papers require first_announced_date in YYYY-MM-DD; revision dates do not reset freshness") from exc
        if not 0 <= (day - announced).days <= selection["max_lookback_days"]:
            raise ValueError("New paper is outside the permitted first-announcement window")
    evidence = paper.get("evidence_level")
    if evidence not in {"fulltext", "abstract"}:
        raise ValueError("evidence_level must be fulltext or abstract")
    if evidence == "abstract" and not selection["allow_abstract_only"]:
        raise ValueError("Abstract-only papers are disabled in the profile")
    if evidence == "abstract":
        paper["quality_status"] = "pending_fulltext_verification"
        paper["score_scope"] = "provisional_abstract_only"
    else:
        paper["quality_status"] = "fulltext_reviewed"
        paper["score_scope"] = "fulltext"
    sections = paper.get("sections", {})
    if not isinstance(sections, dict) or not sections.get("abstract"):
        raise ValueError("An original-abstract paraphrase is required")
    if not roles & {"abstract", "fulltext", "full_text", "publication", "official_publication", "arxiv", "primary_publication"}:
        raise ValueError("A source for the original abstract/full text is required")
    if evidence == "fulltext" and any(not sections.get(key) for key in SECTION_KEYS):
        raise ValueError("Full-text papers require all nine expanded-card sections")
    score = paper.get("score")
    if evidence == "abstract" and not score:
        paper["score"] = {}
        paper["score_total"] = None
    else:
        weights = profile["scoring"]
        if not isinstance(score, dict) or set(score) != set(weights):
            raise ValueError("Scores must contain exactly the configured dimensions")
        for key, maximum in weights.items():
            value = score[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum:
                raise ValueError(f"Score {key} must be within [0, {maximum}]")
        total = sum(score.values())
        if total < selection["min_score"] or score["relevance"] < selection["min_relevance"]:
            raise ValueError("Paper does not meet the confirmed score thresholds")
        if not paper.get("score_reason"):
            raise ValueError("Score rationale is required")
        paper["score_total"] = total
        paper["score_provisional"] = evidence != "fulltext"
    if not paper.get("selection_reason"):
        raise ValueError("Priority/selection rationale is required")
    if not paper.get("source_pdf") and not (paper.get("download_reason") or paper.get("download_status")):
        raise ValueError("Missing PDF requires an explicit download reason/status")
    if not paper.get("source_pdf") and not (paper.get("doi") or paper.get("official_url")):
        raise ValueError("Missing PDF requires a DOI or official access URL")


def _safe_filename(rank, title):
    value = unicodedata.normalize("NFKC", title)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    value = value[:100].rstrip(" .") or "paper"
    # APFS/ext4 limit bytes while NTFS limits UTF-16 units; fit both conservatively.
    while len(value.encode("utf-8")) > 180:
        value = value[:-1]
    return f"{rank:02d}_{value}.pdf"


def _fingerprint(papers, profile, updates=None):
    ignored = {"rank", "pdf_file", "id", "recommended_dates", "first_seen_at", "files", "status", "source_pdf"}
    payload = {"profile": profile, "papers": [{k: v for k, v in p.items() if k not in ignored} for p in papers]}
    if updates is not None:
        payload["watch_updates"] = updates
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def publish(root: Path, date: str, papers, profile, *, updates=None) -> dict:
    day = _date(date)
    if profile.get("confirmation", {}).get("status") != "confirmed":
        raise ValueError("Confirm the user's standards before publishing")
    if len(papers) != profile["selection"]["daily_count"]:
        raise ValueError("Selection count does not match the confirmed daily_count")
    with _lock(root) as root:
        registry = _registry(root)
        selected = []
        for raw in papers:
            paper = _canonical(raw, root)
            _check_paper(paper, day, profile)
            if _match(paper, selected):
                raise ValueError("Duplicate paper within today's selection")
            existing = _match(paper, registry["papers"])
            if existing and (existing.get("status") == "preexisting" or any(d != date for d in existing.get("recommended_dates", []))):
                raise ValueError(f"Previously owned or recommended paper: {paper['title']}")
            if existing:
                paper["id"] = existing["id"]
                paper["aliases"] = sorted(set(paper["aliases"]) | set(existing.get("aliases", [])))
            selected.append(paper)
        rules = profile["selection"]
        weekend = day.weekday() >= 5 and rules["weekend_mode"] == "combined"
        if not weekend:
            new_count = sum(p["category"] != "published" for p in selected)
            if new_count > rules["new_count"]:
                raise ValueError("Weekday new-paper quota exceeded")
            deficit = rules["new_count"] - new_count
            if deficit and sum(bool(p.get("fallback_reason")) for p in selected if p["category"] == "published") < deficit:
                raise ValueError("Published quota replacements require explicit fallback_reason for each missing new paper")
        fingerprint = _fingerprint(selected, profile, updates)
        target = root / date
        if target.exists():
            existing = _json(target / "metadata.json", {})
            if existing.get("fingerprint") == fingerprint:
                return {"date": date, "count": len(selected), "status": "unchanged", "overview": str(target / "00_overview.md")}
            raise ValueError("Date directory already exists with different content; refusing to overwrite")
        transaction = uuid.uuid4().hex
        stage = root / ".work" / "transactions" / transaction
        stage.mkdir(parents=True)
        output = []
        try:
            for rank, paper in enumerate(selected, 1):
                entry = dict(paper, rank=rank)
                if paper.get("source_pdf"):
                    filename = _safe_filename(rank, paper["title"])
                    shutil.copyfile(paper["source_pdf"], stage / filename)
                    if _hash(stage / filename) != paper["pdf_sha256"]:
                        raise ValueError("PDF changed while being copied")
                    entry["pdf_file"] = filename
                entry.pop("source_pdf", None)
                output.append(entry)
                merged = _upsert(registry, paper)
                merged.update(status="recommended", recommended_dates=[date])
                if entry.get("pdf_file"):
                    merged.setdefault("files", []).append({"path": f"{date}/{entry['pdf_file']}", "sha256": entry["pdf_sha256"]})
            metadata = {"schema_version": 1, "date": date, "timezone": profile.get("timezone"), "created_at": _utc(), "fingerprint": fingerprint, "mode": "weekend_combined" if weekend else "weekday", "expected_count": rules["daily_count"], "papers": output}
            if updates is not None:
                metadata["watch_updates"] = "watch_updates.json"
                metadata["watch_fingerprint"] = updates["fingerprint"]
                _atomic(stage / "watch_updates.json", updates)
            _atomic(stage / "metadata.json", metadata)
            _atomic(stage / "00_overview.md", render_overview(date, output, profile, updates), text=True)
            _atomic(stage / "search_log.json", {"date": date, "created_at": _utc(), "remote_urls_validated_by_engine": False, "records": [{"id": p["id"], "sources": p.get("sources", []), "search_log": p.get("search_log", []), "download_status": "downloaded" if p.get("pdf_file") else p.get("download_status", "unavailable"), "download_reason": p.get("download_reason"), "fallback_reason": p.get("fallback_reason")} for p in output]})
            _atomic(root / ".work" / "publication.json", {"transaction": transaction, "date": date, "fingerprint": fingerprint, "registry": registry})
            _recover(root)
        except Exception:
            # A written journal is intentionally retained for the next locked operation.
            if not (root / ".work" / "publication.json").exists():
                shutil.rmtree(stage, ignore_errors=True)
            raise
        return {"date": date, "count": len(output), "status": "published", "overview": str(target / "00_overview.md"), "pdfs": sum(bool(p.get("pdf_file")) for p in output)}


def validate_library(root: Path, date=None, profile=None) -> dict:
    root = Path(root).expanduser().resolve()
    errors, warnings = [], []
    if date:
        _date(date)
    registry = _registry(root)
    seen = {}
    for paper in registry["papers"]:
        scores = paper.get("score")
        if isinstance(scores, dict) and set(scores) == SCORE_KEYS:
            if all(type(v) in (int, float) and math.isfinite(v) for v in scores.values()):
                if paper.get("score_total") != sum(scores.values()):
                    errors.append(f"Score total disagrees with components: {paper['id']}")
        dates = paper.get("recommended_dates", [])
        if len(dates) != len(set(dates)) or len(dates) > 1 or (dates and paper.get("status") == "preexisting"):
            errors.append(f"Invalid recommendation history: {paper['id']}")
        for alias in paper.get("aliases", []):
            if alias in seen and seen[alias] != paper["id"]:
                errors.append(f"Duplicate identity alias: {alias}")
            seen[alias] = paper["id"]
        for file in paper.get("files", []):
            path = root / file["path"]
            if not path.resolve().is_relative_to(root):
                errors.append(f"File path escapes library: {file['path']}")
            elif not path.is_file() or _hash(path) != file["sha256"]:
                errors.append(f"Missing or changed registered PDF: {file['path']}")
    targets = [root / date] if date else sorted(p.parent for p in root.glob("????-??-??/metadata.json"))
    checked = 0
    for folder in targets:
        data = _json(folder / "metadata.json")
        if not data:
            errors.append(f"Missing metadata: {folder.name}")
            continue
        papers = data.get("papers", [])
        if data.get("watch_updates"):
            update_path = folder / "watch_updates.json"
            updates = _json(update_path, {})
            from .watch import _digest
            if updates.get("fingerprint") != data.get("watch_fingerprint") or _digest({k:v for k,v in updates.items() if k != "fingerprint"}) != updates.get("fingerprint"):
                errors.append(f"Changed watch snapshot: {folder.name}")
        expected = data.get("expected_count", profile["selection"]["daily_count"] if profile else None)
        if expected is None or len(papers) != expected:
            errors.append(f"Wrong paper count: {folder.name}")
        if [p.get("rank") for p in papers] != list(range(1, len(papers) + 1)):
            errors.append(f"Invalid priority ranks: {folder.name}")
        day_seen = set()
        for paper in papers:
            aliases = set(paper.get("aliases", []))
            if aliases & day_seen:
                errors.append(f"Repeated paper in {folder.name}: {paper.get('title')}")
            day_seen |= aliases
            match = next((p for p in registry["papers"] if p["id"] == paper.get("id")), None)
            if not match or folder.name not in match.get("recommended_dates", []):
                errors.append(f"Report/registry history mismatch: {paper.get('title')}")
            if paper.get("pdf_file"):
                path = folder / paper["pdf_file"]
                try:
                    if not path.resolve().is_relative_to(folder.resolve()):
                        raise ValueError("PDF path escapes date folder")
                    pages, text = _pdf(path)
                    if _hash(path) != paper.get("pdf_sha256"):
                        errors.append(f"PDF hash mismatch: {path.name}")
                    if len(text.strip()) < 40:
                        warnings.append(f"Little extractable PDF text; inspect rendering or OCR: {path.name}")
                    checked += 1
                except Exception as exc:
                    errors.append(str(exc))
        overview = folder / "00_overview.md"
        if not overview.is_file():
            errors.append(f"Missing overview: {folder.name}")
        else:
            for link in re.findall(r"\]\(([^\n]+?)\)", overview.read_text(encoding="utf-8")):
                target = unquote(link.split("#", 1)[0].strip("<>"))
                if target and not urlparse(target).scheme and not (folder / target).exists():
                    errors.append(f"Broken local link in {folder.name}: {target}")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "papers_registered": len(registry["papers"]), "pdfs_checked": checked, "external_urls_checked": False}
