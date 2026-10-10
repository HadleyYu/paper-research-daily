"""Offline contracts for official-source discovery and bounded downloads."""
from email.message import Message
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from pypdf import PdfWriter

from paper_daily import network, sources


ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:arxiv="http://arxiv.org/schemas/atom"><entry>
 <id>http://arxiv.org/abs/2501.12345v2</id><title>A control study</title>
 <author><name>A Researcher</name></author><summary>A short abstract.</summary>
 <published>2025-01-10T10:00:00Z</published><updated>2025-02-10T12:00:00Z</updated>
 </entry></feed>'''
RSS = b'''<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
 <entry><id>oai:arXiv.org:2501.12345v2</id><title>A control study</title>
 <dc:creator>A Researcher, B Researcher</dc:creator>
 <summary>arXiv:2501.12345v2 Announce Type: replace Abstract: A short abstract.</summary>
 <published>2025-02-11T00:00:00-05:00</published><updated>2025-02-11T05:01:00Z</updated>
 <arxiv:announce_type>replace</arxiv:announce_type></entry></feed>'''
HTML = b'''<html><dl id="articles"><h3>Fri, 10 Jan 2025 (2 entries)</h3>
 <dt><a href="/abs/2501.12345">arXiv:2501.12345</a></dt><dd><div class="meta">
 <div class="list-title mathjax"><span class="descriptor">Title:</span>A <em>control</em> study</div>
 <div class="list-authors"><a href="/search">A Researcher</a>, <a href="/search">B Researcher</a></div>
 </div></dd></dl></html>'''


def pdf_bytes(width=100):
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=100)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.pace = patch("paper_daily.network._pace_arxiv")
        self.pace.start()
        self.addCleanup(self.pace.stop)

    def response(self, body=b"ok", headers=None):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = body
        response.headers = headers or {}
        response.geturl.return_value = "https://example.org/file"
        return response

    def test_timeout_retry_is_bounded_and_error_is_redacted(self):
        opener = MagicMock()
        opener.open.side_effect = URLError("private-secret-in-query")
        with patch.object(network, "build_opener", return_value=opener), patch.object(network.time, "sleep") as sleep:
            with self.assertRaises(network.FetchError) as raised:
                network.fetch("https://example.org/?api_key=private-secret-in-query", retries=2)
        self.assertEqual(opener.open.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertNotIn("secret", str(raised.exception))
        self.assertNotIn("api_key", str(raised.exception))

    def test_429_retry_after_is_capped_then_success(self):
        headers = Message()
        headers["Retry-After"] = "9999"
        opener = MagicMock()
        opener.open.side_effect = [HTTPError("https://example.org/?key=secret", 429, "secret", headers, None), self.response()]
        with patch.object(network, "build_opener", return_value=opener), patch.object(network.time, "sleep") as sleep:
            self.assertEqual(network.fetch("https://example.org/"), b"ok")
        sleep.assert_called_once_with(60.0)

    def test_429_exhaustion_is_not_empty_result(self):
        opener = MagicMock()
        opener.open.side_effect = HTTPError("https://example.org/", 429, "body secret", {}, None)
        with patch.object(network, "build_opener", return_value=opener), patch.object(network.time, "sleep"):
            with self.assertRaisesRegex(network.FetchError, "HTTP 429"):
                network.fetch("https://example.org/", retries=0)
        self.assertEqual(opener.open.call_count, 1)

    def test_invalid_urls_are_rejected_without_echoing_credentials(self):
        for url in ["file:///etc/passwd", "https://user:secret@example.org/a", "javascript:secret", "https://example.org:bad/a"]:
            with self.subTest(url=url), self.assertRaises(network.FetchError) as raised:
                network.fetch(url)
            self.assertNotIn("secret", str(raised.exception))

    def test_size_limit_and_invalid_content_length(self):
        for headers in [{"Content-Length": str(network.MAX_BYTES + 1)}, {"Content-Length": "bad"}]:
            opener = MagicMock()
            opener.open.return_value = self.response(headers=headers)
            with patch.object(network, "build_opener", return_value=opener), self.assertRaises(network.FetchError):
                network.fetch("https://example.org/")

    def test_openalex_key_is_header_only_and_unauthorized_is_clear(self):
        opener = MagicMock()
        opener.open.side_effect = HTTPError("https://api.openalex.org/works", 401, "private-key", {}, None)
        with patch.dict("os.environ", {"OPENALEX_API_KEY": "private-key"}), patch.object(network, "build_opener", return_value=opener):
            with self.assertRaisesRegex(network.FetchError, "OPENALEX_API_KEY") as raised:
                network.fetch("https://api.openalex.org/works?search=control")
        request = opener.open.call_args.args[0]
        self.assertNotIn("private-key", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer private-key")
        self.assertNotIn("private-key", str(raised.exception))

    def test_redirect_drops_authorization_across_hosts(self):
        request = Request("https://api.openalex.org/works", headers={"Authorization": "Bearer secret"})
        redirected = network._SafeRedirect().redirect_request(request, None, 302, "", {}, "https://example.org/works")
        self.assertIsNone(redirected.get_header("Authorization"))
        with self.assertRaises(network.FetchError):
            network._SafeRedirect().redirect_request(request, None, 302, "", {}, "http://api.openalex.org/works")

    def test_actual_arxiv_pacing(self):
        self.pace.stop()
        with patch.object(network, "_last_arxiv_request", 10.0), patch.object(network.time, "monotonic", side_effect=[11.0, 13.2]), patch.object(network.time, "sleep") as sleep:
            network._pace_arxiv("export.arxiv.org")
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 2.2)


class SourceTests(unittest.TestCase):
    def test_arxiv_versions_and_submission_are_not_announcements(self):
        with patch.object(network, "fetch", return_value=ATOM) as fetch:
            item = sources.arxiv_search("all:control")[0]
        self.assertEqual(item["arxiv_id"], "2501.12345")
        self.assertEqual(item["version"], "v2")
        self.assertEqual(item["first_submitted"], "2025-01-10T10:00:00Z")
        self.assertEqual(item["updated"], "2025-02-10T12:00:00Z")
        self.assertIsNone(item["first_announced"])
        self.assertEqual(item["discovery_source"], "arxiv")
        self.assertTrue(fetch.call_args.args[0].startswith("https://export.arxiv.org/api/query?"))

    def test_legacy_identifier(self):
        item = sources._parse_atom(ATOM.replace(b"2501.12345v2", b"hep-th/9901001v3"), "https://export.arxiv.org/")[0]
        self.assertEqual(item["arxiv_id"], "hep-th/9901001")
        self.assertEqual(item["version"], "v3")

    def test_rss_dates_and_replacements(self):
        with patch.object(network, "fetch", return_value=RSS):
            item = sources.arxiv_recent("cs.RO")[0]
        self.assertIsNone(item["first_submitted"])
        self.assertIsNone(item["updated"])
        self.assertIsNone(item["first_announced"])
        self.assertEqual(item["announcement_date"], "2025-02-11T00:00:00-05:00")
        self.assertEqual(item["feed_generated_at"], "2025-02-11T05:01:00Z")
        self.assertEqual(item["abstract"], "A short abstract.")
        self.assertEqual(item["authors"], ["A Researcher", "B Researcher"])
        new = sources._parse_atom(RSS.replace(b">replace<", b">new<"), "https://rss.arxiv.org/atom/cs.RO", rss=True)[0]
        self.assertEqual(new["first_announced"], new["announcement_date"])

    def test_official_html_fallback_is_title_only(self):
        for first in [network.FetchError("HTTP 429"), b'<feed xmlns="http://www.w3.org/2005/Atom"/>']:
            with self.subTest(first=first), patch.object(network, "fetch", side_effect=[first, HTML]):
                item = sources.arxiv_recent("cs.RO")[0]
            self.assertEqual(item["title"], "A control study")
            self.assertEqual(item["listed_date"], "2025-01-10")
            self.assertIsNone(item["first_submitted"])
            self.assertIsNone(item["first_announced"])
            self.assertIsNone(item["abstract"])
            self.assertEqual(item["discovery_method"], "recent_html")
            self.assertIn("discovery_warning", item)

    def test_invalid_arxiv_response_is_not_no_results(self):
        for body in [b"<html>login</html>", b"bad xml", ATOM.replace(b"http://arxiv.org/abs/2501.12345v2", b"http://arxiv.org/api/errors#x")]:
            with self.subTest(body=body), patch.object(network, "fetch", return_value=body), self.assertRaises(sources.SourceError):
                sources.arxiv_search("all:control")
        with patch.object(network, "fetch", return_value=b'<feed xmlns="http://www.w3.org/2005/Atom"/>'):
            self.assertEqual(sources.arxiv_search("all:control"), [])

    def test_crossref_candidate_not_publication_verification(self):
        body = {"status": "ok", "message": {"items": [{"title": ["A study"], "DOI": "10.1234/example",
                "author": [{"given": "A", "family": "Researcher"}], "container-title": ["A Journal"], "type": "journal-article"}]}}
        with patch.object(network, "fetch", return_value=json.dumps(body).encode()):
            item = sources.crossref_search("A study")[0]
        self.assertFalse(item["publication_verified"])
        self.assertEqual(item["venue"], "A Journal")

    def test_openalex_candidate_key_not_in_provenance(self):
        body = {"results": [{"display_name": "A study", "doi": "https://doi.org/10.1234/example",
                            "primary_location": {"source": {"display_name": "A Journal"}}}]}
        with patch.dict("os.environ", {"OPENALEX_API_KEY": "do-not-store"}), patch.object(network, "fetch", return_value=json.dumps(body).encode()) as fetch:
            item = sources.openalex_search("A study")[0]
        self.assertFalse(item["publication_verified"])
        self.assertEqual(item["doi"], "10.1234/example")
        self.assertNotIn("do-not-store", json.dumps(item))
        self.assertNotIn("do-not-store", fetch.call_args.args[0])

    def test_malformed_json_and_provider_errors_fail_explicitly(self):
        for function in [sources.crossref_search, sources.openalex_search]:
            for body in [b"bad json", b"[]", b'{"error":"private response"}']:
                with self.subTest(function=function, body=body), patch.object(network, "fetch", return_value=body), self.assertRaises(sources.SourceError):
                    function("control")

    def test_malformed_nested_records_fail_explicitly(self):
        pairs = [(sources.crossref_search, {"status": "ok", "message": {"items": [{"title": ["A study"], "author": "bad"}]}}),
                 (sources.openalex_search, {"results": [{"display_name": "A study", "primary_location": "bad"}]})]
        for function, body in pairs:
            with self.subTest(function=function), patch.object(network, "fetch", return_value=json.dumps(body).encode()), self.assertRaises(sources.SourceError):
                function("control")


class DownloadTests(unittest.TestCase):
    def test_valid_pdf_is_atomic_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "with spaces 中文" / "paper.pdf"
            with patch.object(network, "fetch", return_value=pdf_bytes()):
                result = sources.download_pdf("https://example.org/paper.pdf?signature=secret", destination)
                repeat = sources.download_pdf("https://example.org/paper.pdf", destination)
            self.assertTrue(destination.is_file())
            self.assertEqual(result["pages"], 1)
            self.assertEqual(repeat["status"], "already_present")
            self.assertEqual(result["source_url"], "https://example.org/paper.pdf")
            self.assertFalse(list(destination.parent.glob("*.tmp")))

    def test_nonidentical_pdf_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "paper.pdf"
            original = pdf_bytes(100)
            destination.write_bytes(original)
            with patch.object(network, "fetch", return_value=pdf_bytes(200)), self.assertRaises(FileExistsError):
                sources.download_pdf("https://example.org/paper.pdf", destination)
            self.assertEqual(destination.read_bytes(), original)

    def test_html_and_broken_pdf_do_not_create_files(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "paper.pdf"
            for body in [b"<html>institution login</html>", b"%PDF-1.7\nbroken"]:
                with self.subTest(body=body), patch.object(network, "fetch", return_value=body), self.assertRaises(sources.SourceError):
                    sources.download_pdf("https://example.org/paper.pdf", destination)
                self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
