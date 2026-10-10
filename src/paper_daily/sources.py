"""Official discovery adapters; returned records are candidates, not endorsements.

API contracts checked against arXiv's API/Atom specifications, Crossref REST
documentation and OpenAlex authentication documentation. Submission, update,
announcement and feed-generation timestamps deliberately remain distinct.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from . import network

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
ARXIV_ID = re.compile(r"(?P<base>(?:\d{4}\.\d{4,5}|[a-z][a-z.\-]+/\d{7}))(?P<version>v\d+)?$", re.I)


class SourceError(RuntimeError):
    """Invalid provider response; not equivalent to an empty search result."""


def _limit(value: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"limit must be an integer between 1 and {maximum}")
    return value


def _text(value) -> str:
    return " ".join(str(value or "").split())


def _provenance(url: str, kind: str) -> list[dict]:
    return [{"url": url, "kind": kind, "role": "discovery", "retrieved_at": datetime.now(timezone.utc).isoformat()}]


def _arxiv_identity(raw: str) -> tuple[str, str | None]:
    found = ARXIV_ID.search(raw.strip())
    if not found:
        raise SourceError("arXiv returned an invalid article identifier or an API error entry.")
    return found.group("base"), found.group("version")


def _parse_atom(data: bytes, source_url: str, *, rss: bool = False) -> list[dict]:
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise SourceError("Unexpected XML declarations in arXiv response.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise SourceError("arXiv returned malformed XML; search coverage is unknown.") from None
    if root.tag != ATOM + "feed":
        raise SourceError("arXiv response is not an Atom feed.")
    output = []
    for entry in root.findall(ATOM + "entry"):
        base, version = _arxiv_identity(entry.findtext(ATOM + "id", ""))
        title = _text(entry.findtext(ATOM + "title"))
        if not title:
            raise SourceError("arXiv record is missing its title.")
        authors = [_text(a.findtext(ATOM + "name")) for a in entry.findall(ATOM + "author")]
        if not authors and rss:
            authors = [_text(a) for a in entry.findtext(DC + "creator", "").split(",") if _text(a)]
        published = entry.findtext(ATOM + "published")
        updated = entry.findtext(ATOM + "updated")
        announce_type = entry.findtext(ARXIV + "announce_type") if rss else None
        abstract = _text(entry.findtext(ATOM + "summary"))
        if rss and "Abstract:" in abstract:
            abstract = abstract.split("Abstract:", 1)[1].strip()
        identifier = base + (version or "")
        output.append({
            "title": title, "authors": authors, "arxiv_id": base, "version": version,
            "doi": entry.findtext(ARXIV + "doi") or entry.findtext(ARXIV + "DOI"),
            "official_url": f"https://arxiv.org/abs/{identifier}",
            "pdf_url": f"https://arxiv.org/pdf/{identifier}", "abstract": abstract,
            "first_submitted": None if rss else published,
            "updated": None if rss else updated,
            "first_announced": published if rss and announce_type == "new" else None,
            "announcement_date": published if rss else None,
            "announce_type": announce_type,
            "feed_generated_at": updated if rss else None,
            "discovery_source": "arxiv", "discovery_method": "atom_feed" if rss else "api",
            "publication_verified": False,
            "venue": entry.findtext(ARXIV + "journal_ref") or entry.findtext(ARXIV + "journal_reference"),
            "sources": _provenance(source_url, "arxiv_atom_feed" if rss else "arxiv_api"),
            "date_note": ("Feed timestamps are not submission timestamps; only announce_type=new establishes first announcement."
                          if rss else "API published is first-version submission, not first announcement; updated is this version's submission."),
        })
    return output


def arxiv_search(query: str, limit: int = 20, sort_by: str = "submittedDate") -> list[dict]:
    """Search only the official API. Failures raise; no hidden web-search fallback."""
    _limit(limit, 2000)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must not be empty")
    if sort_by not in {"submittedDate", "lastUpdatedDate", "relevance"}:
        raise ValueError("Unsupported arXiv sort order")
    url = "https://export.arxiv.org/api/query?" + urlencode({
        "search_query": query, "start": 0, "max_results": limit,
        "sortBy": sort_by, "sortOrder": "descending"})
    return _parse_atom(network.fetch(url), url)[:limit]


class _RecentHTML(HTMLParser):
    """Extract title/author records, preserving listing dates as listing dates."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records: list[dict] = []
        self.current: dict | None = None
        self.stack: list[tuple[str, str]] = []
        self.heading: list[str] = []
        self.listed_date: str | None = None
        self.article_list = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        role = ""
        classes = attrs.get("class", "").split()
        if tag == "dl" and attrs.get("id") == "articles":
            self.article_list = True
        if tag == "h3":
            self.heading = []
            role = "heading"
        if tag == "dt":
            self.current = {"title_parts": [], "authors": [], "listed_date": self.listed_date}
        if tag == "a" and self.current is not None:
            href = attrs.get("href", "")
            if href.startswith("/abs/"):
                self.current["arxiv_raw"] = href.removeprefix("/abs/")
            if any(r == "authors" for _, r in self.stack):
                role = "author"
                self.current["authors"].append("")
        if "list-title" in classes:
            role = "title"
        if "list-authors" in classes:
            role = "authors"
        if tag not in {"br", "hr", "meta", "img", "input", "link"}:
            self.stack.append((tag, role))

    def handle_data(self, data):
        roles = {r for _, r in self.stack}
        if "heading" in roles:
            self.heading.append(data)
        if self.current is not None:
            if "title" in roles:
                self.current["title_parts"].append(data)
            if "author" in roles and self.current["authors"]:
                self.current["authors"][-1] += data

    def handle_endtag(self, tag):
        if tag == "h3":
            text = _text(" ".join(self.heading))
            match = re.search(r"\b(\d{1,2}) ([A-Za-z]{3}) (\d{4})\b", text)
            if match:
                months = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
                day, month, year = match.groups()
                if month in months:
                    self.listed_date = f"{year}-{months[month]:02d}-{int(day):02d}"
        if tag == "dd" and self.current is not None:
            if "arxiv_raw" not in self.current:
                raise SourceError("arXiv listing entry is missing its identifier.")
            self.records.append(self.current)
            self.current = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def _parse_recent_html(data: bytes, url: str) -> list[dict]:
    parser = _RecentHTML()
    try:
        parser.feed(data.decode("utf-8"))
    except UnicodeDecodeError:
        raise SourceError("arXiv recent listing is not valid UTF-8.") from None
    if not parser.article_list:
        raise SourceError("arXiv recent listing structure was not recognized; coverage is unknown.")
    result = []
    for record in parser.records:
        base, version = _arxiv_identity(record["arxiv_raw"])
        title = _text(" ".join(record["title_parts"]))
        title = re.sub(r"^Title:\s*", "", title)
        if not title:
            raise SourceError("arXiv listing entry is missing its title.")
        identifier = base + (version or "")
        result.append({"title": title, "authors": [_text(a) for a in record["authors"]],
                       "arxiv_id": base, "version": version, "doi": None,
                       "official_url": f"https://arxiv.org/abs/{identifier}",
                       "pdf_url": f"https://arxiv.org/pdf/{identifier}",
                       "first_submitted": None, "updated": None, "first_announced": None,
                       "listed_date": record["listed_date"], "abstract": None,
                       "discovery_source": "arxiv", "discovery_method": "recent_html",
                       "publication_verified": False,
                       "date_note": "Title/author discovery only. Listing dates can include replacements/cross-lists; verify the abstract page before claiming freshness.",
                       "sources": _provenance(url, "arxiv_recent_list")})
    return result


