# PDF Scraper

A small utility to find and download PDF files from web pages or local links and optionally extract text. Designed to be simple, extensible and scriptable.

## Features
- Crawl a single page or a list of pages for PDF links
- Download PDFs to a configurable output directory
- Optional text extraction from PDFs (plain text)
- Respect robots.txt and rate limits (configurable)
- CLI and library usage for easy automation

## Requirements
- Python 3.8+
- Recommended libraries:
    - requests
    - beautifulsoup4
    - tqdm (optional, for progress)
    - pdfminer.six or PyPDF2 (for optional text extraction)

Install dependencies:
```
pip install -r requirements.txt
```
or
```
pip install requests beautifulsoup4 tqdm pdfminer.six
```

## Installation
1. Clone the repository:
```
git clone https://example.com/your-repo.git
cd your-repo
```
2. Install dependencies as shown above.

## Quick CLI usage
Basic download from a single URL:
```
python scraper.py --url https://example.com/page-with-pdfs --output ./downloads
```
Download from a file with multiple URLs:
```
python scraper.py --input urls.txt --output ./downloads --concurrency 4
```
Extract text after download:
```
python scraper.py --url https://example.com --output ./downloads --extract
```

CLI options (common)
- --url: single page URL to scan
- --input: file containing URLs (one per line)
- --output: output directory for downloaded PDFs
- --extract: enable text extraction to .txt files
- --concurrency: number of parallel downloads
- --delay: seconds to wait between requests
- --user-agent: custom user agent string

## Library usage
Example Python usage:
```py
from pdf_scraper import PdfScraper

scraper = PdfScraper(output_dir="./downloads", extract_text=True, concurrency=2)
scraper.crawl("https://example.com/page-with-pdfs")
```

## Configuration
Put defaults into a config file (yaml/json) or pass via CLI. Typical options:
- output_dir
- concurrency
- delay_between_requests
- user_agent
- follow_external_links (true/false)
- respect_robots (true/false)

## Output
- Downloads stored as ./downloads/<original-filename>.pdf
- If extraction enabled: ./downloads/<original-filename>.txt

## Tips & Best Practices
- Respect website terms and robots.txt
- Use reasonable concurrency and delay to avoid overloading servers
- Test on a few pages before large crawls
- Check downloaded PDFs for duplicates by checksum or filename normalization

## Contributing
- Fork the repo, create a feature branch, open a PR with tests and a short description.

## License
Specify a license (e.g., MIT). Add a LICENSE file to the repo.

If you want, provide the script name or language details and I can produce a ready-to-run example implementation.
