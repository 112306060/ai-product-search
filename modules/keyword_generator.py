from modules.search_profile import SearchProfile


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

    # 補充品牌與專業通路搜尋版本，
    # 但仍然完全根據使用者商品條件生成。
    base_keywords = list(keywords)

    for keyword in base_keywords:
        variants = [
            f"{keyword} brand",
            f"{keyword} professional",
            f"{keyword} distributor",
        ]

        for variant in variants:
            if variant not in keywords:
                keywords.append(variant)

    return keywords