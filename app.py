import os
import pandas as pd
import pycountry
import streamlit as st
from dotenv import load_dotenv
from prospecting import (
    discover_stores, DISCOVERY_DIAGNOSTICS, audit_store, save_prospect,
    load_prospects, export_csv, update_prospect, find_public_emails,
)
from outreach import generate_draft

load_dotenv()
# Streamlit Community Cloud secrets are not automatically environment variables.
for secret_name in ("EXA_API_KEY", "BRAVE_SEARCH_API_KEY", "GEMINI_API_KEY", "GEMINI_MODEL", "SQLITE_PATH"):
    try:
        if secret_name in st.secrets and not os.getenv(secret_name):
            os.environ[secret_name] = str(st.secrets[secret_name])
    except Exception:
        pass

st.set_page_config(page_title="Shopify Store Intelligence", page_icon="🛍️", layout="wide")
st.markdown("""
<style>
.stApp{background:radial-gradient(ellipse at 12% 0%,#172554 0,#090d19 46%,#070a12 100%)}
.block-container{padding-top:1.6rem;max-width:1500px}
.hero{padding:1.5rem 1.8rem;border:1px solid #263653;border-radius:20px;background:linear-gradient(120deg,#111c35,#101827);margin-bottom:1.2rem}
.hero h1{margin:0;font-size:2.25rem;letter-spacing:-1px}.hero p{color:#a8b7ce;margin:.45rem 0 0}
div[data-testid="stMetric"]{background:#101a2b;border:1px solid #263653;padding:14px;border-radius:14px}
section[data-testid="stSidebar"]{background:#0b1220}
.small-muted{color:#9aa9bf;font-size:.9rem}
</style>
<div class="hero"><h1>🛍️ SHOPIFY STORE INTELLIGENCE</h1><p>Discover stores. Diagnose public storefront signals. Prioritise better prospects.</p></div>
""", unsafe_allow_html=True)

STATUSES = ["New", "Audited", "Qualified", "Contacted", "Replied", "Interested", "Client", "Not Interested"]
COUNTRIES = ["Any country"] + sorted(country.name for country in pycountry.countries)
NICHES = ["All niches","Apparel & Clothing","Accessories","Shoes & Footwear","Jewelry & Watches","Beauty & Skincare","Haircare","Makeup & Cosmetics","Health & Wellness","Fitness & Sports Nutrition","Supplements","Food & Beverage","Coffee & Tea","Pet Supplies","Baby & Kids","Toys & Games","Home & Living","Furniture","Home Decor","Kitchen & Dining","Garden & Outdoor","Electronics","Consumer Technology","Phones & Accessories","Computers & Gaming","Smart Home","Automotive","Travel & Luggage","Bags & Backpacks","Sports & Outdoors","Camping & Hiking","Arts & Crafts","Books & Stationery","Office Supplies","Hobbies & Collectibles","Personalised Gifts","Luxury Goods","Sustainable & Eco Products","Men's Fashion","Women's Fashion","Streetwear","Vintage & Resale","Wedding & Events","Industrial & B2B","Digital Products"]

if "discovered" not in st.session_state: st.session_state["discovered"] = []
if "last_audit" not in st.session_state: st.session_state["last_audit"] = None

prospects = load_prospects()
st.sidebar.title("Command centre")
st.sidebar.success("Workspace online")
st.sidebar.caption("Search providers")
st.sidebar.write("Exa: " + ("Connected" if os.getenv("EXA_API_KEY") else "Not configured"))
st.sidebar.write("Brave: " + ("Connected" if os.getenv("BRAVE_SEARCH_API_KEY") else "Not configured"))
st.sidebar.write("Fallback: DuckDuckGo + Bing RSS")
st.sidebar.caption("Add EXA_API_KEY or BRAVE_SEARCH_API_KEY in Streamlit → Manage app → Settings → Secrets for more reliable discovery.")
st.sidebar.divider()
st.sidebar.caption("Public scans cannot prove sales, revenue, conversion rates or exact store age. Sales status remains unknown unless owner-authorised data is connected.")

tabs = st.tabs(["📊 Overview", "🔎 Store Discovery", "🧠 Store Audit", "📇 Prospect CRM", "✉️ Outreach Studio"])

with tabs[0]:
    st.subheader("Your prospecting pipeline")
    prospects = load_prospects()
    a,b,c,d,e = st.columns(5)
    a.metric("Saved stores", len(prospects))
    b.metric("Shopify signals", sum(bool(p.get("is_shopify")) for p in prospects))
    c.metric("Need attention", sum(bool(p.get("opportunities")) for p in prospects))
    d.metric("Qualified", sum(p.get("status") == "Qualified" for p in prospects))
    e.metric("With public email", sum(bool(p.get("emails")) for p in prospects))
    if prospects:
        chart = pd.DataFrame([{"Status": p.get("status","New"), "Stores": 1} for p in prospects])
        st.markdown("#### Pipeline by status")
        st.bar_chart(chart.groupby("Status")["Stores"].sum())
        st.markdown("#### Highest opportunity scores")
        ranked = sorted(prospects, key=lambda p: int(p.get("score",0)), reverse=True)[:8]
        st.dataframe(pd.DataFrame([{"Store":p.get("domain"),"Score":p.get("score"),"Status":p.get("status"),"Maturity signals":p.get("maturity")} for p in ranked]), use_container_width=True, hide_index=True)
    else:
        st.info("Your pipeline is empty. Start by discovering or auditing a storefront.")

