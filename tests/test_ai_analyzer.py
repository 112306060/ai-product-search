from modules.ai_analyzer import (
    analyze_brand_page,
)
from modules.search_profile import (
    SearchProfile,
)


def test_hair_care_profile():
    profile = SearchProfile(
        query="歐洲有機天然洗髮精",
        product_keywords=[
            "shampoo",
            "conditioner",
            "hair care",
        ],
        positioning_keywords=[
            "organic",
            "natural",
        ],
        included_regions=[
            "Europe",
        ],
    )

    page_text = """
    Green People is a British natural and organic brand.
    We sell organic shampoo, conditioner and
    professional hair care products.
    """

    result = analyze_brand_page(
        url="https://greenpeople.co.uk",
        page_text=page_text,
        index=1,
        search_profile=profile,
    )

    assert result["公司名稱"] == "Green People"

    assert (
        "Shampoo"
        in result["商品類別"]
    )

    assert (
        "Organic"
        in result["商品內容"]
    )

    assert (
        "符合商品條件"
        in result["評論"]
    )


def test_body_lotion_profile():
    profile = SearchProfile(
        query="日本天然身體乳",
        product_keywords=[
            "body lotion",
        ],
        positioning_keywords=[
            "natural",
        ],
        included_countries=[
            "Japan",
        ],
    )

    page_text = """
    This Japanese natural beauty brand produces
    natural body lotion and skin care products.
    """

    result = analyze_brand_page(
        url="https://example.jp",
        page_text=page_text,
        index=2,
        search_profile=profile,
    )

    assert (
        result["商品類別"]
        == "Body Lotion"
    )

    assert (
        "Body Lotion"
        in result["商品內容"]
    )

    assert (
        "Hair Care"
        not in result["商品類別"]
    )

    assert (
        "Shampoo"
        not in result["商品內容"]
    )


if __name__ == "__main__":
    test_hair_care_profile()
    test_body_lotion_profile()

    print(
        "All AI analyzer tests passed."
    )

