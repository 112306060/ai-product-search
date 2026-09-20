from modules.candidate_filter import (
    evaluate_candidates,
    filter_candidates,
)
from modules.exhibitions.cosmoprof_asia import (
    get_all_exhibitors,
)
from modules.search_profile import SearchProfile


def build_test_profile() -> SearchProfile:
    """
    模擬目前公司的搜尋需求。

    這些條件之後會由使用者介面輸入，
    目前只是測試資料。
    """

    return SearchProfile(
        query="歐洲有機天然洗髮精",
        product_keywords=[
            "shampoo",
            "conditioner",
            "hair care products",
            "hair care",
            "scalp care",
            "hair treatment",
        ],
        positioning_keywords=[
            "organic",
            "natural",
            "vegan",
            "botanical",
            "clean beauty",
        ],
        excluded_keywords=[
            "hair removal",
            "beauty equipment",
            "packaging",
            "nail",
            "eyelash",
        ],
        included_regions=[
            "Europe",
        ],
        excluded_countries=[],
        require_official_url=True,
        require_product_match=True,
        require_positioning_match=True,
        allow_unknown_country=False,
    )


def main() -> None:
    profile = build_test_profile()

    exhibitors = get_all_exhibitors()

    filtered = filter_candidates(
        exhibitors,
        profile,
    )

    evaluated = evaluate_candidates(
        exhibitors,
        profile,
    )

    rejected = [
        item
        for item in evaluated
        if not item["filter_result"]["is_candidate"]
    ]

    print(
        f"[TOTAL] {len(exhibitors)}"
    )

    print(
        f"[MATCHED] {len(filtered)}"
    )

    print(
        f"[REJECTED] {len(rejected)}"
    )

    print("\n[FIRST 20 MATCHED]")

    for exhibitor in filtered[:20]:
        result = exhibitor["filter_result"]

        print("-" * 80)

        print(
            exhibitor["company_name"]
        )

        print(
            "國家：",
            exhibitor["country"],
        )

        print(
            "官網：",
            exhibitor["official_url"],
        )

        print(
            "商品符合：",
            result[
                "matched_product_keywords"
            ],
        )

        print(
            "定位符合：",
            result[
                "matched_positioning_keywords"
            ],
        )

        print(
            "產品分類：",
            exhibitor["product_category"],
        )


if __name__ == "__main__":
    main()