def arxiv_recent(category: str, limit: int = 100) -> list[dict]:
    """Current Atom announcements, with official recent-list fallback.

    The limit caps this response, not a claim of exhaustive category coverage.
    An empty feed can occur on a non-announcement day, so recent HTML is checked.
    """
    _limit(limit, 2000)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,40}", category):
        raise ValueError("Use one arXiv category, for example cs.RO or math.OC")
    atom_url = f"https://rss.arxiv.org/atom/{category}"
    fallback_reason = "Atom feed contained no entries; checked the recent listing."
    try:
        records = _parse_atom(network.fetch(atom_url), atom_url, rss=True)
        if records:
            return records[:limit]
    except (network.FetchError, SourceError) as error:
        fallback_reason = "Atom feed unavailable: " + str(error)
    # The browser listing rejects very small/nonstandard page sizes. Keep the
    # public limit while requesting the next supported-sized listing page.
    page_size = next(size for size in (25, 50, 100, 250, 500, 1000, 2000) if size >= limit)
    html_url = f"https://arxiv.org/list/{category}/recent?show={page_size}"
    records = _parse_recent_html(network.fetch(html_url), html_url)[:limit]
    for record in records:
        record["discovery_warning"] = fallback_reason
    return records


def _json_response(data: bytes, provider: str) -> dict:
    try:
        result = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SourceError(f"{provider} returned malformed JSON; coverage is unknown.") from None
    if not isinstance(result, dict):
        raise SourceError(f"{provider} returned an unexpected response structure.")
    return result


def _object_list(value, provider: str, field: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(entry, dict) for entry in value):
        raise SourceError(f"{provider} record has an invalid {field} field.")
    return value


