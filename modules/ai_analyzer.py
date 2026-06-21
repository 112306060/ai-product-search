from datetime import datetime
from urllib.parse import urlparse

from modules.brand_name_validator import (
    validate_brand_name,
)
from modules.search_profile import SearchProfile


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


GENERAL_BUSINESS_KEYWORDS = {
    "professional": "Professional",
    "salon": "Salon",
    "distribution": "Distribution",
    "distributor": "Distributor",
    "wholesale": "Wholesale",
    "retail": "Retail",
    "private label": "Private Label",
    "oem": "OEM",
    "odm": "ODM",
    "product information file": "PIF",
    "pif": "PIF",
}


def analyze_brand_page(
    url: str,
    page_text: str,
    index: int,
    search_profile: SearchProfile,
    source: str = "Google Search",
) -> dict:
    """
    依照 SearchProfile 整理品牌資料。

    商品類別、商品內容及評論皆由本次搜尋條件產生，
    不再固定為髮品或洗髮精。
    """

    guessed_name = guess_company_name(
        url,
        page_text,
    )

    company_name = validate_brand_name(
        proposed_name=guessed_name,
        url=url,
    )

    country = guess_country(
        url,
        page_text,
    )

    product_category = guess_product_category(
        search_profile
    )

    product_content = guess_product_content(
        page_text=page_text,
        search_profile=search_profile,
    )

    comment = guess_comment(
        page_text=page_text,
        search_profile=search_profile,
    )

    return {
        "記錄日期": datetime.now().strftime(
            "%Y%m%d"
        ),
        "編號": index,
        "公司名稱": company_name,
        "網站": url,
        "國家": country,
        "資料來源": source,
        "商品類別": product_category,
        "商品內容": product_content,
        "評論": comment,
        "": "",
        "後續連絡情況": "",
        "連絡人資料": "",
        "來源連結": url,
    }


def guess_company_name(
    url: str,
    page_text: str,
) -> str:
    domain = (
        urlparse(url)
        .netloc
        .replace("www.", "")
    )

    base = domain.split(".")[0]

    name = (
        base
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )

    name = " ".join(
        word.capitalize()
        for word in name.split()
    )

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

    return special_names.get(
        lower_name,
        name,
    )


def guess_country(
    url: str,
    page_text: str,
) -> str:
    domain = urlparse(url).netloc.lower()

    text = (
        page_text[:5000].lower()
        if page_text
        else ""
    )

    for suffix, country in (
        COUNTRY_HINTS.items()
    ):
        if domain.endswith(suffix):
            return country

    for keyword, country in (
        COUNTRY_KEYWORDS.items()
    ):
        if keyword in text:
            return country

    return ""


def normalize_display_text(
    value: str,
) -> str:
    """
    將搜尋關鍵字轉成較適合 Excel 顯示的格式。
    """

    cleaned = str(value).strip()

    if not cleaned:
        return ""

    return " ".join(
        word.capitalize()
        for word in cleaned.split()
    )


def guess_product_category(
    search_profile: SearchProfile,
) -> str:
    """
    使用商品關鍵字建立商品類別。

    例如：
    shampoo / conditioner / hair care
    會輸出：
    Shampoo / Conditioner / Hair Care
    """

    categories = []

    for keyword in (
        search_profile.product_keywords
    ):
        display = normalize_display_text(
            keyword
        )

        if (
            display
            and display not in categories
        ):
            categories.append(display)

    if categories:
        return " / ".join(categories)

    if search_profile.query.strip():
        return search_profile.query.strip()

    return "待確認"


def find_matching_keywords(
    page_text: str,
    keywords: list[str],
) -> list[str]:
    text = (
        page_text.lower()
        if page_text
        else ""
    )

    matches = []

    for keyword in keywords:
        cleaned = str(keyword).strip()

        if not cleaned:
            continue

        if cleaned.lower() in text:
            display = normalize_display_text(
                cleaned
            )

            if display not in matches:
                matches.append(display)

    return matches


def find_business_features(
    page_text: str,
) -> list[str]:
    text = (
        page_text.lower()
        if page_text
        else ""
    )

    features = []

    for keyword, display in (
        GENERAL_BUSINESS_KEYWORDS.items()
    ):
        if (
            keyword in text
            and display not in features
        ):
            features.append(display)

    return features


def guess_product_content(
    page_text: str,
    search_profile: SearchProfile,
) -> str:
    """
    從頁面找出符合本次搜尋的商品與定位詞。
    """

    matched_products = (
        find_matching_keywords(
            page_text,
            search_profile.product_keywords,
        )
    )

    matched_positioning = (
        find_matching_keywords(
            page_text,
            search_profile.positioning_keywords,
        )
    )

    business_features = (
        find_business_features(page_text)
    )

    content_parts = []

    content_parts.extend(
        matched_products
    )

    content_parts.extend(
        matched_positioning
    )

    for feature in business_features:
        if feature not in content_parts:
            content_parts.append(feature)

    if content_parts:
        return " / ".join(content_parts)

    if search_profile.product_keywords:
        expected_products = [
            normalize_display_text(keyword)
            for keyword in (
                search_profile.product_keywords
            )
            if str(keyword).strip()
        ]

        return (
            "待人工確認："
            + " / ".join(expected_products)
        )

    return "已抓取官網內容，待人工確認商品資訊"


def guess_comment(
    page_text: str,
    search_profile: SearchProfile,
) -> str:
    """
    產生與本次搜尋條件有關的評論。
    """

    matched_products = (
        find_matching_keywords(
            page_text,
            search_profile.product_keywords,
        )
    )

    matched_positioning = (
        find_matching_keywords(
            page_text,
            search_profile.positioning_keywords,
        )
    )

    business_features = (
        find_business_features(page_text)
    )

    comments = []

    if matched_products:
        comments.append(
            "符合商品條件："
            + "、".join(matched_products)
        )

    if matched_positioning:
        comments.append(
            "符合定位條件："
            + "、".join(
                matched_positioning
            )
        )

    if business_features:
        comments.append(
            "頁面提及："
            + "、".join(
                business_features
            )
        )

    if search_profile.query.strip():
        comments.append(
            "本次搜尋需求："
            + search_profile.query.strip()
        )

    if not comments:
        return (
            "已抓取官網內容，"
            "待人工確認是否符合本次搜尋條件"
        )

    return "；".join(comments)

