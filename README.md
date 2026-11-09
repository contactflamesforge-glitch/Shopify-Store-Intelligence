# Shopify Store Intelligence

A prospecting and public-storefront intelligence workspace for digital marketers, Shopify consultants and ecommerce agencies.

## What it does

- Discover candidate ecommerce storefronts by niche and market.
- Search with Exa or Brave Search when API keys are configured, with DuckDuckGo and Bing RSS fallbacks.
- Audit public homepage signals: Shopify technology markers, product links, page title/description, mobile viewport, trust/policy links and publicly listed email addresses.
- Prioritise visible improvement opportunities with a transparent heuristic score.
- Label storefront maturity signals without pretending to know the exact store launch date.
- Keep sales status explicitly **unknown** unless verified using owner-authorised data.
- Manage prospects through a pipeline, save notes and export CSV.
- Generate editable, draft-only cold outreach using observed audit findings.
- Store CRM records in SQLite.

## Search setup (recommended)

For reliable discovery, add at least one provider key to Streamlit Community Cloud:

1. Open the app's **Manage app → Settings → Secrets**.
2. Add one or both keys:

```toml
EXA_API_KEY = "your-exa-key"
BRAVE_SEARCH_API_KEY = "your-brave-search-key"
```

Exa and Brave are optional integrations; without them, the app tries DuckDuckGo and Bing RSS. Public search engines may rate-limit or block cloud-hosted requests, so results are not guaranteed without a supported API key.

Optional Gemini drafting:

```toml
GEMINI_API_KEY = "your-gemini-key"
GEMINI_MODEL = "gemini-2.5-flash"
```

Never commit keys to GitHub or paste them into chat.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Data persistence

The CRM uses SQLite at `data/prospects.db` by default. Set `SQLITE_PATH` to a persistent mounted volume when deploying to an environment that supports persistent disks. Streamlit Community Cloud's local filesystem may reset across app restarts/redeployments; use a managed database for durable production records.

## Important limits and responsible use

- Public website scans cannot establish sales, revenue, conversion rates, ad spend, traffic, profitability or exact store age.
- “Maturity” is a rough label based on visible storefront signals, not a launch-date claim.
- Shopify detection is based on public HTML markers and can be inconclusive.
- The opportunity score is a heuristic prioritisation aid, not a verified business diagnosis.
- Audit only publicly accessible pages, respect website terms and rate limits, and use business contact details published for business enquiries.
- Outreach is draft-only. This app does not send email.
- Shopify analytics require explicit store-owner authorisation.
