"""Public Shopify prospect discovery, auditing and SQLite-backed CRM."""
import csv
import io
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StoreIntelligence/1.0; +https://example.com/bot)"}
DB_PATH = os.getenv("SQLITE_PATH", os.path.join("data", "prospects.db"))
DISCOVERY_DIAGNOSTICS = []
BLOCKED = ("duckduckgo.com", "bing.com", "google.com", "facebook.com", "instagram.com",
           "tiktok.com", "youtube.com", "pinterest.com", "reddit.com", "wikipedia.org",
           "amazon.com", "etsy.com", "aliexpress.com", "findniche.com", "gempages.net",
           "sellercenter.io", "storeinspect.com", "eachspy.com", "storeleads.app",
           "builtwith.com", "similarweb.com", "commerceinspector.com", "bluecreativeus.com", "vtlabs.org")


def clean_url(url):
    value = (url or "").strip()
    if not value:
        raise ValueError("Enter a store URL.")
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Enter a valid http(s) store URL.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed.")
    return value


def _result_url(href):
    if not href:
        return ""
    href = unquote(href.strip())
    parsed = urlparse(href)
    if "uddg" in parse_qs(parsed.query):
        href = parse_qs(parsed.query)["uddg"][0]
        parsed = urlparse(href)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    domain = parsed.hostname.lower().removeprefix("www.")
    if any(domain == item or domain.endswith("." + item) for item in BLOCKED):
        return ""
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
        return ""
    return "https://" + domain


def _exa_search(query, limit):
    key = os.getenv("EXA_API_KEY")
    if not key:
        return []
    response = requests.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": key, "Content-Type": "application/json"},
        json={"query": query, "type": "auto", "numResults": min(limit, 25),
              "contents": {"text": {"maxCharacters": 500}}},
        timeout=25,
    )
    response.raise_for_status()
    data = response.json()
    return [{"url": item.get("url", ""), "snippet": item.get("text", "")[:350]}
            for item in data.get("results", [])]


def _brave_search(query, limit):
    key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not key:
        return []
    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": min(limit, 20)},
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    return [{"url": item.get("url", ""), "snippet": item.get("description", "")}
            for item in response.json().get("web", {}).get("results", [])]


def _ddg(query, limit):
    response = requests.get("https://html.duckduckgo.com/html/", params={"q": query},
                            headers=HEADERS, timeout=18)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.select("a.result__a, a[data-testid='result-title-a']")
    if not links:
        links = soup.select(".result a[href], .web-result a[href]")
    found = []
    for anchor in links:
        url = _result_url(anchor.get("href", ""))
        if url:
            parent = anchor.find_parent(class_="result") or anchor.parent
            found.append({"url": url, "snippet": parent.get_text(" ", strip=True)[:350] if parent else ""})
        if len(found) >= limit:
            break
    return found


def _bing(query, limit):
    response = requests.get("https://www.bing.com/search",
                            params={"q": query, "format": "rss"}, headers=HEADERS, timeout=18)
    response.raise_for_status()
    from xml.etree import ElementTree
    root = ElementTree.fromstring(response.text)
    found = []
    for item in root.findall(".//item"):
        url = _result_url(item.findtext("link", ""))
        if url:
            found.append({"url": url, "snippet": item.findtext("description", "")[:350]})
        if len(found) >= limit:
            break
    return found


