import re, json, os, csv, io, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, unquote
import requests
from bs4 import BeautifulSoup

HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
DB=os.path.join("data","prospects.json")
DISCOVERY_DIAGNOSTICS=[]
BLOCKED=("duckduckgo.com","bing.com","google.com","facebook.com","instagram.com","tiktok.com","youtube.com","pinterest.com","reddit.com","wikipedia.org","amazon.com","etsy.com")

def clean_url(url):
    url=url.strip()
    if not url.startswith(("http://","https://")): url="https://"+url
    if not urlparse(url).netloc: raise ValueError("Enter a valid store URL.")
    return url

def _result_url(href):
    if not href: return ""
    href=unquote(href); p=urlparse(href)
    if "uddg" in parse_qs(p.query):
        href=parse_qs(p.query)["uddg"][0]; p=urlparse(href)
    if p.scheme not in ("http","https") or not p.netloc: return ""
    domain=p.netloc.lower().removeprefix("www.").split(":")[0]
    if any(domain == d or domain.endswith("."+d) for d in BLOCKED): return ""
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$",domain): return ""
    return "https://"+domain

def _ddg(query, limit):
    r=requests.get("https://html.duckduckgo.com/html/",params={"q":query},headers=HEADERS,timeout=18)
    r.raise_for_status(); soup=BeautifulSoup(r.text,"html.parser")
    links=soup.select("a.result__a, a[data-testid='result-title-a']")
    if not links: links=soup.select(".result a[href], .web-result a[href]")
    out=[]
    for a in links:
        url=_result_url(a.get("href",""))
        if url:
            parent=a.find_parent(class_="result") or a.parent
            out.append({"url":url,"snippet":parent.get_text(" ",strip=True)[:350] if parent else ""})
        if len(out)>=limit: break
    return out

def _bing(query, limit):
    r=requests.get("https://www.bing.com/search",params={"q":query,"format":"rss"},headers=HEADERS,timeout=18)
    r.raise_for_status(); root=ET.fromstring(r.text); out=[]
    for item in root.findall(".//item"):
        url=_result_url(item.findtext("link",""))
        if url: out.append({"url":url,"snippet":item.findtext("description","")[:350]})
        if len(out)>=limit: break
    return out

def discover_stores(niche, market="", limit=10):
    global DISCOVERY_DIAGNOSTICS
    DISCOVERY_DIAGNOSTICS=[]
    niche=niche.strip(); market=market.strip()
    if not niche: return []
    queries=[f"{niche} Shopify store {market}".strip(),f"site:myshopify.com {niche} {market}".strip(),f"{niche} online shop {market}".strip()]
    results=[]; seen=set()
    for query in queries:
        for searcher in (_ddg,_bing):
            try:
                batch=searcher(query,limit)
                DISCOVERY_DIAGNOSTICS.append(f"{searcher.__name__}: HTTP success; {len(batch)} links parsed for query: {query}")
            except requests.RequestException as exc:
                DISCOVERY_DIAGNOSTICS.append(f"{searcher.__name__}: network/HTTP error: {type(exc).__name__}: {str(exc)[:180]}")
                continue
            except (ET.ParseError,ValueError) as exc:
                DISCOVERY_DIAGNOSTICS.append(f"{searcher.__name__}: response parsing error: {type(exc).__name__}: {str(exc)[:180]}")
                continue
            for item in batch:
                domain=urlparse(item["url"]).netloc.lower().removeprefix("www.")
                if domain in seen: continue
                seen.add(domain); results.append({"domain":domain,"url":item["url"],"snippet":item.get("snippet","")})
                if len(results)>=int(limit): return results
    return results

def audit_store(url):
    response=requests.get(clean_url(url),headers=HEADERS,timeout=20,allow_redirects=True)
    response.raise_for_status(); soup=BeautifulSoup(response.text,"html.parser"); html=response.text
    domain=urlparse(response.url).netloc.lower().removeprefix("www."); text=soup.get_text(" ",strip=True).lower()
    shopify=any(x in html.lower() for x in ["cdn.shopify.com","shopify.theme","myshopify.com"])
    emails=sorted(set(re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",html,re.I)))
    emails=[e for e in emails if not any(x in e.lower() for x in ["example.com","sentry.io","shopify.com"])]
    products=len(set(a.get("href") for a in soup.select('a[href*="/products/"]')))
    signals=[]; opportunities=[]; score=50
    if shopify: signals.append("Shopify technology signal detected")
    else: opportunities.append("Shopify platform could not be verified")
    if products: signals.append(f"{products} distinct product links found")
    else: opportunities.append("No product links detected on scanned homepage"); score+=8
    checks=[(("shipping","delivery"),"Shipping or delivery information not visible",10),(("return policy","returns","refund policy"),"Returns/refund information not visible",8),(("contact us","contact"),"Contact route not obvious",8),(("review","reviews","testimonial"),"Reviews/testimonials not visible",7)]
    for terms,label,points in checks:
        if not any(term in text for term in terms): opportunities.append(label+" on scanned page"); score+=points
    if emails: signals.append("Public email address detected")
    else: opportunities.append("No public business email detected on scanned page")
    if any(x in text for x in ["instagram","tiktok","facebook"]): signals.append("Social channel links or mentions detected")
    return {"domain":domain,"url":response.url,"is_shopify":shopify,"score":min(100,score),"product_count":products,"emails":emails,"signals":signals,"opportunities":opportunities,"audited_at":datetime.now(timezone.utc).isoformat()}

def load_prospects():
    try:
        with open(DB,encoding="utf-8") as f: return json.load(f)
    except (FileNotFoundError,ValueError,OSError): return []

def save_prospect(prospect):
    os.makedirs("data",exist_ok=True); items=load_prospects()
    items=[p for p in items if p.get("domain")!=prospect.get("domain")]; items.append(prospect)
    with open(DB,"w",encoding="utf-8") as f: json.dump(items,f,indent=2)
    return prospect

def export_csv(items):
    out=io.StringIO(); fields=["domain","url","is_shopify","score","product_count","emails","audited_at"]
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction="ignore"); writer.writeheader()
    for item in items:
        row=dict(item); row["emails"]="; ".join(row.get("emails",[])); writer.writerow(row)
    return out.getvalue()
