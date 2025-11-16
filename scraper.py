#!/usr/bin/env python3
"""
Command-line helper for downloading every PDF linked from one or more web pages.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List

from pdf_scraper import PdfScraper


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download all PDF files referenced by the provided URL(s)."
    )

    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--url", help="Single page URL to crawl for PDF files.")
    target.add_argument(
        "--input",
        help="Path to a text file containing URLs (one per line).",
    )

    parser.add_argument(
        "--output",
        default="./downloads",
        help="Directory to store downloaded PDFs (default: %(default)s).",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Also extract text from each PDF using pdfminer.six.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Number of parallel download workers (default: %(default)s).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to wait between HTTP requests (default: %(default)s).",
    )
    parser.add_argument(
        "--user-agent",
        help="Custom User-Agent string for HTTP requests.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=0,
        help="How many link hops away from the starting page to crawl.",
    )
    parser.add_argument(
        "--follow-external",
        action="store_true",
        help="Follow links that leave the starting domain.",
    )
    parser.add_argument(
        "--no-robots",
        action="store_true",
        help="Ignore robots.txt rules (use with caution).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Timeout (seconds) for network requests (default: %(default)s).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    return parser.parse_args(argv)


def load_urls(args: argparse.Namespace) -> List[str]:
    if args.url:
        return [args.url.strip()]
    assert args.input
    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(f"URL list not found: {path}")
    urls: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                urls.append(line)
    if not urls:
        raise ValueError("Input file does not contain any URLs.")
    return urls


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    urls = load_urls(args)

    scraper = PdfScraper(
        output_dir=args.output,
        extract_text=args.extract,
        concurrency=args.concurrency,
        delay=args.delay,
        user_agent=args.user_agent,
        follow_external_links=args.follow_external,
        respect_robots=not args.no_robots,
        timeout=args.timeout,
    )

    logging.info("Starting crawl for %d URL(s)", len(urls))
    results = scraper.crawl_many(urls, max_depth=args.max_depth)

    if results:
        print(f"Downloaded {len(results)} PDF files to {args.output}")
        for item in results:
            print(f"- {item.pdf_path} (from {item.source_url})")
    else:
        print("No PDF files were downloaded.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
