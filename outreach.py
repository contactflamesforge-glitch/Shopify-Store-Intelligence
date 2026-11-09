"""Editable, draft-only prospect outreach."""
import os


def generate_draft(prospect, service, tone):
    domain = prospect.get("domain", "your store")
    observations = prospect.get("opportunities", [])[:3]
    notes = "; ".join(observations) if observations else "a few areas worth reviewing"
    prompt = f"""Write a concise, human cold email to the owner/operator of {domain}.
Service: {service}. Tone: {tone}.
Only use these public scan observations: {notes}.
Write 90-130 words, include a subject line, one low-friction CTA, no fabricated metrics,
no claims about sales/revenue, and phrase observations cautiously as things noticed on
the publicly accessible page. Do not imply a full technical or conversion audit."""
    key = os.getenv("GEMINI_API_KEY")
    if key:
        try:
            from google import genai
            client = genai.Client(api_key=key)
            response = client.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), contents=prompt)
            if response.text:
                return response.text.strip()
        except Exception:
            pass
    return f"""Subject: A quick idea for {domain}

Hi there,

I came across {domain} while researching businesses in your space. On the public pages I reviewed, I noticed {notes.lower()}. These may be worth a closer look as you work to make the shopping experience as clear and reassuring as possible.

I help stores with {service.lower()}. If useful, I can share two practical suggestions based on what I noticed.

Would you be open to me sending those over?

Best,
[Your name]"""
