import os

def generate_draft(prospect, service, tone):
    domain=prospect.get("domain","your store")
    notes="; ".join(prospect.get("opportunities",[])[:2]) or "a few possible improvements"
    prompt=f"""Write a concise personalised cold email to the owner/operator of {domain}. Service: {service}. Tone: {tone}. Public scan observations: {notes}. 90-130 words, helpful, one low-friction CTA, no fabricated metrics, no claims about sales or revenue. Include subject line."""
    key=os.getenv("GEMINI_API_KEY")
    if key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            return genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt).text
        except Exception: pass
    return f"""Subject: A quick idea for {domain}

Hi there,

I came across {domain} while researching stores in your space. I noticed {notes.lower()} on the public pages I reviewed, and thought there may be an opportunity to make the customer journey clearer.

I help businesses with {service.lower()}. If this is on your roadmap, I’d be happy to share a couple of practical ideas tailored to your store.

Would a short conversation next week be useful?

Best,
[Your name]"""
