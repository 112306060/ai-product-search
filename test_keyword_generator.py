from modules.keyword_generator import (
    generate_keywords,
)
from modules.search_profile import SearchProfile


def test_generates_keywords_from_profile():
    profile = SearchProfile(
        query="歐洲有機天然洗髮精",
        product_keywords=[
            "shampoo",
        ],
        positioning_keywords=[
            "organic",
            "natural",
        ],
        included_regions=[
            "Europe",
        ],
    )

    keywords = generate_keywords(profile)

    assert "organic shampoo Europe" in keywords
    assert "natural shampoo Europe" in keywords
    assert "organic shampoo Europe brand" in keywords


def test_different_product_does_not_generate_shampoo():
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

    keywords = generate_keywords(profile)

    assert "natural body lotion Japan" in keywords

    assert not any(
        "shampoo" in keyword.lower()
        for keyword in keywords
    )


def test_search_without_location():
    profile = SearchProfile(
        query="純素護膚品",
        product_keywords=[
            "skincare",
        ],
        positioning_keywords=[
            "vegan",
        ],
    )

    keywords = generate_keywords(profile)

    assert "vegan skincare" in keywords


def test_query_is_used_when_product_keywords_are_empty():
    profile = SearchProfile(
        query="天然精油",
        product_keywords=[],
        positioning_keywords=[],
    )

    keywords = generate_keywords(profile)

    assert "天然精油" in keywords


if __name__ == "__main__":
    test_generates_keywords_from_profile()
    test_different_product_does_not_generate_shampoo()
    test_search_without_location()
    test_query_is_used_when_product_keywords_are_empty()

    print(
        "All keyword generator tests passed."
    )