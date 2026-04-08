#!/usr/bin/env python3
"""
MESDA Journal Web Scraper
Extracts article metadata from mesdajournal.org/online-issues/
"""

import json
import re
import time
import sys
from pathlib import Path
from typing import List, Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError
import ssl

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 not installed. Run: pip install beautifulsoup4")
    sys.exit(1)

OUT_DIR = Path(__file__).parent
MESDA_URL = "https://www.mesdajournal.org/online-issues/"

def fetch_html(url: str, retries: int = 3) -> Optional[str]:
    """Fetch HTML from URL with retries and respectful rate limiting."""
    for attempt in range(retries):
        try:
            time.sleep(2)  # Respectful delay
            req = Request(url)
            req.add_header('User-Agent', 'SAPFM Card Catalog ETL (research/educational)')

            # Handle SSL issues
            ctx = ssl._create_unverified_context()
            with urlopen(req, context=ctx, timeout=30) as response:
                return response.read().decode('utf-8', errors='replace')
        except URLError as e:
            print(f"  Attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5)
            continue
    return None

def parse_articles_from_html(html: str) -> List[Dict[str, str]]:
    """Parse MESDA Journal HTML to extract article metadata."""
    soup = BeautifulSoup(html, 'html.parser')
    articles = []

    current_volume = None
    current_year = None

    # Find all heading tags to identify volumes and articles
    for elem in soup.find_all(['h2', 'h4', 'a', 'p']):
        # Volume headers like "Vol. 46 (2025)"
        if elem.name == 'h2':
            match = re.search(r'Vol\.\s+(\d+)\s*\((\d{4})\)', elem.get_text())
            if match:
                current_volume = int(match.group(1))
                current_year = int(match.group(2))
                print(f"  Found Vol. {current_volume} ({current_year})")

        # Article links
        elif elem.name == 'a' and current_year:
            text = elem.get_text().strip()
            href = elem.get('href', '')

            # Skip non-article links (Blurb, archive.org container links)
            if not href or 'blurb.com' in href or text.startswith('Vol.'):
                continue

            # Extract author if it's in the format "Title by Author"
            # Author might be in the same element or following text
            parent = elem.parent
            full_text = parent.get_text() if parent else text

            title = text
            author = ""

            # Try to extract author from " by Author" pattern
            match = re.search(r'\s+by\s+(.+?)(?:\n|$)', full_text)
            if match:
                author = match.group(1).strip()
                # Remove author from title if it's there
                title = re.sub(r'\s+by\s+.+', '', title).strip()

            # Skip if it's just a volume/issue header
            if len(title) > 10 and current_volume and current_year:
                article = {
                    "article_title": title,
                    "article_author": author,
                    "year": current_year,
                    "volume": current_volume,
                    "url": href,
                    "source_key": "mesda",
                    "card_type": "article",
                }
                articles.append(article)
                print(f"    [{len(articles)}] {title[:60]}...")

    return articles

def fetch_article_text(url: str, max_chars: int = 5000) -> Optional[str]:
    """Fetch and extract text from an individual article page."""
    try:
        html = fetch_html(url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()

        # Try to find the main article content
        # MESDA articles typically in <article> or <div class="content">
        content = soup.find('article')
        if not content:
            content = soup.find('div', class_='content')
        if not content:
            content = soup.body if soup.body else soup

        # Get text content
        text = content.get_text() if content else soup.get_text()

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text[:max_chars]
    except Exception as e:
        print(f"  Error fetching article text: {e}")
        return None

def phase_scrape():
    """Scrape all articles from MESDA Journal website."""
    print(f"\nFetching MESDA Journal from {MESDA_URL}")
    html = fetch_html(MESDA_URL)

    if not html:
        print("ERROR: Could not fetch MESDA Journal website")
        return

    print("Parsing articles from HTML...")
    articles = parse_articles_from_html(html)

    # Save to mesda_journal_website_raw.json
    raw_path = OUT_DIR / "mesda_journal_website_raw.json"
    raw_path.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nScraped {len(articles)} articles")
    print(f"Saved to {raw_path.name}")

def phase_fetch_text(limit: int = 10):
    """Fetch article text for a sample of articles."""
    raw_path = OUT_DIR / "mesda_journal_website_raw.json"

    if not raw_path.exists():
        print("ERROR: mesda_journal_website_raw.json not found. Run scrape phase first.")
        return

    articles = json.loads(raw_path.read_text(encoding="utf-8"))

    print(f"\nFetching article text for first {limit} articles...")
    for i, article in enumerate(articles[:limit]):
        url = article.get("url", "")
        if not url:
            continue

        print(f"  [{i+1}] Fetching: {article['article_title'][:60]}...")
        text = fetch_article_text(url, max_chars=5000)

        if text:
            article["body"] = text
            print(f"      ✓ Got {len(text):,} chars")
        else:
            print(f"      ✗ Failed to fetch")

    # Save back with text added
    raw_path.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFetch complete. Saved {len(articles)} articles to {raw_path.name}")

def main():
    if len(sys.argv) > 1:
        phase = sys.argv[1]
    else:
        phase = "scrape"

    limit = 10
    if len(sys.argv) > 2:
        limit = int(sys.argv[2])

    if phase == "scrape":
        phase_scrape()
    elif phase == "fetch":
        phase_fetch_text(limit=limit)
    elif phase == "fetch-all":
        raw_path = OUT_DIR / "mesda_journal_website_raw.json"
        articles = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
        phase_fetch_text(limit=len(articles))
    else:
        print(f"Unknown phase: {phase}")
        print("Usage: python mesda_website_scraper.py [scrape|fetch|fetch-all] [limit]")
        print("  scrape     — Extract article metadata from mesdajournal.org")
        print("  fetch [N]  — Fetch article text for first N articles (default 10)")
        print("  fetch-all  — Fetch article text for all articles")

if __name__ == "__main__":
    main()