with tabs[1]:
    st.subheader("Discover public storefront candidates")
    left,right = st.columns(2)
    niche = left.selectbox("Shopify niche / product category", NICHES)
    market = right.selectbox("Target country", COUNTRIES, index=COUNTRIES.index("United States"))
    limit = st.select_slider("Number of Shopify stores to find", options=[5,10,20,30,50], value=10)
    st.caption("Directories, agencies and case studies are filtered out. Only public Shopify storefront signals are shown.")
    if st.button("🔍 Discover Shopify stores", type="primary", use_container_width=True):
        selected_niche = "" if niche == "All niches" else niche
        selected_market = "" if market == "Any country" else market
        with st.spinner(f"Searching for up to {limit} verified Shopify storefronts…"):
            st.session_state["discovered"] = discover_stores(selected_niche, selected_market, limit)
            for candidate in st.session_state["discovered"]:
                candidate["emails"] = find_public_emails(candidate["url"])
        count = len(st.session_state["discovered"])
        if count >= limit: st.success(f"Found {count} Shopify storefront candidates.")
        elif count: st.warning(f"Found {count} verified Shopify stores, not {limit}. No unverified results were added to pad the list.")
        else: st.warning("No verified Shopify stores found. Try another category or country.")
    if DISCOVERY_DIAGNOSTICS:
        with st.expander("Search diagnostics", expanded=not st.session_state["discovered"]):
            for line in DISCOVERY_DIAGNOSTICS: st.write("• " + line)
    for item in st.session_state.get("discovered", []):
        with st.container(border=True):
            x,y = st.columns([5,1])
            x.markdown(f"**{item['domain']}**  \n{item['url']}  \n{item.get('snippet','')}")
            x.markdown("**Public email:** " + (", ".join(item.get("emails", [])) or "Not found on public pages"))
            if y.button("Audit & save", key="discover_"+item["domain"]):
                try:
                    with st.spinner("Auditing public storefront…"):
                        result = audit_store(item["url"])
                    save_prospect(result)
                    st.success(f"Saved {item['domain']} to CRM.")
                except Exception as exc: st.error(f"Audit failed: {exc}")

with tabs[2]:
    st.subheader("Run a public storefront audit")
    url = st.text_input("Store URL", placeholder="https://example.com")
    if st.button("Run intelligence audit", type="primary"):
        try:
            with st.spinner("Inspecting homepage HTML and public storefront signals…"):
                st.session_state["last_audit"] = audit_store(url)
        except Exception as exc:
            st.error(f"Could not audit this URL: {exc}")
    result = st.session_state.get("last_audit")
    if result:
        st.markdown(f"### {result['domain']} — {'🟢 Shopify signals found' if result['is_shopify'] else '🟠 Shopify not verified'}")
        x,y,z,w = st.columns(4)
        x.metric("Opportunity score", f"{result['score']}/100")
        y.metric("Product links", result["product_count"])
        z.metric("Public emails", len(result["emails"]))
        w.metric("Maturity signals", result["maturity"].split()[0])
        st.info(result["sales_status"])
        st.markdown("**Observed opportunities**")
        if result["opportunities"]:
            for issue in result["opportunities"]: st.write("• " + issue)
        else: st.write("No obvious issues detected by this limited homepage scan.")
        st.markdown("**Positive signals**")
        for signal in result["signals"]: st.write("• " + signal)
        st.write("**Public contact details:** " + (", ".join(result["emails"]) or "No public email detected"))
        st.write("**Page title:** " + (result.get("title") or "Not detected"))
        st.write("**Meta description:** " + (result.get("description") or "Not detected"))
        if st.button("💾 Save audit to CRM"):
            save_prospect(result); st.success("Saved to Prospect CRM.")

with tabs[3]:
    st.subheader("Prospect relationship manager")
    prospects = load_prospects()
    if prospects:
        filter_status = st.selectbox("Filter pipeline", ["All"] + STATUSES)
        shown = [p for p in prospects if filter_status == "All" or p.get("status","New") == filter_status]
        table = [{"Store":p.get("domain"),"Score":p.get("score",0),"Shopify": "Yes" if p.get("is_shopify") else "Unverified","Maturity":p.get("maturity","Unknown"),"Status":p.get("status","New"),"Email":", ".join(p.get("emails",[]))} for p in shown]
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        chosen = st.selectbox("Edit a prospect", [p["domain"] for p in prospects])
        selected = next(p for p in prospects if p["domain"] == chosen)
        current_status = selected.get("status","New")
        status = st.selectbox("Pipeline status", STATUSES, index=STATUSES.index(current_status) if current_status in STATUSES else 0)
        notes = st.text_area("Notes", value=selected.get("notes",""), key="notes_"+chosen)
        if st.button("Save CRM changes"):
            update_prospect(chosen, status=status, notes=notes); st.success("Prospect updated."); st.rerun()
        st.download_button("⬇️ Export all prospects (CSV)", export_csv(prospects), "shopify_prospects.csv", "text/csv")
    else:
        st.info("No prospects saved yet. Use Store Discovery or Store Audit.")

with tabs[4]:
    st.subheader("Personalised, draft-only outreach")
    prospects = load_prospects()
    if prospects:
        domains = [p.get("domain","Unknown") for p in prospects]
        selected_domain = st.selectbox("Choose a prospect", domains)
        prospect = next(p for p in prospects if p.get("domain") == selected_domain)
        service = st.text_input("Your service / offer", "Shopify conversion optimisation and digital marketing")
        tone = st.selectbox("Writing style", ["Friendly and consultative", "Direct and concise", "Expert and analytical"])
        if st.button("Generate personalised email", type="primary"):
            with st.spinner("Preparing a draft using observed audit findings…"):
                st.session_state["draft"] = generate_draft(prospect, service, tone)
        if st.session_state.get("draft"):
            st.text_area("Edit before using", st.session_state["draft"], height=300)
            st.caption("Draft only. Verify every observation and recipient. No email is sent by this app.")
    else:
        st.info("Save at least one prospect before generating outreach.")