def _object(value, provider: str, field: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SourceError(f"{provider} record has an invalid {field} field.")
    return value


def crossref_search(query: str, limit: int = 10) -> list[dict]:
    _limit(limit, 1000)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must not be empty")
    url = "https://api.crossref.org/works?" + urlencode({"query.bibliographic": query, "rows": limit})
    data = _json_response(network.fetch(url), "Crossref")
    items = data.get("message", {}).get("items") if isinstance(data.get("message"), dict) else None
    if data.get("status") != "ok" or not isinstance(items, list):
        raise SourceError("Crossref returned an invalid works response.")
    records = []
    for item in items[:limit]:
        if not isinstance(item, dict) or not isinstance(item.get("title"), list) or not item["title"] or not _text(item["title"][0]):
            raise SourceError("Crossref record is missing a title.")
        authors = [_text(" ".join(filter(None, [_text(a.get("given")), _text(a.get("family"))])))
                   or _text(a.get("name")) for a in _object_list(item.get("author"), "Crossref", "author")]
        venues = item.get("container-title") or []
        if not isinstance(venues, list):
            raise SourceError("Crossref record has an invalid container-title field.")
        doi = _text(item.get("DOI")) or None
        records.append({"title": _text(item["title"][0]), "authors": authors, "doi": doi,
                        "arxiv_id": None, "official_url": f"https://doi.org/{doi}" if doi else item.get("URL"),
                        "pdf_url": None, "venue": "; ".join(_text(v) for v in venues),
                        "publication_type": item.get("type"), "publication_date_parts": _object(item.get("published"), "Crossref", "published").get("date-parts"),
                        "publication_verified": False, "discovery_source": "crossref",
                        "verification_note": "Metadata candidate only; verify publication and version against publisher/proceedings.",
                        "sources": _provenance(url, "crossref_metadata")})
    return records


def openalex_search(query: str, limit: int = 10) -> list[dict]:
    _limit(limit, 200)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must not be empty")
    url = "https://api.openalex.org/works?" + urlencode({"search": query, "per-page": limit})
    data = _json_response(network.fetch(url), "OpenAlex")
    items = data.get("results")
    if not isinstance(items, list):
        raise SourceError("OpenAlex returned an invalid works response.")
    records = []
    for item in items[:limit]:
        if not isinstance(item, dict) or not _text(item.get("display_name") or item.get("title")):
            raise SourceError("OpenAlex record is missing a title.")
        location = _object(item.get("primary_location"), "OpenAlex", "primary_location")
        source = _object(location.get("source"), "OpenAlex", "source")
        doi = item.get("doi")
        if doi:
            if not isinstance(doi, str):
                raise SourceError("OpenAlex record has an invalid DOI field.")
            doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
        records.append({"title": _text(item.get("display_name") or item.get("title")),
                        "authors": [_text(_object(a.get("author"), "OpenAlex", "author").get("display_name")) for a in _object_list(item.get("authorships"), "OpenAlex", "authorships")],
                        "doi": doi, "arxiv_id": None, "openalex_id": item.get("id"),
                        "official_url": location.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else item.get("id")),
                        "pdf_url": location.get("pdf_url"), "venue": source.get("display_name"),
                        "publication_date": item.get("publication_date"), "publication_verified": False,
                        "discovery_source": "openalex",
                        "verification_note": "Metadata candidate only; verify publication and version against publisher/proceedings.",
                        "sources": _provenance(url, "openalex_metadata")})
    return records


def download_pdf(url: str, destination: Path) -> dict:
    """Download an accessible PDF; never bypass access controls or replace a file.

    A temporary file is fsynced and hard-linked into place (atomic, no clobber).
    Filesystems without hard-link support return an explicit error instead of
    falling back to a potentially destructive overwrite.
    """
    from pypdf import PdfReader
    destination = Path(destination)
    if destination.suffix.lower() != ".pdf":
        raise ValueError("PDF destination must use the .pdf extension")
    safe_url = network.public_url(url)
    data = network.fetch(url)
    if not data.startswith(b"%PDF-"):
        raise SourceError("Response is not a PDF (possibly a login or HTML error page).")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise SourceError("Encrypted PDF requires authorized manual handling.")
        pages = len(reader.pages)
        if pages < 1:
            raise SourceError("PDF contains no pages.")
        for page in reader.pages:
            _ = page.mediabox
    except SourceError:
        raise
    except Exception:
        raise SourceError("PDF could not be parsed; no file was saved.") from None
    digest = hashlib.sha256(data).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    status = "downloaded"
    if destination.exists():
        if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise FileExistsError("Destination already exists with different content; choose a new version filename.")
        status = "already_present"
    else:
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".paper-download-", suffix=".tmp", delete=False) as stream:
                temp_name = stream.name
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temp_name, destination)
            except FileExistsError:
                if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                    raise FileExistsError("Destination appeared with different content; nothing was overwritten.") from None
                status = "already_present"
        finally:
            if temp_name is not None:
                Path(temp_name).unlink(missing_ok=True)
    return {"path": str(destination), "sha256": digest, "pages": pages,
            "bytes": len(data), "source_url": safe_url, "status": status}
