"""Bounded HTTP access. Errors deliberately omit URLs, queries and credentials."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.client import IncompleteRead
import os
import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 64 * 1024 * 1024
ARXIV_INTERVAL = 3.2
_arxiv_lock = threading.Lock()
_last_arxiv_request: float | None = None


class FetchError(RuntimeError):
    """A safe-to-display transport failure, without server body or request query."""


def validate_url(url: str):
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or any(ord(c) < 32 for c in url)):
            raise ValueError
        parsed.port
    except (ValueError, TypeError):
        raise FetchError("URL must be HTTP(S), with a host and without embedded credentials.") from None
    return parsed


def public_url(url: str) -> str:
    """Safe provenance for downloads: never persist a signed query or fragment."""
    parsed = validate_url(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = validate_url(newurl)
        original = validate_url(req.full_url)
        if original.scheme == "https" and target.scheme != "https":
            raise FetchError("Refused an HTTPS-to-HTTP redirect.")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and (target.hostname, target.port) != (original.hostname, original.port):
            redirected.remove_header("Authorization")
            redirected.remove_header("Cookie")
        return redirected


def _pace_arxiv(host: str) -> None:
    global _last_arxiv_request
    if host != "arxiv.org" and not host.endswith(".arxiv.org"):
        return
    with _arxiv_lock:
        now = time.monotonic()
        if _last_arxiv_request is not None:
            delay = ARXIV_INTERVAL - (now - _last_arxiv_request)
            if delay > 0:
                time.sleep(delay)
        _last_arxiv_request = time.monotonic()


def _retry_delay(value: str | None, attempt: int) -> float:
    delay = min(2 ** attempt, 60)
    if value:
        try:
            delay = float(value)
        except ValueError:
            try:
                then = parsedate_to_datetime(value)
                if then.tzinfo is None:
                    then = then.replace(tzinfo=timezone.utc)
                delay = (then - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                pass
    return max(0.0, min(delay, 60.0))


def fetch(url: str, timeout: float = 30, retries: int = 2) -> bytes:
    """Fetch at most 64 MiB, retrying transient failures at most ``retries`` times.

    arXiv requests are paced within this process. Callers running independent
    processes must serialize them too. Authentication is read only from the
    OPENALEX_API_KEY environment variable, for the official HTTPS host only.
    """
    parsed = validate_url(url)
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 5:
        raise ValueError("retries must be an integer between 0 and 5")
    if not 0 < timeout <= 120:
        raise ValueError("timeout must be between 0 and 120 seconds")
    headers = {"User-Agent": "paper-research-daily/0.1 (+portable literature workflow)",
               "Accept-Encoding": "identity"}
    api_key = os.environ.get("OPENALEX_API_KEY")
    if parsed.hostname == "api.openalex.org" and parsed.scheme == "https" and api_key:
        if any(ord(c) < 32 or ord(c) > 126 for c in api_key):
            raise FetchError("OPENALEX_API_KEY contains invalid characters.")
        headers["Authorization"] = "Bearer " + api_key
    opener = build_opener(_SafeRedirect())
    for attempt in range(retries + 1):
        _pace_arxiv(parsed.hostname or "")
        try:
            with opener.open(Request(url, headers=headers), timeout=timeout) as response:
                validate_url(response.geturl())
                length = response.headers.get("Content-Length")
                if length:
                    try:
                        if int(length) > MAX_BYTES:
                            raise FetchError("Response exceeds the 64 MiB download limit.")
                    except ValueError:
                        raise FetchError("Invalid Content-Length response header.") from None
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise FetchError("Response exceeds the 64 MiB download limit.")
                return body
        except HTTPError as error:
            status = error.code
            retry_after = error.headers.get("Retry-After") if error.headers else None
            error.close()
            if status in {401, 403}:
                hint = " Check OPENALEX_API_KEY in the environment." if parsed.hostname == "api.openalex.org" else ""
                raise FetchError(f"HTTP {status}: access was denied.{hint}") from None
            if status not in {408, 429, 500, 502, 503, 504} or attempt == retries:
                raise FetchError(f"HTTP {status}: retrieval failed after {attempt + 1} attempt(s).") from None
            time.sleep(_retry_delay(retry_after, attempt))
        except (URLError, TimeoutError, socket.timeout, ConnectionError, OSError, IncompleteRead):
            if attempt == retries:
                raise FetchError(f"Network or timeout failure after {attempt + 1} attempt(s).") from None
            time.sleep(_retry_delay(None, attempt))
    raise FetchError("Retrieval failed.")  # Defensive: loop always returns or raises.
