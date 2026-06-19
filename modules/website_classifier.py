import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def classify_website(url: str, page_text: str) -> dict:
    page_text = page_text[:5000] if page_text else ""

    prompt = f"""
You are helping a Taiwanese trading company find overseas beauty / hair care brands for distribution rights.

The company wants BRAND AGENCY opportunities, not OEM or manufacturing.

Website URL:
{url}

Website Content:
{page_text}

Keep ONLY if the website is:
- an official brand website
- an independent hair care brand
- an organic / natural beauty brand
- a professional salon hair care brand
- a brand that may be suitable for Taiwan distribution or agency rights

Reject if the website is:
- OEM manufacturer
- ODM manufacturer
- private label manufacturer
- distributor
- wholesaler
- retailer
- marketplace
- media website
- blog
- social media
- exhibition organizer
- regulatory consultant
- data platform
- government site

Return ONLY valid JSON:

{{
  "is_candidate": true,
  "site_type": "brand",
  "agency_fit_score": 85,
  "country": "France",
  "reason": "Official French organic hair care brand suitable for distribution."
}}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "You classify websites for brand distribution opportunities. Return only valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "is_candidate": False,
            "site_type": "parse_error",
            "agency_fit_score": 0,
            "country": "",
            "reason": content[:300]
        }