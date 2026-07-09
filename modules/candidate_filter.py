from modules.search_profile import SearchProfile


SEARCHABLE_FIELDS = [
    "company_name",
    "product_category",
    "exhibitor_type",
    "description",
    "brand_positioning",
    "product_content",
    "title",
    "snippet",
]


# 排除詞判斷刻意不看 product_category：
# 這個欄位常常是一家公司「同時掛在好幾個分類底下」的
# 大雜燴（例如同時做洗護髮又兼做包材/指甲），如果用同一段
# 文字判斷排除詞，一家主力做洗護髮的公司只要剛好也掛了
# 一個 nail/packaging 分類，就會被整家誤判排除。
# 排除詞判斷只看公司名稱與描述等「代表這家公司主要身分」
# 的欄位，product_category 則保留給商品/定位比對使用
# （那邊本來就希望比對範圍越廣越好）。
EXCLUSION_CHECK_FIELDS = [
    field_name
    for field_name in SEARCHABLE_FIELDS
    if field_name != "product_category"
]


def build_text_from_fields(
    candidate: dict,
    field_names: list[str],
) -> str:
    values = []

    for field_name in field_names:
        value = candidate.get(
            field_name,
            "",
        )

        if value:
            values.append(str(value))

    return " ".join(values).lower()


def build_searchable_text(
    candidate: dict,
) -> str:
    """
    將不同來源的候選資料合併成可搜尋文字，
    用於商品/定位詞比對。

    展覽名錄、Google 搜尋結果與其他來源，
    都可以共用這個篩選器。
    """

    return build_text_from_fields(
        candidate,
        SEARCHABLE_FIELDS,
    )


def build_exclusion_check_text(
    candidate: dict,
) -> str:
    """
    專門給排除詞判斷用的較窄文字，
    不包含 product_category 這種多重分類標籤欄位。
    """

    return build_text_from_fields(
        candidate,
        EXCLUSION_CHECK_FIELDS,
    )


def contains_any(
    text: str,
    keywords: list[str],
) -> bool:
    """
    判斷文字是否包含關鍵字清單中的任一項。
    """

    if not keywords:
        return False

    return any(
        keyword in text
        for keyword in keywords
    )


def find_matched_keywords(
    text: str,
    keywords: list[str],
) -> list[str]:
    """
    回傳實際符合的關鍵字，
    方便之後在 Streamlit 或紀錄中顯示。
    """

    return [
        keyword
        for keyword in keywords
        if keyword in text
    ]


def normalize_country(
    country: str,
) -> str:
    return str(country).strip().lower()


def get_candidate_filter_result(
    candidate: dict,
    profile: SearchProfile,
) -> dict:
    """
    根據使用者提供的 SearchProfile 判斷候選資料。

    此函式本身不認識：
    - 洗髮精
    - 有機
    - 天然
    - 中國
    - 義大利

    所有條件皆來自 profile。
    """

    searchable_text = build_searchable_text(
        candidate
    )

    exclusion_check_text = (
        build_exclusion_check_text(
            candidate
        )
    )

    official_url = str(
        candidate.get(
            "official_url",
            "",
        )
    ).strip()

    country = normalize_country(
        candidate.get(
            "country",
            "",
        )
    )

    product_keywords = (
        profile.normalized_product_keywords()
    )

    positioning_keywords = (
        profile.normalized_positioning_keywords()
    )

    excluded_keywords = (
        profile.normalized_excluded_keywords()
    )

    included_countries = (
        profile.resolved_included_countries()
    )

    excluded_countries = set(
        profile.normalized_excluded_countries()
    )

    matched_product_keywords = (
        find_matched_keywords(
            searchable_text,
            product_keywords,
        )
    )

    matched_positioning_keywords = (
        find_matched_keywords(
            searchable_text,
            positioning_keywords,
        )
    )

    matched_excluded_keywords = (
        find_matched_keywords(
            exclusion_check_text,
            excluded_keywords,
        )
    )

    has_product_match = bool(
        matched_product_keywords
    )

    has_positioning_match = bool(
        matched_positioning_keywords
    )

    country_is_unknown = not bool(country)

    country_is_excluded = (
        country in excluded_countries
    )

    # 如果使用者沒有指定包含國家或地區，
    # included_countries 會是空集合，
    # 此時代表不限制國家。
    country_is_included = (
        not included_countries
        or country in included_countries
    )

    rejection_reasons = []

    if (
        profile.require_official_url
        and not official_url
    ):
        rejection_reasons.append(
            "missing_official_url"
        )

    if (
        country_is_unknown
        and not profile.allow_unknown_country
    ):
        rejection_reasons.append(
            "unknown_country"
        )

    if (
        country
        and not country_is_included
    ):
        rejection_reasons.append(
            "country_not_included"
        )

    if country_is_excluded:
        rejection_reasons.append(
            "excluded_country"
        )

    if matched_excluded_keywords:
        rejection_reasons.append(
            "excluded_keyword"
        )

    if (
        profile.require_product_match
        and not has_product_match
    ):
        rejection_reasons.append(
            "no_product_match"
        )

    if (
        profile.require_positioning_match
        and not has_positioning_match
    ):
        rejection_reasons.append(
            "no_positioning_match"
        )

    return {
        "is_candidate": (
            len(rejection_reasons) == 0
        ),
        "country": country,
        "country_is_unknown": (
            country_is_unknown
        ),
        "country_is_included": (
            country_is_included
        ),
        "country_is_excluded": (
            country_is_excluded
        ),
        "has_product_match": (
            has_product_match
        ),
        "has_positioning_match": (
            has_positioning_match
        ),
        "matched_product_keywords": (
            matched_product_keywords
        ),
        "matched_positioning_keywords": (
            matched_positioning_keywords
        ),
        "matched_excluded_keywords": (
            matched_excluded_keywords
        ),
        "rejection_reasons": (
            rejection_reasons
        ),
    }


def filter_candidates(
    candidates: list[dict],
    profile: SearchProfile,
) -> list[dict]:
    """
    只回傳通過篩選的候選資料。

    每筆資料會額外附上 filter_result，
    方便後續查看符合了哪些條件。
    """

    filtered = []

    for candidate in candidates:
        filter_result = (
            get_candidate_filter_result(
                candidate,
                profile,
            )
        )

        if not filter_result["is_candidate"]:
            continue

        candidate_with_result = {
            **candidate,
            "filter_result": filter_result,
        }

        filtered.append(
            candidate_with_result
        )

    return filtered


def evaluate_candidates(
    candidates: list[dict],
    profile: SearchProfile,
) -> list[dict]:
    """
    回傳全部候選資料及其篩選結果。

    這個函式不會刪除未通過資料，
    適合除錯或之後在介面顯示：
    為何某家公司被排除。
    """

    evaluated = []

    for candidate in candidates:
        filter_result = (
            get_candidate_filter_result(
                candidate,
                profile,
            )
        )

        evaluated.append(
            {
                **candidate,
                "filter_result": filter_result,
            }
        )

    return evaluated