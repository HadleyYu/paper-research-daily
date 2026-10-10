"""Validated, portable user profiles. No machine-specific defaults or secrets."""
from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEIGHTS = {"relevance": 35, "evidence": 25, "inspiration": 20,
           "novelty": 10, "representative": 5, "reproducibility": 5}

DEFAULT = {
    "schema_version": 1,
    "project": {"name": "My research", "research_question": "", "topics": [],
                "exclude": [], "level": "graduate"},
    "output_root": "./literature",
    "language": "zh-CN",
    "timezone": "Asia/Shanghai",
    "selection": {"daily_count": 8, "new_count": 4, "published_count": 4,
                  "weekend_mode": "combined", "lookback_hours": 72,
                  "max_lookback_days": 7, "min_score": 75, "min_relevance": 25,
                  "allow_abstract_only": False, "pool_limit": 100,
                  "reevaluate_days": 14},
    "scoring": WEIGHTS,
    "sources": {"new": ["arxiv"], "published": ["crossref", "openalex", "official"]},
    "analysis": {"depth": "dense", "chinese_character_range": [1200, 1800],
                 "distinguish_author_and_analysis": True},
    "schedule": {"enabled": False, "timezone": "America/New_York",
                 "prepare_time": "19:00", "final_time": "20:05",
                 "deadline": "09:30"},
    "confirmation": {"status": "draft", "confirmed_at": None},
}


def new_profile(topic: str, root: str, *, language="zh-CN", timezone="Asia/Shanghai",
                count=8, new_count=None) -> dict:
    profile = deepcopy(DEFAULT)
    profile["project"].update(name=topic.strip(), research_question=topic.strip(),
                              topics=[topic.strip()])
    profile.update(output_root=root, language=language, timezone=timezone)
    new_count = count // 2 if new_count is None else new_count
    profile["selection"].update(daily_count=count, new_count=new_count,
                                published_count=count-new_count)
    validate_profile(profile)
    return profile


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")


def validate_profile(profile: dict) -> None:
    if not isinstance(profile, dict) or profile.get("schema_version") != 1:
        raise ValueError("Expected profile schema_version: 1")
    for key in DEFAULT:
        if key not in profile:
            raise ValueError(f"Missing profile field: {key}")
    project = profile["project"]
    if not isinstance(project, dict) or not str(project.get("research_question", "")).strip():
        raise ValueError("project.research_question is required")
    for key in ("topics", "exclude"):
        if not isinstance(project.get(key), list) or not all(isinstance(x, str) for x in project[key]):
            raise ValueError(f"project.{key} must be a list of strings")
    if not isinstance(profile["output_root"], str) or not profile["output_root"].strip():
        raise ValueError("output_root must be a nonempty path")
    if profile["language"] not in {"zh-CN", "en"}:
        raise ValueError("v0.1 report languages: zh-CN, en")
    try:
        ZoneInfo(profile["timezone"])
        ZoneInfo(profile["schedule"]["timezone"])
    except (ZoneInfoNotFoundError, TypeError) as exc:
        raise ValueError("Invalid IANA timezone; install tzdata on Windows") from exc
    selection = profile["selection"]
    if not isinstance(selection, dict):
        raise ValueError("selection must be an object")
    for key in DEFAULT["selection"]:
        if key not in selection:
            raise ValueError(f"Missing selection.{key}")
    for key in ("daily_count", "lookback_hours", "max_lookback_days", "pool_limit", "reevaluate_days"):
        _integer(selection[key], f"selection.{key}", 1)
    for key in ("new_count", "published_count", "min_score", "min_relevance"):
        _integer(selection[key], f"selection.{key}")
    if selection["new_count"] + selection["published_count"] != selection["daily_count"]:
        raise ValueError("new_count + published_count must equal daily_count")
    if selection["weekend_mode"] not in {"combined", "same_as_weekday"}:
        raise ValueError("weekend_mode must be combined or same_as_weekday")
    if type(selection["allow_abstract_only"]) is not bool:
        raise ValueError("allow_abstract_only must be true or false")
    if selection["lookback_hours"] > selection["max_lookback_days"] * 24:
        raise ValueError("lookback_hours cannot exceed max_lookback_days")
    weights = profile["scoring"]
    if not isinstance(weights, dict) or set(weights) != set(WEIGHTS):
        raise ValueError("scoring must contain exactly the six documented dimensions")
    for key, value in weights.items():
        _integer(value, f"scoring.{key}")
    if sum(weights.values()) != 100:
        raise ValueError("Scoring weights must sum to 100")
    if selection["min_score"] > 100 or selection["min_relevance"] > weights["relevance"]:
        raise ValueError("Selection thresholds exceed scoring weights")
    for group in ("new", "published"):
        values = profile["sources"].get(group)
        if not isinstance(values, list) or not values or not all(isinstance(x, str) and x for x in values):
            raise ValueError(f"sources.{group} must be a nonempty list")
    schedule = profile["schedule"]
    if type(schedule.get("enabled")) is not bool:
        raise ValueError("schedule.enabled must be true or false")
    for key in ("prepare_time", "final_time", "deadline"):
        try:
            time.fromisoformat(schedule[key])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"Invalid schedule.{key}; use HH:MM") from exc
    if profile["confirmation"].get("status") not in {"draft", "confirmed"}:
        raise ValueError("confirmation.status must be draft or confirmed")
    # These are configuration fields, never credential containers.
    forbidden = {"password", "cookie", "cookies", "token", "api_key", "secret", "credential"}
    def check_keys(obj):
        if isinstance(obj, dict):
            if forbidden & {str(k).casefold() for k in obj}:
                raise ValueError("Credentials belong in the runtime, never profile JSON")
            for value in obj.values():
                check_keys(value)
        elif isinstance(obj, list):
            for value in obj:
                check_keys(value)
    check_keys(profile)


def load_profile(path: str | Path) -> dict:
    profile = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    validate_profile(profile)
    return profile


def profile_fingerprint(profile: dict) -> str:
    standards = {key: value for key, value in profile.items() if key != "confirmation"}
    return hashlib.sha256(json.dumps(standards, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def is_confirmed(profile: dict) -> bool:
    confirmation = profile["confirmation"]
    return (confirmation.get("status") == "confirmed" and
            confirmation.get("profile_sha256") == profile_fingerprint(profile))


def library_root(profile: dict, profile_path: str | Path) -> Path:
    path = Path(profile["output_root"]).expanduser()
    return path.resolve() if path.is_absolute() else (Path(profile_path).resolve().parent / path).resolve()


def report_date(profile: dict, instant: datetime | None = None) -> str:
    if instant is not None and instant.tzinfo is None:
        raise ValueError("report_date requires an aware datetime")
    return (instant or datetime.now(ZoneInfo("UTC"))).astimezone(ZoneInfo(profile["timezone"])).date().isoformat()


def write_profile(path: str | Path, profile: dict, *, overwrite=False) -> None:
    validate_profile(profile)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", encoding="utf-8", newline="\n") as stream:
        json.dump(profile, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
