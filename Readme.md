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
Download every linked PDF from a single page:
```
python scraper.py --url https://example.com/resources --output ./downloads
```
Process a list of seed pages (one URL per line):
```
python scraper.py --input urls.txt --output ./downloads --concurrency 4
```
Extract plain text alongside each PDF:
```
python scraper.py --url https://example.com --output ./downloads --extract
```

Notable CLI options
- `--max-depth`: follow HTML links up to _n_ hops away from the starting URL(s)
- `--follow-external`: allow crawling across different domains
- `--delay`: seconds to wait between requests (shared across threads)
- `--user-agent`: custom identification string for polite crawling
- `--no-robots`: ignore robots.txt (⚠️ only where permitted)
- `--verbose`: emit detailed logging about crawl progress

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
