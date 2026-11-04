"""
Abhinav Group Website Crawler — Phase 3
Crawls https://abhinavgroup.co.in/ respecting robots.txt.
Extracts: pages, project data, images, documents.

Outputs (written to data/website-extraction/):
  - discovered_urls.csv
  - extracted_pages.json
  - projects.json
  - project_images.json
  - documents_inventory.json

Reports (written to data/reports/):
  - extraction_report.md
  - broken_links_report.csv
  - duplicate_content_report.csv
  - missing_information_report.md

Usage:
    python scripts/crawl_website/crawl_abhinav.py

Requirements (install once):
    pip install httpx beautifulsoup4 lxml
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.robotparser
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "website-extraction"
REPORTS_DIR = ROOT / "data" / "reports"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ─────────────────────────────────────────────────────────────────
BASE_URL = "https://abhinavgroup.co.in"
MAX_PAGES = 300          # Safety limit
REQUEST_DELAY = 1.5      # Seconds between requests (be polite)
REQUEST_TIMEOUT = 20     # Seconds per request
MAX_RETRIES = 2

# Project keywords to identify project pages
PROJECT_KEYWORDS = [
    "samsara", "pebbles greenfield", "pebble greenfield", "the curve", "aeromall",
    "vatvriksha", "pebbles urbania", "celestia", "royal heritage", "avaanti",
    "windmere", "silver cascade", "elara", "signature", "enclave", "heights",
    "residency", "gardens", "villa", "township"
]

# Image categories
IMAGE_CATEGORIES = {
    "banner": ["banner", "hero", "slider", "carousel"],
    "gallery": ["gallery", "thumb", "image"],
    "floor_plan": ["floor", "plan", "layout"],
    "amenity": ["amenity", "amenities", "facility"],
    "location": ["location", "map", "connectivity"],
    "logo": ["logo"],
}

HEADERS = {
    "User-Agent": "AbhinavGroupChatbotCrawler/1.0 (Property Sales Chatbot; +https://abhinavgroup.co.in)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
}

# ── State ──────────────────────────────────────────────────────────────────
visited_urls: Set[str] = set()
queued_urls: List[str] = []
extracted_pages: List[Dict] = []
all_images: List[Dict] = []
all_documents: List[Dict] = []
broken_links: List[Dict] = []
crawl_errors: List[Dict] = []
content_hashes: Dict[str, List[str]] = defaultdict(list)

# ── Robots.txt ─────────────────────────────────────────────────────────────
rp = urllib.robotparser.RobotFileParser()
rp.set_url(f"{BASE_URL}/robots.txt")
print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching robots.txt ...")

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx beautifulsoup4 lxml")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 not installed. Run: pip install httpx beautifulsoup4 lxml")
    sys.exit(1)

try:
    rp.read()
    print(f"  robots.txt fetched OK")
except Exception as e:
    print(f"  Could not fetch robots.txt: {e} — continuing with full crawl")


# ── Helpers ────────────────────────────────────────────────────────────────

def normalize_url(url: str, base: str = BASE_URL) -> Optional[str]:
    """Normalize URL — returns None if should be skipped."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("#") or url.startswith("javascript:") or url.startswith("mailto:"):
        return None
    full = urljoin(base, url)
    parsed = urlparse(full)
    # Stay on same domain
    if parsed.netloc and parsed.netloc not in ("abhinavgroup.co.in", "www.abhinavgroup.co.in"):
        return None
    # Strip fragments
    full = parsed._replace(fragment="").geturl()
    return full


def is_allowed(url: str) -> bool:
    """Check robots.txt permission."""
    try:
        return rp.can_fetch(HEADERS["User-Agent"], url)
    except Exception:
        return True  # Allow if robots.txt check fails


def is_document_url(url: str) -> bool:
    """Check if URL is a document (PDF, etc.)."""
    ext = urlparse(url).path.lower().split(".")[-1]
    return ext in ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx")


