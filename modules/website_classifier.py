import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from modules.search_profile import SearchProfile


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def format_list(values: list[str]) -> str:
    cleaned = [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]

    if not cleaned:
        return "(not specified)"

    return ", ".join(cleaned)


def classify_website(
    url: str,
    page_text: str,
    search_profile: SearchProfile,
) -> dict:
    """
    根據使用者本次 SearchProfile 判斷網站是否為候選。

    此模組不再固定認定：
    - shampoo
    - hair care
    - organic
    - natural
    - Europe

    實際條件都由 search_profile 傳入。
    """

    page_text = (
        page_text[:5000]
        if page_text
        else ""
    )

    product_keywords = format_list(
        search_profile.product_keywords
    )

    positioning_keywords = format_list(
        search_profile.positioning_keywords
    )

    excluded_keywords = format_list(
        search_profile.excluded_keywords
    )

    included_countries = format_list(
        search_profile.included_countries
    )

    included_regions = format_list(
        search_profile.included_regions
    )

    excluded_countries = format_list(
        search_profile.excluded_countries
    )

    prompt = f"""
You are helping a Taiwanese trading company evaluate overseas brands
for possible distribution or agency rights.

USER SEARCH REQUEST:
{search_profile.query}

TARGET PRODUCT CONCEPTS:
{product_keywords}

DESIRED BRAND POSITIONING:
{positioning_keywords}

INCLUDED COUNTRIES:
{included_countries}

INCLUDED REGIONS:
{included_regions}

EXCLUDED COUNTRIES:
{excluded_countries}

EXCLUDED CONTENT OR BUSINESS TYPES:
{excluded_keywords}

Website URL:
{url}

Website Content:
{page_text}

Evaluate whether this website matches the user's current search request.

Keep only when:
- it is an official website for a brand or brand owner
- its products meaningfully match the target product concepts
- its positioning meaningfully matches the desired positioning,
  when positioning requirements were provided
- it is potentially suitable for Taiwan distribution or agency rights
- its country does not conflict with the user's country settings

Reject when:
- it is a retailer, marketplace, media site, blog or social platform
- it is an exhibition organizer, consultant, data platform or government site
- it clearly matches an excluded keyword or excluded business type
- it does not sell the requested type of product
- it does not match the requested positioning
- it is located in an excluded country
- it is only an OEM, ODM or private-label manufacturer without its own brand

Return ONLY valid JSON using this structure:

{{
  "is_candidate": true,
  "site_type": "brand",
  "agency_fit_score": 85,
  "country": "France",
  "matched_products": ["example product"],
  "matched_positioning": ["example positioning"],
  "reason": "Short explanation based on the user's search request."
}}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You classify websites for international "
                    "brand distribution opportunities. "
                    "Follow the user's dynamic search conditions. "
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
    )

    content = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        return {
            "is_candidate": False,
            "site_type": "parse_error",
            "agency_fit_score": 0,
            "country": "",
            "matched_products": [],
            "matched_positioning": [],
            "reason": content[:300],
        }

    return {
        "is_candidate": bool(
            result.get("is_candidate", False)
        ),
        "site_type": str(
            result.get("site_type", "")
        ),
        "agency_fit_score": result.get(
            "agency_fit_score",
            0,
        ),
        "country": result.get(
            "country",
            "",
        ),
        "matched_products": result.get(
            "matched_products",
            [],
        ),
        "matched_positioning": result.get(
            "matched_positioning",
            [],
        ),
        "reason": str(
            result.get("reason", "")
        ),
    }

