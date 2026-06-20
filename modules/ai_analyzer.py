import re
from datetime import datetime
from urllib.parse import urlparse
from modules.brand_name_validator import validate_brand_name
COUNTRY_HINTS = {
    ".it": "Italy",
    ".fr": "France",
    ".de": "Germany",
    ".es": "Spain",
    ".nl": "Netherlands",
    ".be": "Belgium",
    ".dk": "Denmark",
    ".se": "Sweden",
    ".fi": "Finland",
    ".pl": "Poland",
    ".at": "Austria",
    ".eu": "Europe / EU",
    ".co.uk": "United Kingdom",
    ".uk": "United Kingdom",
}

COUNTRY_KEYWORDS = {
    "austria": "Austria",
    "italy": "Italy",
    "italian": "Italy",
    "france": "France",
    "french": "France",
    "germany": "Germany",
    "german": "Germany",
    "spain": "Spain",
    "spanish": "Spain",
    "netherlands": "Netherlands",
    "dutch": "Netherlands",
    "denmark": "Denmark",
    "danish": "Denmark",
    "sweden": "Sweden",
    "swedish": "Sweden",
    "finland": "Finland",
    "poland": "Poland",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "england": "United Kingdom",
}

def analyze_brand_page(
    url: str,
    page_text: str,
    index: int,
    source: str = "Google Search",
) -> dict:
    guessed_name = guess_company_name(url, page_text)

    company_name = validate_brand_name(
        proposed_name=guessed_name,
        url=url,
    )
    country = guess_country(url, page_text)
    product_content = guess_product_content(page_text)
    comment = guess_comment(page_text)

    return {
        "記錄日期": datetime.now().strftime("%Y%m%d"),
        "編號": index,
        "公司名稱": company_name,
        "網站": url,
        "國家": country,
        "資料來源": source,
        "商品類別": "HAIR CARE",
        "商品內容": product_content,
        "評論": comment,
        "": "",
        "後續連絡情況": "",
        "連絡人資料": "",
        "來源連結": url,
    }

def guess_company_name(url: str, page_text: str) -> str:
    domain = urlparse(url).netloc.replace("www.", "")
    base = domain.split(".")[0]

    name = base.replace("-", " ").replace("_", " ").strip()
    name = " ".join(word.capitalize() for word in name.split())

    # 常見特殊品牌修正
    special_names = {
        "vieloe": "Vielö",
        "lapurative": "La Purative",
        "unique beauty": "Unique Beauty",
        "greenpeople": "Green People",
        "evolvebeauty": "Evolve Beauty",
        "harklinikken": "Hårklinikken",
        "muehle shaving": "MÜHLE",
        "cosmeservice": "Cosmeservice",
        "ceway": "CE.way",
    }

    lower_name = name.lower()
    return special_names.get(lower_name, name)

def guess_country(url: str, page_text: str) -> str:
    domain = urlparse(url).netloc.lower()
    text = page_text[:5000].lower() if page_text else ""

    for suffix, country in COUNTRY_HINTS.items():
        if domain.endswith(suffix):
            return country

    for keyword, country in COUNTRY_KEYWORDS.items():
        if keyword in text:
            return country

    return ""

def guess_product_content(page_text: str) -> str:
    text = page_text.lower() if page_text else ""

    features = []

    if "shampoo" in text:
        features.append("Shampoo")
    if "organic" in text:
        features.append("Organic")
    if "natural" in text:
        features.append("Natural")
    if "vegan" in text:
        features.append("Vegan")
    if "scalp" in text:
        features.append("Scalp Care")
    if "salon" in text or "professional" in text:
        features.append("Professional / Salon")

    if not features:
        return "Shampoo / 洗髮精相關產品"

    return " / ".join(features)

def guess_comment(page_text: str) -> str:
    text = page_text.lower() if page_text else ""

    comments = []

    if "organic" in text:
        comments.append("頁面提及 organic，有機定位")
    if "natural" in text:
        comments.append("頁面提及 natural，天然成分")
    if "vegan" in text:
        comments.append("頁面提及 vegan，純素定位")
    if "professional" in text or "salon" in text:
        comments.append("頁面提及 professional/salon，可能適合沙龍通路")
    if "pif" in text or "product information file" in text:
        comments.append("頁面提及 PIF / Product Information File")
    if "private label" in text or "oem" in text or "odm" in text:
        comments.append("頁面提及 OEM/ODM/Private Label")

    if not comments:
        return "已抓取官網內容，待人工確認天然、有機、PIF、沙龍專業等資訊"

    return "；".join(comments)