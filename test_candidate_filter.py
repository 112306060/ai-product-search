from modules.candidate_filter import (
    filter_candidates,
    get_candidate_filter_result,
)
from modules.search_profile import SearchProfile


def build_test_profile() -> SearchProfile:
    """
    模擬某次使用者搜尋：

    - 商品：有機天然洗髮精
    - 地區：歐洲
    - 排除國家：中國
    """

    return SearchProfile(
        query="歐洲有機天然洗髮精",
        product_keywords=[
            "shampoo",
            "conditioner",
            "hair care products",
            "scalp care",
        ],
        positioning_keywords=[
            "organic",
            "natural",
            "vegan",
        ],
        excluded_keywords=[
            "hair removal",
            "packaging",
            "beauty equipment",
        ],
        included_regions=[
            "Europe",
        ],
        excluded_countries=[
            "China",
        ],
        require_official_url=True,
        require_product_match=True,
        require_positioning_match=True,
        allow_unknown_country=False,
    )


def test_matching_european_brand_passes():
    profile = build_test_profile()

    candidate = {
        "company_name": (
            "Example Organic Hair"
        ),
        "country": "Italy",
        "official_url": (
            "https://example.com"
        ),
        "product_category": (
            "Organic shampoo and "
            "hair care products"
        ),
        "description": (
            "Natural and vegan formulas"
        ),
    }

    result = get_candidate_filter_result(
        candidate,
        profile,
    )

    assert result["is_candidate"] is True

    assert (
        result["has_product_match"]
        is True
    )

    assert (
        result["has_positioning_match"]
        is True
    )

    assert (
        result["country_is_included"]
        is True
    )


def test_skincare_only_is_rejected():
    profile = build_test_profile()

    candidate = {
        "company_name": "Natural Skin",
        "country": "France",
        "official_url": (
            "https://example.com"
        ),
        "product_category": (
            "Natural skincare products"
        ),
        "description": (
            "Organic face cream"
        ),
    }

    result = get_candidate_filter_result(
        candidate,
        profile,
    )

    assert result["is_candidate"] is False

    assert (
        "no_product_match"
        in result["rejection_reasons"]
    )


def test_hair_brand_without_positioning_is_rejected():
    profile = build_test_profile()

    candidate = {
        "company_name": "Salon Hair",
        "country": "Spain",
        "official_url": (
            "https://example.com"
        ),
        "product_category": (
            "Shampoo and conditioner"
        ),
        "description": (
            "Professional salon products"
        ),
    }

    result = get_candidate_filter_result(
        candidate,
        profile,
    )

    assert result["is_candidate"] is False

    assert (
        "no_positioning_match"
        in result["rejection_reasons"]
    )


def test_excluded_country_is_rejected():
    profile = build_test_profile()

    candidate = {
        "company_name": (
            "Example Factory"
        ),
        "country": "China",
        "official_url": (
            "https://example.com"
        ),
        "product_category": (
            "Organic shampoo"
        ),
        "description": (
            "Natural hair care products"
        ),
    }

    result = get_candidate_filter_result(
        candidate,
        profile,
    )

    assert result["is_candidate"] is False

    assert (
        "excluded_country"
        in result["rejection_reasons"]
    )


def test_country_outside_selected_region_is_rejected():
    profile = build_test_profile()

    candidate = {
        "company_name": (
            "American Natural Hair"
        ),
        "country": "USA",
        "official_url": (
            "https://example.com"
        ),
        "product_category": (
            "Organic shampoo"
        ),
        "description": (
            "Natural hair care products"
        ),
    }

    result = get_candidate_filter_result(
        candidate,
        profile,
    )

    assert result["is_candidate"] is False

    assert (
        "country_not_included"
        in result["rejection_reasons"]
    )


def test_missing_website_is_rejected():
    profile = build_test_profile()

    candidate = {
        "company_name": (
            "No Website Brand"
        ),
        "country": "Germany",
        "official_url": "",
        "product_category": (
            "Organic shampoo"
        ),
        "description": (
            "Natural hair care"
        ),
    }

    result = get_candidate_filter_result(
        candidate,
        profile,
    )

    assert result["is_candidate"] is False

    assert (
        "missing_official_url"
        in result["rejection_reasons"]
    )


def test_unknown_country_is_rejected_when_disabled():
    profile = build_test_profile()

    candidate = {
        "company_name": (
            "Unknown Country Brand"
        ),
        "country": "",
        "official_url": (
            "https://example.com"
        ),
        "product_category": (
            "Organic shampoo"
        ),
        "description": (
            "Natural hair care"
        ),
    }

    result = get_candidate_filter_result(
        candidate,
        profile,
    )

    assert result["is_candidate"] is False

    assert (
        "unknown_country"
        in result["rejection_reasons"]
    )


def test_user_can_search_without_country_limit():
    """
    模擬另一位使用者不限制國家。
    """

    profile = SearchProfile(
        query="天然洗髮精",
        product_keywords=[
            "shampoo",
        ],
        positioning_keywords=[
            "natural",
        ],
        included_countries=[],
        included_regions=[],
        excluded_countries=[],
    )

    candidate = {
        "company_name": (
            "Global Natural Hair"
        ),
        "country": "Japan",
        "official_url": (
            "https://example.com"
        ),
        "product_category": (
            "Natural shampoo"
        ),
        "description": "",
    }

    result = get_candidate_filter_result(
        candidate,
        profile,
    )

    assert result["is_candidate"] is True


def test_user_can_select_specific_country():
    """
    模擬另一位使用者只搜尋日本。
    """

    profile = SearchProfile(
        query="日本天然洗髮精",
        product_keywords=[
            "shampoo",
        ],
        positioning_keywords=[
            "natural",
        ],
        included_countries=[
            "Japan",
        ],
    )

    japan_candidate = {
        "company_name": (
            "Japan Natural Hair"
        ),
        "country": "Japan",
        "official_url": (
            "https://example.jp"
        ),
        "product_category": (
            "Natural shampoo"
        ),
        "description": "",
    }

    france_candidate = {
        "company_name": (
            "France Natural Hair"
        ),
        "country": "France",
        "official_url": (
            "https://example.fr"
        ),
        "product_category": (
            "Natural shampoo"
        ),
        "description": "",
    }

    result = filter_candidates(
        [
            japan_candidate,
            france_candidate,
        ],
        profile,
    )

    assert len(result) == 1

    assert (
        result[0]["country"]
        == "Japan"
    )


if __name__ == "__main__":
    test_matching_european_brand_passes()
    test_skincare_only_is_rejected()
    test_hair_brand_without_positioning_is_rejected()
    test_excluded_country_is_rejected()
    test_country_outside_selected_region_is_rejected()
    test_missing_website_is_rejected()
    test_unknown_country_is_rejected_when_disabled()
    test_user_can_search_without_country_limit()
    test_user_can_select_specific_country()

    print(
        "All candidate filter tests passed."
    )