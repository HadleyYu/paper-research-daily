"""Optional, independent event ledger. Retrieval and scholarly judgment belong to the agent."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import re
import uuid

from .library import _atomic, _date, _json, _utc, _norm, normalize_arxiv, normalize_doi

KINDS = {"paper", "revision", "code", "weights", "dataset", "talk"}
COVERAGE = {"checked", "baseline", "failed", "partial"}


def _instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Watch timestamps must be ISO 8601 with a UTC offset") from exc


def _url(value):
    parsed = urlparse(str(value))
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Watch evidence needs a public HTTP(S) URL without credentials")


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Watch requires nonempty {field}")


def validate_config(config):
    if not isinstance(config, dict) or type(config.get("enabled")) is not bool:
        raise ValueError("watch.enabled must be a boolean")
    if not config["enabled"]:
        return
    if type(config.get("daily_limit")) is not int or not 0 <= config["daily_limit"] <= 3:
        raise ValueError("watch.daily_limit must be 0..3")
    targets = config.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("Enabled watch requires targets")
    ids = set()
    for target in targets:
        for key in ("id", "name", "relevance"):
            _text(target.get(key), f"target.{key}")
        if target["id"] in ids:
            raise ValueError("Duplicate watch target ID")
        ids.add(target["id"])
        if not target.get("official_urls"):
            raise ValueError("Watch target requires official_urls")
        for url in target["official_urls"]:
            _url(url)
    weekly = config.get("weekly", {})
    if type(weekly.get("enabled")) is not bool:
        raise ValueError("watch.weekly.enabled must be a boolean")
    if weekly.get("weekday", 6) != 6:
        raise ValueError("Weekly watch review is Sunday (weekday 6) in the report timezone")


def _settings(profile):
    config = profile.get("watch", {"enabled": False})
    validate_config(config)
    if not config["enabled"]:
        raise ValueError("Watch is disabled; configure and confirm it before use")
    return config


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _work_keys(work):
    keys = set()
    for field, normalizer in (("arxiv_id", normalize_arxiv), ("doi", normalize_doi)):
        if work.get(field):
            keys.add(field + ":" + normalizer(work[field]))
    if work.get("title") and work.get("authors"):
        for author in work["authors"]:
            keys.add("title_author:" + _norm(work["title"]) + ":" + _norm(author))
    if work.get("official_url"):
        _url(work["official_url"])
        keys.add("url:" + work["official_url"].rstrip("/"))
    if not keys:
        raise ValueError("Event work requires DOI, arXiv ID, title+authors, or official_url")
    return sorted(keys)


def _same(left, right):
    return (left["kind"] == right["kind"] and left["revision"] == right["revision"]
            and bool(set(left["work_keys"]) & set(right["work_keys"])))


def normalize_input(data, day, profile):
    config = _settings(profile)
    _date(day)
    result = deepcopy(data)
    if result.get("schema_version") != 1 or result.get("date") != day:
        raise ValueError("Watch input schema_version/date mismatch")
    if result.get("timezone") != profile["timezone"]:
        raise ValueError("Watch/report timezone mismatch")
    cutoff = _instant(result.get("generated_at"))
    if cutoff.astimezone(ZoneInfo(profile["timezone"])).date().isoformat() != day:
        raise ValueError("Watch generation date is not the local report date")
    targets = {t["id"] for t in config["targets"]}
    rows = result.get("coverage", [])
    if {r.get("target_id") for r in rows} != targets or len(rows) != len(targets):
        raise ValueError("Coverage must account for every configured target exactly once")
    for row in rows:
        if row.get("status") not in COVERAGE:
            raise ValueError("Unknown watch coverage status")
        if _instant(row.get("checked_at")) > cutoff:
            raise ValueError("Coverage check is later than generation")
        _text(row.get("detail"), "coverage.detail")
        if not row.get("sources"):
            raise ValueError("Coverage requires attempted source URLs")
        for source in row["sources"]:
            _url(source)
    merged = []
    for raw in result.get("events", []):
        e = deepcopy(raw)
        if e.get("kind") not in KINDS:
            raise ValueError("Unsupported event kind")
        for key in ("title", "revision", "summary", "delta", "relevance", "action", "limitations", "impact_reason"):
            _text(e.get(key), key)
        if type(e.get("impact")) is not int or not 0 <= e["impact"] <= 5:
            raise ValueError("Event impact is an editorial decision-impact rank 0..5")
        if not e.get("target_ids") or not set(e["target_ids"]) <= targets:
            raise ValueError("Event contains unknown watch target")
        if e.get("disposition") not in {"eligible", "baseline", "unknown_date", "exclude"}:
            raise ValueError("Event disposition must be eligible, baseline, unknown_date, or exclude")
        if e["disposition"] != "eligible":
            _text(e.get("reason"), "nonselected reason")
        found, checked = _instant(e.get("first_discovered_at")), _instant(e.get("verified_at"))
        if found > checked or checked > cutoff:
            raise ValueError("Event discovery/verification order is invalid")
        when = e.get("occurred_at")
        if when is None:
            if e["disposition"] != "unknown_date":
                raise ValueError("Undated events must remain unknown_date")
        else:
            occurred = _instant(when)
            if occurred > checked:
                raise ValueError("Event date cannot be later than verification")
            _text(e.get("date_evidence"), "date_evidence (not webpage Last-Modified)")
            if e["disposition"] == "eligible" and not cutoff-timedelta(days=7) <= occurred <= cutoff:
                raise ValueError("Eligible event is outside the last seven days; use baseline/exclude")
        sources = e.get("sources", [])
        if not sources or not any(s.get("primary") is True for s in sources):
            raise ValueError("Events require verified primary evidence")
        for source in sources:
            _url(source.get("url"))
            _text(source.get("supports"), "source.supports")
            if _instant(source.get("verified_at")) > checked:
                raise ValueError("Source verification is later than event verification")
        if e.get("in_daily_papers") and not e.get("additional_information"):
            raise ValueError("A same-day paper needs genuinely additional event information")
        e["work_keys"] = _work_keys(e.get("work", {}))
        e["target_ids"] = sorted(set(e["target_ids"]))
        matches = [old for old in merged if _same(e, old)]
        if len(matches) > 1:
            raise ValueError("Ambiguous event identity bridge; reconcile aliases first")
        if matches:
            old = matches[0]
            if old["disposition"] != e["disposition"] or old.get("occurred_at") != e.get("occurred_at"):
                raise ValueError("Duplicate sources disagree on event date/disposition")
            old["work_keys"] = sorted(set(old["work_keys"] + e["work_keys"]))
            old["target_ids"] = sorted(set(old["target_ids"] + e["target_ids"]))
            old["sources"] = list({s["url"]: s for s in old["sources"] + e["sources"]}.values())
            old["first_discovered_at"] = min(old["first_discovered_at"], e["first_discovered_at"], key=_instant)
            old["verified_at"] = max(old["verified_at"], e["verified_at"], key=_instant)
        else:
            merged.append(e)
    result["events"] = merged
    weekly = result.get("weekly")
    sunday = cutoff.astimezone(ZoneInfo(profile["timezone"])).weekday() == 6
    if weekly is not None and (not sunday or not config["weekly"]["enabled"]):
        raise ValueError("Weekly route review is allowed only on enabled local Sundays")
    if sunday and config["weekly"]["enabled"]:
        if not isinstance(weekly, dict):
            raise ValueError("Sunday needs weekly review or an explicit insufficient_evidence reason")
        if weekly.get("status") not in {"reviewed", "insufficient_evidence"}:
            raise ValueError("Invalid weekly status")
        start = _instant(weekly.get("window_start")); end = _instant(weekly.get("window_end"))
        if end != cutoff or start != cutoff-timedelta(days=7):
            raise ValueError("Weekly window must be the seven days ending at generation")
        changes = weekly.get("changes", []); questions = weekly.get("questions", [])
        if len(changes) > 3 or len(questions) > 2:
            raise ValueError("Weekly review limits: three changes and two questions")
        if weekly["status"] == "reviewed" and (not changes or not questions):
            raise ValueError("Reviewed routes require evidence and 1–2 testable questions")
        if weekly["status"] == "insufficient_evidence":
            _text(weekly.get("reason"), "weekly.reason")
        for change in changes:
            for key in ("before", "addition", "remaining", "relevance"):
                _text(change.get(key), "weekly." + key)
            if not change.get("sources"):
                raise ValueError("Weekly change requires original sources")
            for source in change["sources"]:
                _url(source["url"])
                if not start <= _instant(source["occurred_at"]) <= end:
                    raise ValueError("Weekly new evidence must fall in the seven-day window")
                _text(source.get("supports"), "weekly source.supports")
        for question in questions:
            _text(question, "weekly question")
    return result


def _registry(base):
    value = _json(base / "registry.json", {"schema_version": 1, "events": []})
    if value.get("schema_version") != 1 or not isinstance(value.get("events"), list):
        raise ValueError("Unrecognized watch registry")
    return value


def _recover(base):
    path = base / ".work/publication.json"; journal = _json(path)
    if journal is None:
        return
    _date(journal["date"])
    if not re.fullmatch(r"[0-9a-f]{32}", journal["transaction"]):
        raise ValueError("Invalid watch transaction")
    target = base / journal["date"]
    stage = base / ".work/transactions" / journal["transaction"]
    if not target.exists():
        if not stage.exists():
            raise ValueError("Missing staged watch transaction")
        os.replace(stage, target)
    if _json(target / "updates.json", {}).get("fingerprint") != journal["fingerprint"]:
        raise ValueError("Watch recovery refuses a foreign date folder")
    _atomic(base / "registry.json", journal["registry"])
    path.unlink()


@contextmanager
def _lock(root):
    base = Path(root).resolve() / "watch"
    base.mkdir(parents=True, exist_ok=True)
    path = base / ".watch.lock"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("Watch is locked; inspect the process before removing a stale lock") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "created_at": _utc()}, f)
        _recover(base)
        yield base
    finally:
        path.unlink(missing_ok=True)


def _select(data, registry, profile):
    decisions = []; eligible = []
    for event in data["events"]:
        matches = [e for e in registry["events"] if _same(event, e)]
        if len(matches) > 1:
            raise ValueError("Ambiguous registry event identity; merge explicitly")
        old = matches[0] if matches else None
        reason = event.get("reason", "")
        if old and (old.get("displayed_dates") or old.get("disposition") == "baseline"):
            reason = "Previously displayed event" if old.get("displayed_dates") else "Already known baseline event"
        elif event["disposition"] == "eligible":
            eligible.append(event)
        else:
            reason = reason or event["disposition"]
        if reason:
            decisions.append({"title": event["title"], "revision": event["revision"], "reason": reason})
    eligible.sort(key=lambda e: (-e["impact"], -_instant(e["occurred_at"]).timestamp(), e["title"]))
    limit = profile["watch"]["daily_limit"]
    for e in eligible[limit:]:
        decisions.append({"title": e["title"], "revision": e["revision"], "reason": "Daily impact limit; retain candidate"})
    return eligible[:limit], decisions


def prepare(root, day, data, profile):
    data = normalize_input(data, day, profile)
    with _lock(root) as base:
        selected, decisions = _select(data, _registry(base), profile)
        snapshot = dict(data, stage="prepared", selected=selected, decisions=decisions)
        folder = base / ".work/prepared" / day
        _atomic(folder / "snapshot.json", snapshot)
        _atomic(folder / "00_prepared_updates.md", render_updates(snapshot, profile["language"]), text=True)
        return {"status": "prepared", "displayed": 0, "candidates": len(data["events"]), "snapshot": str(folder / "snapshot.json")}


def publish(root, day, data, profile):
    from .config import is_confirmed
    if not is_confirmed(profile):
        raise ValueError("Watch profile needs confirmation of its current standards")
    data = normalize_input(data, day, profile)
    for field in ("stage", "selected", "decisions", "fingerprint", "input_fingerprint"):
        data.pop(field, None)
    if any(e.get("example_only") for e in data["events"]):
        raise ValueError("Synthetic example_only events cannot be published")
    fingerprint = _digest({"input": data, "watch": profile["watch"], "language": profile["language"]})
    with _lock(root) as base:
        target = base / day
        if target.exists():
            existing = _json(target / "updates.json", {})
            if existing.get("input_fingerprint") == fingerprint:
                return {"status": "unchanged", "notify": False, "count": len(existing["selected"]), "snapshot": str(target / "updates.json")}
            raise ValueError("Watch date already exists with different content; refusing overwrite")
        registry = _registry(base)
        selected, decisions = _select(data, registry, profile)
        selected_ids = set()
        for e in data["events"]:
            old = next((r for r in registry["events"] if _same(e, r)), None)
            dates = list(old.get("displayed_dates", [])) if old else []
            ident = old["id"] if old else _digest([e["work_keys"], e["kind"], e["revision"]])
            if e in selected:
                dates.append(day); selected_ids.add(ident)
            entry = dict(e, id=ident, displayed_dates=dates)
            if old:
                entry["work_keys"] = sorted(set(old["work_keys"] + entry["work_keys"]))
                entry["target_ids"] = sorted(set(old["target_ids"] + entry["target_ids"]))
                source_history = {s["url"]: s for s in old["sources"]}
                for source in entry["sources"]:
                    previous = source_history.get(source["url"])
                    if previous is None or _instant(source["verified_at"]) >= _instant(previous["verified_at"]):
                        source_history[source["url"]] = source
                entry["sources"] = list(source_history.values())
                entry["verified_at"] = max(old["verified_at"], entry["verified_at"], key=_instant)
                entry["first_discovered_at"] = min(old["first_discovered_at"], entry["first_discovered_at"], key=_instant)
                if old["disposition"] == "baseline":
                    entry["disposition"] = "baseline"
                registry["events"][registry["events"].index(old)] = entry
            else:
                registry["events"].append(entry)
        snapshot = dict(data, stage="published", selected=[e for e in registry["events"] if e["id"] in selected_ids], decisions=decisions, input_fingerprint=fingerprint)
        # Preserve editorial impact order after registry insertion order.
        snapshot["selected"].sort(key=lambda e: (-e["impact"], -_instant(e["occurred_at"]).timestamp(), e["title"]))
        snapshot["fingerprint"] = _digest(snapshot)
        transaction = uuid.uuid4().hex; stage = base / ".work/transactions" / transaction
        _atomic(stage / "updates.json", snapshot)
        _atomic(stage / "00_updates.md", render_updates(snapshot, profile["language"]), text=True)
        _atomic(base / ".work/publication.json", dict(date=day, transaction=transaction, fingerprint=snapshot["fingerprint"], registry=registry))
        _recover(base)
        return {"status": "published", "notify": True, "count": len(selected), "snapshot": str(target / "updates.json"), "overview": str(target / "00_updates.md")}


def load_snapshot(path, day, profile, *, published=True):
    snapshot = _json(Path(path))
    if snapshot is None:
        raise ValueError("Missing watch snapshot")
    normalize_input(snapshot, day, profile)
    if published:
        if snapshot.get("stage") != "published":
            raise ValueError("Paper publication requires a published watch snapshot")
        payload = {k: v for k, v in snapshot.items() if k != "fingerprint"}
        if _digest(payload) != snapshot.get("fingerprint"):
            raise ValueError("Watch snapshot integrity mismatch")
    elif snapshot.get("stage") not in {"prepared", "published"}:
        raise ValueError("Expected a prepared/published watch snapshot")
    return snapshot


def render_updates(snapshot, language="zh-CN"):
    zh = language == "zh-CN"
    lines = ["## 重点团队动态" if zh else "## Researcher and team updates", "",
             ("预备资料，尚未正式展示。" if zh else "Prepared only; no display history consumed.") if snapshot.get("stage") == "prepared" else "",
             ("核验截止：" if zh else "Verified through: ") + snapshot["generated_at"], ""]
    events = snapshot.get("selected", [])
    if not events:
        statuses = {r["status"] for r in snapshot["coverage"]}
        if statuses & {"failed", "partial"}:
            message = "未选出可核验动态；部分来源未完成，不能据此判断没有更新。" if zh else "No verified updates selected; incomplete sources prevent a no-update conclusion."
        elif "baseline" in statuses:
            message = "首次建立跟踪基线；既有成果不作为今日新动态。" if zh else "Initial baseline recorded; existing work is not today's news."
        else:
            message = "已检查的来源中没有达到入选标准的新动态。" if zh else "No qualifying new event found in the checked sources."
        lines += [message, ""]
    for i, e in enumerate(events, 1):
        lines += [f"### {i}. {e['title']}", "", e["summary"], "",
                  ("对象：" if zh else "Targets: ") + ", ".join(e["target_ids"]),
                  ("实际发布：" if zh else "Occurred: ") + str(e["occurred_at"]),
                  ("首次发现：" if zh else "First discovered: ") + e["first_discovered_at"],
                  ("核验：" if zh else "Verified: ") + e["verified_at"], "",
                  ("新增：" if zh else "Change: ") + e["delta"],
                  ("课题联系：" if zh else "Research use: ") + e["relevance"],
                  ("建议动作：" if zh else "Next action: ") + e["action"],
                  ("证据边界：" if zh else "Evidence limits: ") + e["limitations"], ""]
        if e.get("additional_information"):
            lines += [e["additional_information"], ""]
        if e.get("paper_ref"):
            _url(e["paper_ref"])
            lines += [f"[{'对应论文' if zh else 'Related paper'}]({e['paper_ref']})", ""]
        lines += [" · ".join(f"[{s['supports']}]({s['url']})" for s in e["sources"]), ""]
    for row in snapshot["coverage"]:
        if row["status"] != "checked":
            lines += [f"- {row['target_id']} ({row['status']}): {row['detail']}"]
    weekly = snapshot.get("weekly")
    if weekly:
        lines += ["", "## 周日研究路线梳理" if zh else "## Sunday research routes", "", weekly["window_start"] + " → " + weekly["window_end"], ""]
        if weekly["status"] == "insufficient_evidence":
            lines += [weekly["reason"], ""]
        for change in weekly.get("changes", []):
            lines += [f"- {change['before']} → {change['addition']} → {change['remaining']}", change["relevance"],
                      " · ".join(f"[{s['supports']}]({s['url']})" for s in change["sources"]), ""]
        for question in weekly.get("questions", []):
            lines += ["- " + question]
    return "\n".join(lines).strip() + "\n"


def validate(root, day, profile):
    _settings(profile)
    base = Path(root).resolve() / "watch"; errors = []
    if (base / ".work/publication.json").exists():
        errors.append("Pending watch publication; resume the same publish input")
    registry = _registry(base); seen = []
    for event in registry["events"]:
        if len(event.get("displayed_dates", [])) > 1:
            errors.append("Repeated event display: " + event["id"])
        if any(_same(event, other) for other in seen):
            errors.append("Duplicate event identity: " + event["id"])
        seen.append(event)
    folders = [base / day] if day else sorted(p.parent for p in base.glob("????-??-??/updates.json"))
    for folder in folders:
        try:
            snapshot = load_snapshot(folder / "updates.json", folder.name, profile)
            if len(snapshot["selected"]) > profile["watch"]["daily_limit"]:
                errors.append("Watch display limit exceeded")
            for e in snapshot["selected"]:
                r = next((r for r in registry["events"] if r["id"] == e["id"]), None)
                if not r or folder.name not in r["displayed_dates"]:
                    errors.append("Watch snapshot/history mismatch")
            if (folder / "00_updates.md").read_text(encoding="utf-8") != render_updates(snapshot, profile["language"]):
                errors.append("Watch rendered content changed")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
    return {"ok": not errors, "errors": errors, "events_registered": len(registry["events"]), "paper_registry_modified": False, "external_urls_checked": False}
