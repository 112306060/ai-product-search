from modules.keyword_translator import (
    translate_terms,
)
from modules.search_profile import SearchProfile


# 使用者輸入越寬鬆（更多商品詞/定位詞/地區），
# 組合出的關鍵字數量會等比例暴增，進而讓 SerpAPI
# 用量失控。這裡設一個安全上限，優先保留使用者
# 明確輸入的基本組合，超出上限才犧牲自動生成的
# brand/professional/distributor 變化版本。
MAX_KEYWORDS = 60

# 每種語言分到的關鍵字名額。因為要留名額給多語言
# 輪流搜尋，非英文語言先不加 brand/professional/
# distributor 這類尾綴變化，只用商品×定位的基本組合。
PER_LANGUAGE_KEYWORD_BUDGET = 12


def build_search_locations(
    profile: SearchProfile,
) -> list[str]:
    """
    取得本次搜尋使用的位置條件。

    優先使用使用者指定國家，
    其次使用地區；兩者皆未指定時不限制位置。
    """

    locations = []

    for country in profile.included_countries:
        cleaned = str(country).strip()

        if cleaned and cleaned not in locations:
            locations.append(cleaned)

    for region in profile.included_regions:
        cleaned = str(region).strip()

        if cleaned and cleaned not in locations:
            locations.append(cleaned)

    return locations


def generate_keywords(
    profile: SearchProfile,
    languages: list[str] | None = None,
) -> list[str]:
    """
    根據使用者本次的 SearchProfile 動態產生搜尋詞。

    此函式不寫死 shampoo、organic 或 Europe。
    """

    product_keywords = [
        str(keyword).strip()
        for keyword in profile.product_keywords
        if str(keyword).strip()
    ]

    positioning_keywords = [
        str(keyword).strip()
        for keyword in profile.positioning_keywords
        if str(keyword).strip()
    ]

    locations = build_search_locations(profile)

    # 使用者沒有設定結構化商品詞時，
    # 至少保留原始自然語言查詢。
    if not product_keywords:
        product_keywords = [
            profile.query.strip()
        ]

    # 沒有指定定位時，不強制加入定位詞。
    positioning_options = (
        positioning_keywords
        if positioning_keywords
        else [""]
    )

    # 沒有指定國家或地區時，不強制加入位置。
    location_options = (
        locations
        if locations
        else [""]
    )

    keywords = []

    for product in product_keywords:
        for positioning in positioning_options:
            for location in location_options:
                parts = [
                    positioning,
                    product,
                    location,
                ]

                keyword = " ".join(
                    part
                    for part in parts
                    if part
                ).strip()

                if keyword and keyword not in keywords:
                    keywords.append(keyword)

    if len(keywords) > MAX_KEYWORDS:
        print(
            "[KEYWORD LIMIT] "
            f"基本關鍵字組合達 {len(keywords)} 組，"
            f"超過上限 {MAX_KEYWORDS}，"
            f"只保留前 {MAX_KEYWORDS} 組"
        )

        return keywords[:MAX_KEYWORDS]

    # 補充品牌與專業通路搜尋版本，
    # 但仍然完全根據使用者商品條件生成，
    # 且不會讓總數超過 MAX_KEYWORDS。
    base_keywords = list(keywords)

    for keyword in base_keywords:
        if len(keywords) >= MAX_KEYWORDS:
            break

        variants = [
            f"{keyword} brand",
            f"{keyword} professional",
            f"{keyword} distributor",
        ]

        for variant in variants:
            if len(keywords) >= MAX_KEYWORDS:
                break

            if variant not in keywords:
                keywords.append(variant)

    return keywords


def generate_keywords_for_language(
    profile: SearchProfile,
    language: str,
    max_count: int = (
        PER_LANGUAGE_KEYWORD_BUDGET
    ),
) -> list[str]:
    """
    針對單一語言，把商品/定位詞翻譯後
    組合出關鍵字，供多語言分批搜尋使用。

    跟 generate_keywords() 不同：
    - 商品/定位詞會先翻譯成目標語言
      （English 不用翻譯，直接用原文）
    - 不加 brand/professional/distributor
      尾綴變化，把名額留給更多語言
    - 有獨立的 max_count 上限，
      由呼叫端依剩餘關鍵字預算決定
    """

    product_keywords = [
        str(keyword).strip()
        for keyword in profile.product_keywords
        if str(keyword).strip()
    ]

    positioning_keywords = [
        str(keyword).strip()
        for keyword in profile.positioning_keywords
        if str(keyword).strip()
    ]

    locations = build_search_locations(
        profile
    )

    if not product_keywords:
        product_keywords = [
            profile.query.strip()
        ]

    translated_products = (
        translate_terms(
            product_keywords,
            language,
        )
    )

    translated_positioning = (
        translate_terms(
            positioning_keywords,
            language,
        )
        if positioning_keywords
        else []
    )

    positioning_options = (
        translated_positioning
        if translated_positioning
        else [""]
    )

    location_options = (
        locations
        if locations
        else [""]
    )

    keywords = []

    for product in translated_products:
        for positioning in (
            positioning_options
        ):
            for location in (
                location_options
            ):
                parts = [
                    positioning,
                    product,
                    location,
                ]

                keyword = " ".join(
                    part
                    for part in parts
                    if part
                ).strip()

                if (
                    keyword
                    and keyword
                    not in keywords
                ):
                    keywords.append(
                        keyword
                    )

                if (
                    len(keywords)
                    >= max_count
                ):
                    return keywords

    return keywords