"""
Core PDF scraping utilities for scanning web pages and downloading PDF files.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

try:
    from pdfminer.high_level import extract_text as pdf_extract_text
except ImportError:  # pragma: no cover - optional dependency
    pdf_extract_text = None  # type: ignore

LOGGER = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "PdfScraper/1.0 (+https://github.com/cursor/cursor-download-all-pdfs)"
    )
}


@dataclass(frozen=True)
class DownloadResult:
    """Represents a completed PDF download."""

    source_url: str
    pdf_path: Path
    text_path: Optional[Path] = None


class PdfScraper:
    """
    Crawl HTML pages, collect PDF links, download them, and optionally extract text.
    """

    def __init__(
        self,
        output_dir: str | Path = "./downloads",
        *,
        extract_text: bool = False,
        concurrency: int = 4,
        delay: float = 0.0,
        user_agent: Optional[str] = None,
        follow_external_links: bool = False,
        respect_robots: bool = True,
        timeout: int = 15,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.extract_text = extract_text
        if self.extract_text and pdf_extract_text is None:
            raise RuntimeError(
                "pdfminer.six is required for text extraction. "
                "Install it with `pip install pdfminer.six`."
            )

        self.concurrency = max(1, concurrency)
        self.delay = max(0.0, delay)
        self.follow_external_links = follow_external_links
        self.respect_robots = respect_robots
        self.timeout = timeout

        self.session = session or requests.Session()
        headers = DEFAULT_HEADERS.copy()
        if user_agent:
            headers["User-Agent"] = user_agent
        self.session.headers.update(headers)

        self._robots_cache: dict[str, RobotFileParser] = {}
        self._robots_lock = threading.Lock()
        self._throttle_lock = threading.Lock()
        self._last_request_ts = 0.0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def crawl(self, url: str, *, max_depth: int = 0) -> List[DownloadResult]:
        """
        Crawl a single starting URL up to `max_depth` link hops, downloading PDFs.
        """
        discovered_results: List[DownloadResult] = []
        visited_pages: Set[str] = set()
        queue: deque[Tuple[str, int]] = deque([(url, 0)])
        start_domain = urlparse(url).netloc

        while queue:
            current_url, depth = queue.popleft()
            normalized = self._normalize_url(current_url)
            if normalized in visited_pages:
                continue
            visited_pages.add(normalized)

            if not self._allowed_by_robots(current_url):
                LOGGER.info("Blocked by robots.txt: %s", current_url)
                continue

            LOGGER.info("Fetching HTML: %s", current_url)
            html = self._fetch_html(current_url)
            if html is None:
                continue

            pdf_links = self._extract_pdf_links(html, current_url)
            if pdf_links:
                LOGGER.info("Found %d PDF links on %s", len(pdf_links), current_url)
                discovered_results.extend(self._download_many(pdf_links))

            if depth >= max_depth:
                continue

            for link in self._extract_html_links(html, current_url):
                if link in visited_pages:
                    continue
                if not self.follow_external_links and urlparse(link).netloc != start_domain:
                    continue
                queue.append((link, depth + 1))

        return discovered_results

    def crawl_many(self, urls: Sequence[str], *, max_depth: int = 0) -> List[DownloadResult]:
        """Crawl a sequence of URLs."""
        results: List[DownloadResult] = []
        for url in urls:
            try:
                results.extend(self.crawl(url, max_depth=max_depth))
            except Exception as exc:  # pragma: no cover - network dependent
                LOGGER.error("Failed to crawl %s: %s", url, exc)
        return results

    # ------------------------------------------------------------------ #
    # Networking helpers
    # ------------------------------------------------------------------ #

    def _fetch_html(self, url: str) -> Optional[str]:
        try:
            self._throttle()
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            LOGGER.warning("Failed to fetch %s: %s", url, exc)
            return None

    def _download_many(self, links: Sequence[str]) -> List[DownloadResult]:
        results: List[DownloadResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            future_to_url = {pool.submit(self._download_single, link): link for link in links}
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    result = future.result()
                except Exception as exc:  # pragma: no cover - network dependent
                    LOGGER.warning("Download failed (%s): %s", future_to_url[future], exc)
                else:
                    if result:
                        results.append(result)
        return results

    def _download_single(self, url: str) -> Optional[DownloadResult]:
        if not self._allowed_by_robots(url):
            LOGGER.info("Blocked by robots.txt: %s", url)
            return None

        LOGGER.info("Downloading PDF: %s", url)
        self._throttle()
        try:
            with self.session.get(url, stream=True, timeout=self.timeout) as resp:
                resp.raise_for_status()
                if not self._looks_like_pdf(resp, url):
                    LOGGER.debug("Skipping non-PDF response: %s", url)
                    return None

                filename = self._build_filename(url, resp)
                pdf_path = self.output_dir / filename
                pdf_path = self._deduplicate_path(pdf_path)

                with open(pdf_path, "wb") as handle:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            handle.write(chunk)

        except requests.RequestException as exc:
            LOGGER.warning("Network error downloading %s: %s", url, exc)
            return None

        text_path: Optional[Path] = None
        if self.extract_text:
            text_path = pdf_path.with_suffix(".txt")
            try:
                text = pdf_extract_text(str(pdf_path))  # type: ignore[arg-type]
                text_path.write_text(text, encoding="utf-8")
            except Exception as exc:  # pragma: no cover - tool dependent
                LOGGER.warning("Failed to extract text from %s: %s", pdf_path, exc)
                text_path = None

        return DownloadResult(source_url=url, pdf_path=pdf_path, text_path=text_path)

    # ------------------------------------------------------------------ #
    # Parsing helpers
    # ------------------------------------------------------------------ #

    def _extract_pdf_links(self, html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: Set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            absolute = urljoin(base_url, href)
            if self._is_pdf_url(absolute):
                links.add(self._normalize_url(absolute))
        return sorted(links)

    def _extract_html_links(self, html: str, base_url: str) -> Set[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: Set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if href.startswith("#"):
                continue
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in ("http", "https"):
                continue
            if self._is_pdf_url(absolute):
                continue
            links.add(self._normalize_url(absolute))
        return links

    # ------------------------------------------------------------------ #
    # Utility helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_pdf_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        path = parsed.path.lower()
        if path.endswith(".pdf"):
            return True
        return False

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlparse(url)
        normalized = parsed._replace(fragment="")
        if not normalized.path:
            normalized = normalized._replace(path="/")
        return urlunparse(normalized)

    def _build_filename(self, url: str, response: requests.Response) -> str:
        # Attempt to honor Content-Disposition.
        cd = response.headers.get("content-disposition")
        if cd:
            filename = self._filename_from_content_disposition(cd)
            if filename:
                return filename

        parsed = urlparse(url)
        candidate = Path(parsed.path).name or "download.pdf"
        if not candidate.lower().endswith(".pdf"):
            candidate += ".pdf"
        return candidate

    @staticmethod
    def _filename_from_content_disposition(header_value: str) -> Optional[str]:
        parts = header_value.split(";")
        for part in parts:
            part = part.strip()
            if part.lower().startswith("filename="):
                filename = part.split("=", 1)[1].strip('"\''" \t")
                if filename:
                    return filename
        return None

    def _deduplicate_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        counter = 1
        while True:
            candidate = path.with_name(f"{stem}({counter}){suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _looks_like_pdf(self, response: requests.Response, url: str) -> bool:
        content_type = response.headers.get("content-type", "").lower()
        if "application/pdf" in content_type:
            return True
        # Fall back to extension heuristic when server misreports.
        return self._is_pdf_url(url)

    def _allowed_by_robots(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        base = f"{parsed.scheme}://{parsed.netloc}"
        with self._robots_lock:
            parser = self._robots_cache.get(base)
            if parser is None:
                robots_url = urljoin(base, "/robots.txt")
                parser = RobotFileParser()
                parser.set_url(robots_url)
                try:
                    parser.read()
                except Exception:  # pragma: no cover - network dependent
                    parser = RobotFileParser()
                    parser.parse("")  # Treat as allow-all on failure.
                self._robots_cache[base] = parser
        user_agent = self.session.headers.get("User-Agent", DEFAULT_HEADERS["User-Agent"])
        return parser.can_fetch(user_agent, url)

    def _throttle(self) -> None:
        if self.delay <= 0:
            return
        with self._throttle_lock:
            elapsed = time.time() - self._last_request_ts
            wait_time = self.delay - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
            self._last_request_ts = time.time()


__all__ = ["PdfScraper", "DownloadResult"]