def is_image_url(url: str) -> bool:
    """Check if URL is an image."""
    ext = urlparse(url).path.lower().split(".")[-1]
    return ext in ("jpg", "jpeg", "png", "gif", "webp", "svg", "avif")


def classify_image(url: str, alt: str = "", caption: str = "") -> str:
    """Classify image into a category."""
    text = (url + " " + alt + " " + caption).lower()
    for category, keywords in IMAGE_CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return category
    return "general"


def identify_project(text: str) -> Optional[str]:
    """Identify which project a page/image is about."""
    t = text.lower()
    if "samsara" in t:
        return "Samsara"
    if "greenfield" in t or ("pebble" in t and "urban" not in t):
        return "Pebbles Greenfield"
    if "urbania" in t:
        return "Pebbles Urbania"
    if ("curve" in t and "virar" in t) or "thecurve" in t or "abhinavthecurve" in t:
        return "The Curve"
    if "aeromall" in t or ("aero" in t and "mall" in t):
        return "Aeromall"
    if "vatvriksha" in t:
        return "Vatvriksha"
    if "avaanti" in t:
        return "Avaanti Residences"
    if "windmere" in t:
        return "Windmere"
    if "celestia" in t:
        return "Celestia"
    return None


def extract_images_from_soup(soup: BeautifulSoup, page_url: str) -> List[Dict]:
    """Extract all image URLs from a BeautifulSoup object."""
    images = []
    seen = set()

    def add_image(img_url: str, alt: str = "", caption: str = "", context: str = "img_tag"):
        if not img_url or img_url in seen:
            return
        seen.add(img_url)
        full_url = normalize_url(img_url, page_url)
        if not full_url:
            return
        filename = Path(urlparse(full_url).path).name or "unknown"
        project = identify_project(page_url + " " + alt + " " + caption + " " + filename)
        images.append({
            "original_url": full_url,
            "source_page": page_url,
            "project": project or "unknown",
            "filename": filename,
            "alt_text": alt,
            "caption": caption,
            "context": context,
            "category": classify_image(full_url, alt, caption),
            "status": "discovered",
        })

    # <img> tags
    for img in soup.find_all("img"):
        # Try srcset first (highest quality)
        srcset = img.get("srcset", "") or img.get("data-srcset", "")
        if srcset:
            # Pick the largest srcset entry
            parts = [p.strip().split() for p in srcset.split(",") if p.strip()]
            if parts:
                try:
                    largest = sorted(parts, key=lambda x: int(x[1].replace("w", "")) if len(x) > 1 else 0, reverse=True)[0][0]
                    add_image(largest, img.get("alt", ""), "", "srcset")
                except (ValueError, IndexError):
                    pass

        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")
        if src:
            add_image(src, img.get("alt", ""), "", "img_src")

    # CSS background images
    for tag in soup.find_all(style=True):
        style = tag.get("style", "")
        bg_matches = re.findall(r'url\(["\']?([^)"\']+)["\']?\)', style)
        for bg_url in bg_matches:
            if is_image_url(bg_url):
                add_image(bg_url, "", "", "css_background")

    # WordPress Elementor / data-* attributes
    for tag in soup.find_all(attrs={"data-background": True}):
        add_image(tag["data-background"], "", "", "data_background")
    for tag in soup.find_all(attrs={"data-image": True}):
        add_image(tag["data-image"], "", "", "data_image")

    # WordPress gallery shortcodes in content
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if is_image_url(href):
            img_inside = a.find("img")
            alt = img_inside.get("alt", "") if img_inside else ""
            add_image(href, alt, "", "gallery_link")

    return images


def extract_text_content(soup: BeautifulSoup) -> str:
    """Extract clean text from a page."""
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:50000]  # Cap at 50k chars per page


