import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from prospecting import discover_stores, audit_store, save_prospect, load_prospects, export_csv
from outreach import generate_draft

load_dotenv()
st.set_page_config(page_title="Shopify Store Intelligence",page_icon="🛍️",layout="wide")
st.markdown("""
<style>
.stApp{background:radial-gradient(ellipse at 15% 0%,#172554 0,#090d19 44%,#070a12 100%)}
.block-container{padding-top:2rem;max-width:1500px}
.hero{padding:1.5rem 1.8rem;border:1px solid #263653;border-radius:18px;background:linear-gradient(120deg,#111c35,#101827);margin-bottom:1.2rem}
.hero h1{margin:0;font-size:2.2rem;letter-spacing:-1px}.hero p{color:#a8b7ce;margin:.4rem 0 0}
div[data-testid="stMetric"]{background:#101a2b;border:1px solid #263653;padding:14px;border-radius:14px}
</style>
<div class="hero"><h1>🛍️ SHOPIFY STORE INTELLIGENCE</h1><p>Discover storefronts. Detect opportunities. Start better conversations.</p></div>
""",unsafe_allow_html=True)
tabs=st.tabs(["🔎 Store Discovery","🧠 Store Audit","📇 Prospect CRM","✉️ Outreach Studio"])
with tabs[0]:
 st.subheader("Find Shopify stores")
 c1,c2,c3=st.columns([2,1,1])
 niche=c1.text_input("Niche / product category",placeholder="e.g. skincare, fitness accessories")
 market=c2.text_input("Market",placeholder="e.g. United States")
 limit=c3.selectbox("Results",[5,10,20],index=1)
 st.caption("Search results are candidates only. Audit each store to verify available Shopify signals.")
 if st.button("Discover stores",type="primary",use_container_width=True):
  if not niche.strip(): st.warning("Enter a niche first.")
  else:
   with st.spinner("Searching public web results…"): st.session_state["discovered"]=discover_stores(niche,market,limit)
   st.success(f"Found {len(st.session_state['discovered'])} candidates.")
 for item in st.session_state.get("discovered",[]):
  with st.container(border=True):
   a,b=st.columns([4,1]); a.markdown(f"**{item['domain']}**  \n{item['url']}  \n{item.get('snippet','')}")
   if b.button("Audit & save",key="candidate_"+item["domain"]):
    try:
     with st.spinner("Auditing public storefront…"): result=audit_store(item["url"])
     if result["is_shopify"]: save_prospect(result); st.success("Saved "+item["domain"])
     else: st.warning("Shopify could not be verified from the public page.")
    except Exception as e: st.error(f"Audit failed: {e}")
with tabs[1]:
 st.subheader("Audit a storefront")
 url=st.text_input("Store URL",placeholder="https://example.com")
 if st.button("Run store intelligence audit",type="primary"):
  try:
   with st.spinner("Inspecting public storefront…"): st.session_state["last_audit"]=audit_store(url)
  except Exception as e: st.error(f"Could not audit this URL: {e}")
 result=st.session_state.get("last_audit")
 if result:
  st.markdown(f"### {result['domain']} — {'🟢 Shopify signal found' if result['is_shopify'] else '🟠 Shopify not verified'}")
  x,y,z=st.columns(3); x.metric("Opportunity score",f"{result['score']}/100"); y.metric("Product links",result["product_count"]); z.metric("Public emails",len(result["emails"]))
  st.write("**Observed opportunities**")
  for issue in result["opportunities"]: st.write("• "+issue)
  st.write("**Public contact details**"); st.write(", ".join(result["emails"]) or "No public email detected")
  st.write("**Evidence**"); st.caption(" · ".join(result["signals"]) or "No additional signals")
  if st.button("Save to prospect CRM"): save_prospect(result); st.success("Prospect saved.")
with tabs[2]:
 st.subheader("Prospect pipeline")
 prospects=load_prospects(); x,y,z=st.columns(3)
 x.metric("Saved stores",len(prospects)); y.metric("Shopify signals",sum(bool(p.get("is_shopify")) for p in prospects)); z.metric("With public emails",sum(bool(p.get("emails")) for p in prospects))
 if prospects:
  df=pd.DataFrame(prospects); cols=[c for c in ["domain","url","score","product_count","emails","audited_at"] if c in df.columns]
  st.dataframe(df[cols],use_container_width=True,hide_index=True)
  st.download_button("Export prospects CSV",export_csv(prospects),"shopify_prospects.csv","text/csv")
 else: st.info("No prospects yet. Discover or audit stores to build your pipeline.")
with tabs[3]:
 st.subheader("Personalised cold outreach")
 prospects=load_prospects()
 if prospects:
  names=[p.get("domain","Unknown") for p in prospects]; selected=st.selectbox("Choose a prospect",names); prospect=prospects[names.index(selected)]
  service=st.text_input("Your service / offer","Shopify conversion optimisation and digital marketing")
  tone=st.selectbox("Tone",["Friendly and consultative","Direct and concise","Expert and analytical"])
  if st.button("Generate email draft",type="primary"):
   with st.spinner("Preparing a tailored draft…"): st.session_state["draft"]=generate_draft(prospect,service,tone)
  if st.session_state.get("draft"): st.text_area("Editable email draft",st.session_state["draft"],height=300); st.caption("Draft only. Verify observations and recipient before sending.")
 else: st.info("Save at least one prospect before generating outreach.")
st.sidebar.title("Command centre"); st.sidebar.success("Independent workspace")
st.sidebar.write("AI drafting: "+("configured" if os.getenv("GEMINI_API_KEY") else "template mode"))
st.sidebar.caption("Public scans do not reveal sales, revenue, conversion rate or exact store age.")
