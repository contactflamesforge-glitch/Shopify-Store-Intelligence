# Shopify Store Intelligence

An independent prospecting workspace for discovering and auditing public Shopify storefronts, finding publicly listed business contact details, prioritising observable growth opportunities, and drafting personalised outreach.

## Features
- Search public Shopify store candidates by niche and market.
- Audit storefronts for Shopify signals, product links, trust/conversion elements and public emails.
- Transparent opportunity scoring based on visible evidence—not guessed revenue or sales.
- Save prospects locally, export CSV, and generate editable cold-email drafts.
- Optional Gemini-powered outreach drafts.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Set `GEMINI_API_KEY` as an environment secret to enable AI drafting. Never commit API keys.

## Responsible use
Only scan publicly accessible pages, respect site terms and rate limits, and use business contact details published for business enquiries. Outreach is draft-only. Public scans cannot establish sales, revenue, conversion rate, or exact store age. Shopify analytics require explicit store-owner authorization and are not inferred from public scanning.