def extract_meta(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract page metadata."""
    meta = {}
    title_tag = soup.find("title")
    if title_tag:
        meta["title"] = title_tag.get_text(strip=True)
    for m in soup.find_all("meta"):
        name = m.get("name") or m.get("property") or ""
        content = m.get("content") or ""
        if name and content:
            meta[name.lower()] = content[:500]
    return meta


def extract_rera_numbers(text: str) -> List[str]:
    """Extract RERA registration numbers from text."""
    patterns = [
        r'RERA[:\s]+([A-Z0-9]+)',
        r'P\d{11}',       # Maharashtra format: P52100XXXXXXX
        r'PR\d{13}',      # Other state format
    ]
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend(matches)
    return list(set(found))


def extract_phone_numbers(text: str) -> List[str]:
    """Extract Indian phone numbers from text."""
    patterns = [
        r'\+91[\s\-]?\d{10}',
        r'0\d{10}',
        r'\b\d{10}\b',
    ]
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        found.extend(matches)
    # Filter to plausible Indian numbers
    return [p for p in list(set(found)) if len(re.sub(r'\D', '', p)) == 10 or len(re.sub(r'\D', '', p)) == 12]


# ── Page Fetcher ───────────────────────────────────────────────────────────

def fetch_page(url: str, client: httpx.Client) -> Optional[httpx.Response]:
    """Fetch a page with retry logic."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
            return response
        except httpx.TimeoutException:
            if attempt < MAX_RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
            crawl_errors.append({"url": url, "error": "timeout", "attempt": attempt + 1})
            return None
        except Exception as e:
            crawl_errors.append({"url": url, "error": str(e), "attempt": attempt + 1})
            return None


# ── Sitemap Discovery ──────────────────────────────────────────────────────

def discover_sitemap_urls(client: httpx.Client) -> List[str]:
    """Try to fetch sitemap.xml and extract URLs."""
    sitemap_urls = []
    for sitemap_path in ["/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"]:
        sitemap_url = BASE_URL + sitemap_path
        print(f"  Trying sitemap: {sitemap_url}")
        resp = fetch_page(sitemap_url, client)
        if resp and resp.status_code == 200:
            # Parse XML sitemap
            urls = re.findall(r'<loc>(.*?)</loc>', resp.text)
            sitemap_urls.extend(urls)
            print(f"  Found {len(urls)} URLs in {sitemap_path}")
            # Check for sub-sitemaps
            sub_sitemaps = re.findall(r'<sitemap>.*?<loc>(.*?)</loc>.*?</sitemap>', resp.text, re.DOTALL)
            for sub in sub_sitemaps:
                sub_resp = fetch_page(sub, client)
                if sub_resp and sub_resp.status_code == 200:
                    sub_urls = re.findall(r'<loc>(.*?)</loc>', sub_resp.text)
                    sitemap_urls.extend(sub_urls)
                    print(f"    Sub-sitemap {sub}: {len(sub_urls)} URLs")
            break
    return list(set(sitemap_urls))


def discover_wp_api_urls(client: httpx.Client) -> List[str]:
    """Try WordPress REST API to find pages and posts."""
    api_urls = []
    endpoints = [
        "/wp-json/wp/v2/pages?per_page=100",
        "/wp-json/wp/v2/posts?per_page=100",
    ]
    for endpoint in endpoints:
        url = BASE_URL + endpoint
        resp = fetch_page(url, client)
        if resp and resp.status_code == 200:
            try:
                items = resp.json()
                for item in items:
                    link = item.get("link") or item.get("guid", {}).get("rendered")
                    if link:
                        api_urls.append(link)
            except Exception:
                pass
    return api_urls


# ── Main Crawl ─────────────────────────────────────────────────────────────

def crawl():
    print(f"\n{'='*60}")
    print(f"  ABHINAV GROUP WEBSITE CRAWLER")
    print(f"  Target: {BASE_URL}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    with httpx.Client(headers=HEADERS) as client:
        # Seed queue
        queued_urls.append(BASE_URL + "/")
        queued_urls.append(BASE_URL + "/sitemap.xml")

        # Discover sitemap URLs
        print("[Phase 3a] Discovering URLs from sitemap ...")
        sitemap_urls = discover_sitemap_urls(client)
        for u in sitemap_urls:
            if u not in queued_urls:
                queued_urls.append(u)
        print(f"  Sitemap URLs discovered: {len(sitemap_urls)}")

        # Discover WordPress API URLs
        print("[Phase 3b] Discovering URLs from WordPress REST API ...")
        wp_api_urls = discover_wp_api_urls(client)
        for u in wp_api_urls:
            if u not in queued_urls:
                queued_urls.append(u)
        print(f"  WP API URLs discovered: {len(wp_api_urls)}")

        # Main crawl loop
        print(f"\n[Phase 3c] Crawling pages ...")
        page_count = 0

        while queued_urls and page_count < MAX_PAGES:
            url = queued_urls.pop(0)

            # Normalize
            normalized = normalize_url(url)
            if not normalized:
                continue

            # Skip if already visited
            if normalized in visited_urls:
                continue
            visited_urls.add(normalized)

            # Skip documents (handle separately)
            if is_document_url(normalized):
                all_documents.append({
                    "url": normalized,
                    "source_page": url,
                    "type": normalized.split(".")[-1].lower(),
                    "status": "discovered",
                    "project": identify_project(normalized),
                })
                continue

            # Skip non-HTML
            if any(normalized.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".xml"]):
                continue

            # Check robots.txt
            if not is_allowed(normalized):
                print(f"  [BLOCKED] {normalized}")
                continue

            page_count += 1
            print(f"  [{page_count:03d}] {normalized}")

            # Fetch
            response = fetch_page(normalized, client)
            time.sleep(REQUEST_DELAY)

            if not response:
                broken_links.append({"url": normalized, "status": "fetch_error", "source": "crawler"})
                continue

            if response.status_code != 200:
                broken_links.append({
                    "url": normalized,
                    "status": str(response.status_code),
                    "source": "crawler"
                })
                if response.status_code not in (301, 302):
                    print(f"       -> HTTP {response.status_code}")
                continue

            # Parse HTML
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                continue

            soup = BeautifulSoup(response.text, "lxml")

            # Content hash for dedup
            text_content = extract_text_content(soup)
            content_hash = hashlib.sha256(text_content[:5000].encode()).hexdigest()[:16]
            content_hashes[content_hash].append(normalized)

            # Extract metadata
            meta = extract_meta(soup)
            project = identify_project(normalized + " " + meta.get("title", "") + " " + text_content[:2000])

            # Extract RERA numbers
            rera_numbers = extract_rera_numbers(text_content)

            # Extract phone numbers
            phones = extract_phone_numbers(text_content)

            # Extract images
            images = extract_images_from_soup(soup, normalized)
            all_images.extend(images)

            # Save page data
            page_data = {
                "url": normalized,
                "title": meta.get("title", ""),
                "meta_description": meta.get("description", ""),
                "og_title": meta.get("og:title", ""),
                "og_description": meta.get("og:description", ""),
                "og_image": meta.get("og:image", ""),
                "project": project,
                "rera_numbers": rera_numbers,
                "phone_numbers": phones,
                "text_length": len(text_content),
                "image_count": len(images),
                "content_hash": content_hash,
                "text_content": text_content,
                "crawled_at": datetime.now().isoformat(),
                "http_status": response.status_code,
            }
            extracted_pages.append(page_data)

            # Discover new links
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href:
                    continue
                full_href = normalize_url(href, normalized)
                if full_href and full_href not in visited_urls and full_href not in queued_urls:
                    queued_urls.append(full_href)

    print(f"\n[Phase 3d] Crawl complete.")
    print(f"  Pages crawled   : {len(extracted_pages)}")
    print(f"  Images found    : {len(all_images)}")
    print(f"  Documents found : {len(all_documents)}")
    print(f"  Broken links    : {len(broken_links)}")
    print(f"  Errors          : {len(crawl_errors)}")


# ── Project Data Extraction ────────────────────────────────────────────────

def build_projects_json() -> List[Dict]:
    """Build structured project data from crawled pages."""
    projects = {}

    for page in extracted_pages:
        project_name = page.get("project")
        if not project_name or project_name == "unknown":
            continue

        if project_name not in projects:
            projects[project_name] = {
                "project_name": project_name,
                "source_urls": [],
                "images": [],
                "documents": [],
                "rera_numbers": [],
                "phone_numbers": [],
                "text_snippets": [],
                "approval_status": "PENDING",
                "price_verified": False,
                "rera_verified": False,
                "data_sources": "website_crawler",
                "extraction_date": datetime.now().isoformat(),
                "requires_verification": True,
                "verification_notes": "Data extracted by crawler — requires manual review before publishing",
            }

        p = projects[project_name]
        if page["url"] not in p["source_urls"]:
            p["source_urls"].append(page["url"])

        # Collect unique RERA numbers
        for rera in page.get("rera_numbers", []):
            if rera not in p["rera_numbers"]:
                p["rera_numbers"].append(rera)

        # Collect unique phone numbers
        for phone in page.get("phone_numbers", []):
            if phone not in p["phone_numbers"]:
                p["phone_numbers"].append(phone)

        # Collect text snippet
        snippet = page["text_content"][:500].strip()
        if snippet and snippet not in p["text_snippets"]:
            p["text_snippets"].append(snippet)

    # Add images per project
    for img in all_images:
        pname = img.get("project")
        if pname and pname in projects:
            projects[pname]["images"].append(img["original_url"])

    # Add documents per project
    for doc in all_documents:
        pname = doc.get("project")
        if pname and pname in projects:
            projects[pname]["documents"].append(doc["url"])

    return list(projects.values())


# ── Output Writers ─────────────────────────────────────────────────────────

def write_outputs(projects: List[Dict]):
    print(f"\n[Phase 3e] Writing output files ...")

    # discovered_urls.csv
    with open(DATA_DIR / "discovered_urls.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "title", "project", "http_status", "crawled_at"])
        writer.writeheader()
        for page in extracted_pages:
            writer.writerow({
                "url": page["url"],
                "title": page.get("title", ""),
                "project": page.get("project", ""),
                "http_status": page.get("http_status", ""),
                "crawled_at": page.get("crawled_at", ""),
            })
        # Also write discovered-but-not-crawled URLs
        for url in visited_urls - {p["url"] for p in extracted_pages}:
            writer.writerow({"url": url, "title": "", "project": "", "http_status": "not_crawled", "crawled_at": ""})
    print(f"  discovered_urls.csv: {len(extracted_pages)} crawled pages")

    # extracted_pages.json (without full text to keep manageable)
    pages_summary = [{k: v for k, v in p.items() if k != "text_content"} for p in extracted_pages]
    with open(DATA_DIR / "extracted_pages.json", "w", encoding="utf-8") as f:
        json.dump(pages_summary, f, indent=2, ensure_ascii=False)
    print(f"  extracted_pages.json: {len(pages_summary)} pages")

    # projects.json
    with open(DATA_DIR / "projects.json", "w", encoding="utf-8") as f:
        json.dump(projects, f, indent=2, ensure_ascii=False)
    print(f"  projects.json: {len(projects)} projects")

    # project_images.json
    with open(DATA_DIR / "project_images.json", "w", encoding="utf-8") as f:
        json.dump(all_images, f, indent=2, ensure_ascii=False)
    print(f"  project_images.json: {len(all_images)} images")

    # documents_inventory.json
    with open(DATA_DIR / "documents_inventory.json", "w", encoding="utf-8") as f:
        json.dump(all_documents, f, indent=2, ensure_ascii=False)
    print(f"  documents_inventory.json: {len(all_documents)} documents")

    # broken_links_report.csv
    with open(REPORTS_DIR / "broken_links_report.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "status", "source"])
        writer.writeheader()
        writer.writerows(broken_links)
    print(f"  broken_links_report.csv: {len(broken_links)} broken links")

    # duplicate_content_report.csv
    duplicates = [(h, urls) for h, urls in content_hashes.items() if len(urls) > 1]
    with open(REPORTS_DIR / "duplicate_content_report.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["content_hash", "url_1", "url_2", "url_3"])
        for h, urls in duplicates:
            row = [h] + urls[:3]
            writer.writerow(row)
    print(f"  duplicate_content_report.csv: {len(duplicates)} duplicate groups")

    # extraction_report.md
    report = f"""# Abhinav Group Website Extraction Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Target: {BASE_URL}

## Summary

| Metric | Count |
|--------|-------|
| Pages crawled | {len(extracted_pages)} |
| Pages with errors | {len(broken_links)} |
| Total images discovered | {len(all_images)} |
| Total documents discovered | {len(all_documents)} |
| Projects identified | {len(projects)} |
| Duplicate content groups | {len(duplicates)} |
| Crawl errors | {len(crawl_errors)} |

## Projects Identified

"""
    for p in projects:
        report += f"### {p['project_name']}\n"
        report += f"- **Source URLs:** {len(p['source_urls'])}\n"
        report += f"- **Images:** {len(p['images'])}\n"
        report += f"- **RERA Numbers:** {', '.join(p['rera_numbers']) or 'Not found'}\n"
        report += f"- **Phone Numbers:** {', '.join(p['phone_numbers'][:3]) or 'Not found'}\n"
        report += f"- **Status:** {p['approval_status']} (requires verification)\n\n"

    report += f"""## Important Notes

> **ALL DATA REQUIRES MANUAL VERIFICATION BEFORE PUBLISHING**
> - Pricing data: Do NOT publish without sales team confirmation
> - RERA numbers: Verify on MahaRERA / relevant state authority portal
> - Project status (ongoing/completed): Verify with Abhinav Group
> - Phone numbers: Verify these are current sales contact numbers

## Crawl Errors

"""
    for err in crawl_errors[:20]:
        report += f"- `{err.get('url', '')}` — {err.get('error', '')}\n"

    with open(REPORTS_DIR / "extraction_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  extraction_report.md: written")

    # missing_information_report.md
    missing = f"""# Missing Information Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This report lists information that could not be automatically extracted.

## Information Requiring Manual Input from Abhinav Group

### Verified Pricing
The following pricing information was NOT found on the official website or is unverified:
- Samsara: Pricing page requires inquiry form
- Pebbles Greenfield: Pricing not publicly listed
- The Curve: Pricing not publicly listed

### RERA Registration Numbers
Please verify these RERA numbers extracted from the website on the official portal:
"""
    for p in projects:
        if p["rera_numbers"]:
            missing += f"- {p['project_name']}: {', '.join(p['rera_numbers'])} — verify at maharerait.maharashtra.gov.in\n"
        else:
            missing += f"- {p['project_name']}: RERA number not found on website — please provide\n"

    missing += """
### Project Status Confirmation Required
- Vatvriksha: Completed or ongoing phases?
- Pebbles Urbania: Completed or ongoing phases?
- Avaanti Residences: Is this an Abhinav Group project?

### Manual Inputs Required
1. Official brochure download links (behind inquiry forms)
2. Floor plan specifications and areas
3. Current possession dates
4. Official sales contact number confirmation
5. Brand hex color codes
"""
    with open(REPORTS_DIR / "missing_information_report.md", "w", encoding="utf-8") as f:
        f.write(missing)
    print(f"  missing_information_report.md: written")


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    crawl()
    projects = build_projects_json()
    write_outputs(projects)

    print(f"\n{'='*60}")
    print(f"  PHASE 3 COMPLETE")
    print(f"  Output: {DATA_DIR}")
    print(f"  Reports: {REPORTS_DIR}")
    print(f"{'='*60}")