def _verify_shopify_store(url):
    """Check public homepage HTML for Shopify and real product/cart evidence."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if response.status_code >= 400 or len(response.content) > 4_000_000:
            return False
        html = response.text.lower()
        soup = BeautifulSoup(response.text, "html.parser")
        markers = ("cdn.shopify.com", "shopify.theme", "shopify-section",
                   "myshopify.com", "shopify-payment-button", "shopify-buy")
        platform = any(marker in html for marker in markers)
        commerce = bool(soup.select('a[href*="/products/"]')) or any(
            token in html for token in ("/cart", "cart-drawer", "cart-notification"))
        return platform and commerce
    except requests.RequestException:
        return False


def discover_stores(niche, market="", limit=10):
    DISCOVERY_DIAGNOSTICS.clear()
    niche, market = (niche or "").strip(), (market or "").strip()
    limit = max(1, min(int(limit), 50))
    location = f" in {market}" if market else ""
    category = niche if niche else "online retail"
    queries = [
        f"{category} Shopify store{location} official online shop",
        f"{category} brand shop Shopify{location} buy online",
        f"Shopify {category} store{location} shop now",
        f"site:myshopify.com {category}{location}",
        f"{category} independent ecommerce store powered by Shopify{location}",
    ]
    providers = []
    if os.getenv("EXA_API_KEY"):
        providers.append(("Exa", _exa_search))
    if os.getenv("BRAVE_SEARCH_API_KEY"):
        providers.append(("Brave Search", _brave_search))
    providers.extend([("DuckDuckGo", _ddg), ("Bing RSS", _bing)])
    candidates, seen = [], set()
    for query in queries:
        for name, searcher in providers:
            try:
                batch = searcher(query, min(limit * 3, 50))
                DISCOVERY_DIAGNOSTICS.append(f"{name}: {len(batch)} raw results for “{query}”.")
                for item in batch:
                    url = _result_url(item.get("url", ""))
                    if not url:
                        continue
                    domain = urlparse(url).hostname.lower().removeprefix("www.")
                    if domain in seen:
                        continue
                    seen.add(domain)
                    candidates.append({"domain": domain, "url": url, "snippet": item.get("snippet", "")})
            except requests.RequestException as exc:
                DISCOVERY_DIAGNOSTICS.append(f"{name}: request failed ({type(exc).__name__}: {str(exc)[:140]}).")
            except (ValueError, KeyError, TypeError) as exc:
                DISCOVERY_DIAGNOSTICS.append(f"{name}: could not parse response ({type(exc).__name__}).")
            time.sleep(0.12)
    verified = []
    for candidate in candidates:
        if _verify_shopify_store(candidate["url"]):
            verified.append(candidate)
            DISCOVERY_DIAGNOSTICS.append(f"Verified Shopify storefront: {candidate['domain']}.")
            if len(verified) >= limit:
                break
        else:
            DISCOVERY_DIAGNOSTICS.append(f"Skipped non-store or unverified result: {candidate['domain']}.")
    if not verified:
        DISCOVERY_DIAGNOSTICS.append("No candidates passed public Shopify verification. Results are not padded with directories or case studies.")
    elif len(verified) < limit:
        DISCOVERY_DIAGNOSTICS.append(f"Only {len(verified)} of {limit} requested stores passed verification.")
    return verified


def _has_link(soup, words):
    for anchor in soup.find_all("a", href=True):
        label = (anchor.get_text(" ", strip=True) + " " + anchor["href"]).lower()
        if any(word in label for word in words):
            return True
    return False


def find_public_emails(url, max_pages=4):
    """Find publicly displayed business contact emails on a storefront and its contact pages."""
    target = clean_url(url)
    try:
        response = requests.get(target, headers=HEADERS, timeout=18, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException:
        return []
    base_host = (urlparse(response.url).hostname or "").lower().removeprefix("www.")
    pages = [(response.url, response.text[:2_000_000])]
    soup = BeautifulSoup(response.text, "html.parser")
    contact_links = []
    from urllib.parse import urljoin
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        label = (anchor.get_text(" ", strip=True) + " " + href).lower()
        if any(word in label for word in ("contact", "about", "support", "help", "customer service")):
            page_url = urljoin(response.url, href)
            parsed = urlparse(page_url)
            host = (parsed.hostname or "").lower().removeprefix("www.")
            if parsed.scheme in ("http", "https") and host == base_host and page_url not in [x[0] for x in pages + contact_links]:
                contact_links.append((page_url, ""))
    for page_url, _ in contact_links[:max(0, max_pages - 1)]:
        try:
            page = requests.get(page_url, headers=HEADERS, timeout=12, allow_redirects=True)
            final_host = (urlparse(page.url).hostname or "").lower().removeprefix("www.")
            if page.status_code < 400 and final_host == base_host:
                pages.append((page.url, page.text[:2_000_000]))
        except requests.RequestException:
            continue
    found = set()
    for page_url, html in pages:
        page_soup = BeautifulSoup(html, "html.parser")
        for anchor in page_soup.select('a[href^="mailto:"]'):
            address = anchor.get("href", "").split(":", 1)[-1].split("?", 1)[0].strip()
            if address:
                found.add(address)
        found.update(re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}", html, re.I))
    return sorted(email for email in found if not any(x in email.lower() for x in
        ("example.com", "sentry.io", "shopify.com", "wixpress.com", "cloudflare.com"))
        and len(email) <= 254)


def audit_store(url):
    target = clean_url(url)
    response = requests.get(target, headers=HEADERS, timeout=25, allow_redirects=True)
    response.raise_for_status()
    if len(response.content) > 5_000_000:
        raise ValueError("The page is too large to safely audit.")
    soup = BeautifulSoup(response.text, "html.parser")
    html = response.text
    text = soup.get_text(" ", strip=True).lower()
    domain = urlparse(response.url).hostname.lower().removeprefix("www.")
    lower_html = html.lower()
    shopify = any(token in lower_html for token in ("cdn.shopify.com", "shopify.theme", "myshopify.com", "shopify-section"))
    emails = find_public_emails(response.url)
    products = len({a.get("href", "").split("?")[0] for a in soup.select('a[href*="/products/"]') if a.get("href")})
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        description = (meta.get("content") or "").strip()
    viewport = bool(soup.find("meta", attrs={"name": "viewport"}))
    checks = [
        (("shipping", "delivery"), "Shipping information not obvious on the scanned page", 8),
        (("return policy", "returns", "refund policy"), "Returns/refund information not obvious on the scanned page", 8),
        (("contact us", "contact"), "Contact route not obvious on the scanned page", 7),
        (("review", "reviews", "testimonial"), "Reviews/testimonials not obvious on the scanned page", 7),
    ]
    signals, opportunities, score = [], [], 35
    if shopify:
        signals.append("Shopify technology markers found in page source")
        score += 15
    else:
        opportunities.append("Shopify platform was not verified from the scanned page")
    if products:
        signals.append(f"{products} distinct product links detected")
        score += min(15, products)
    else:
        opportunities.append("No product links detected on the scanned homepage")
        score += 8
    if title:
        signals.append("Page title is present")
    else:
        opportunities.append("Homepage title is missing")
        score += 5
    if description:
        signals.append("Meta description is present")
    else:
        opportunities.append("Meta description is missing")
        score += 5
    if viewport:
        signals.append("Mobile viewport metadata is present")
    else:
        opportunities.append("Mobile viewport metadata is missing")
        score += 5
    for terms, label, points in checks:
        if not any(term in text for term in terms) and not _has_link(soup, terms):
            opportunities.append(label)
            score += points
        else:
            signals.append(label.replace("not obvious", "detected"))
    if emails:
        signals.append("Public email address detected")
    else:
        opportunities.append("No public business email detected in scanned HTML")
    if any(x in lower_html for x in ("instagram.com", "tiktok.com", "facebook.com")):
        signals.append("Social profile links detected")
    maturity = "Insufficient public signals"
    if products >= 30 and len(signals) >= 5:
        maturity = "More developed storefront signals"
    elif products >= 5 or len(signals) >= 4:
        maturity = "Some established storefront signals"
    else:
        maturity = "Lean or early-stage storefront signals"
    score = max(0, min(100, score))
    return {
        "domain": domain, "url": response.url, "is_shopify": shopify, "score": score,
        "product_count": products, "emails": emails, "signals": signals,
        "opportunities": opportunities, "title": title, "description": description,
        "maturity": maturity, "status": "New", "notes": "",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "sales_status": "Unknown — public scans cannot verify sales",
    }


def _connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("""CREATE TABLE IF NOT EXISTS prospects (
        domain TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New',
        notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
    )""")
    return connection


def load_prospects():
    with _connect() as db:
        rows = db.execute("SELECT payload,status,notes FROM prospects ORDER BY updated_at DESC").fetchall()
    items = []
    for row in rows:
        try:
            item = json.loads(row["payload"])
            item["status"], item["notes"] = row["status"], row["notes"]
            items.append(item)
        except (ValueError, TypeError):
            continue
    return items


def save_prospect(prospect):
    domain = prospect.get("domain")
    if not domain:
        raise ValueError("Prospect is missing its domain.")
    existing = next((p for p in load_prospects() if p.get("domain") == domain), {})
    merged = {**existing, **prospect}
    status = merged.get("status", "New")
    notes = merged.get("notes", "")
    with _connect() as db:
        db.execute("""INSERT INTO prospects(domain,payload,status,notes,updated_at)
            VALUES(?,?,?,?,?) ON CONFLICT(domain) DO UPDATE SET
            payload=excluded.payload,status=excluded.status,notes=excluded.notes,updated_at=excluded.updated_at""",
            (domain, json.dumps(merged), status, notes, datetime.now(timezone.utc).isoformat()))
    return merged


def update_prospect(domain, status=None, notes=None):
    items = {p["domain"]: p for p in load_prospects()}
    if domain not in items:
        raise ValueError("Prospect not found.")
    item = items[domain]
    if status is not None:
        item["status"] = status
    if notes is not None:
        item["notes"] = notes
    return save_prospect(item)


def export_csv(items):
    output = io.StringIO()
    fields = ["domain", "url", "is_shopify", "score", "product_count", "maturity",
              "sales_status", "emails", "status", "notes", "audited_at"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        row = dict(item)
        row["emails"] = "; ".join(row.get("emails", []))
        writer.writerow(row)
    return output.getvalue()
