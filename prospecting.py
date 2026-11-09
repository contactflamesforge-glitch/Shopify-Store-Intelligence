import re, json, os, csv, io
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

HEADERS={"User-Agent":"Mozilla/5.0 (compatible; StoreIntelligenceAudit/1.0)"}
DB=os.path.join("data","prospects.json")

def clean_url(url):
    url=url.strip()
    if not url.startswith(("http://","https://")): url="https://"+url
    if not urlparse(url).netloc: raise ValueError("Enter a valid store URL.")
    return url

def discover_stores(niche, market="", limit=10):
    query=f'"myshopify.com" {niche} {market} store'
    try:
        response=requests.get("https://html.duckduckgo.com/html/",params={"q":query},headers=HEADERS,timeout=20)
        response.raise_for_status()
        soup=BeautifulSoup(response.text,"html.parser")
        results=[]; seen=set()
        for link in soup.select("a.result__a"):
            href=link.get("href","")
            if "uddg=" in href: href=parse_qs(urlparse(href).query).get("uddg",[href])[0]
            domain=urlparse(href).netloc.lower().removeprefix("www.")
            if not domain or domain in seen or any(x in domain for x in ["duckduckgo.com","facebook.com","instagram.com"]): continue
            seen.add(domain); parent=link.find_parent(class_="result")
            snippet=parent.select_one(".result__snippet").get_text(" ",strip=True) if parent and parent.select_one(".result__snippet") else ""
            results.append({"domain":domain,"url":"https://"+domain,"snippet":snippet})
            if len(results)>=limit: break
        return results
    except requests.RequestException: return []

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
    checks=[(("shipping","delivery"),"Shipping or delivery information not visible",10),
            (("return policy","returns","refund policy"),"Returns/refund information not visible",8),
            (("contact us","contact"),"Contact route not obvious",8),
            (("review","reviews","testimonial"),"Reviews/testimonials not visible",7)]
    for terms,label,points in checks:
        if not any(term in text for term in terms): opportunities.append(label+" on scanned page"); score+=points
    if emails: signals.append("Public email address detected")
    else: opportunities.append("No public business email detected on scanned page")
    if any(x in text for x in ["instagram","tiktok","facebook"]): signals.append("Social channel links or mentions detected")
    return {"domain":domain,"url":response.url,"is_shopify":shopify,"score":min(100,score),"product_count":products,
            "emails":emails,"signals":signals,"opportunities":opportunities,"audited_at":datetime.now(timezone.utc).isoformat()}

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
