from modules.candidate_filter import (
    evaluate_candidates,
    filter_candidates,
)
from modules.exhibitions.cosmoprof_north_america_cache import (
    load_cached_exhibitors,
)
from modules.search_profile import (
    SearchProfile,
)


def print_matches(
    title: str,
    matched: list[dict],
    limit: int = 10,
) -> None:
    print()
    print("=" * 80)
    print(title)
    print(
        f"符合筆數：{len(matched)}"
    )
    print("=" * 80)

    for exhibitor in matched[:limit]:
        filter_result = exhibitor.get(
            "filter_result",
            {},
        )

        print("-" * 80)

        print(
            "公司：",
            exhibitor.get(
                "company_name",
                "",
            ),
        )

        print(
            "國家：",
            exhibitor.get(
                "country",
                "",
            ),
        )

        print(
            "官網：",
            exhibitor.get(
                "official_url",
                "",
            ),
        )

        print(
            "商品符合：",
            filter_result.get(
                "matched_product_keywords",
                [],
            ),
        )

        print(
            "定位符合：",
            filter_result.get(
                "matched_positioning_keywords",
                [],
            ),
        )

        print(
            "描述：",
            exhibitor.get(
                "description",
                "",
            )[:250],
        )


def print_rejection_summary(
    title: str,
    evaluated: list[dict],
) -> None:
    reason_counts = {}

    for exhibitor in evaluated:
        filter_result = exhibitor.get(
            "filter_result",
            {},
        )

        for reason in filter_result.get(
            "rejection_reasons",
            [],
        ):
            reason_counts[reason] = (
                reason_counts.get(
                    reason,
                    0,
                )
                + 1
            )

    print()
    print(title)

    for reason, count in sorted(
        reason_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(
            f"  {reason}: {count}"
        )


def main():
    exhibitors = load_cached_exhibitors()

    shampoo_profile = SearchProfile(
        query="有機天然洗髮精",
        product_keywords=[
            "shampoo",
            "conditioner",
            "hair care",
            "haircare",
            "scalp",
            "洗髮",
            "護髮",
            "頭皮",
        ],
        positioning_keywords=[
            "organic",
            "natural",
            "botanical",
            "plant-based",
            "vegan",
            "有機",
            "天然",
        ],
        excluded_keywords=[
            "equipment",
            "machine",
            "packaging",
            "nail",
            "manicure",
            "pedicure",
        ],
        require_official_url=True,
        require_product_match=True,
        require_positioning_match=True,
        allow_unknown_country=True,
    )

    body_wash_profile = SearchProfile(
        query="有機天然沐浴精",
        product_keywords=[
            "body wash",
            "shower gel",
            "bath gel",
            "body cleanser",
            "body care",
            "bath and body",
            "沐浴",
            "身體清潔",
        ],
        positioning_keywords=[
            "organic",
            "natural",
            "botanical",
            "plant-based",
            "vegan",
            "有機",
            "天然",
        ],
        excluded_keywords=[
            "equipment",
            "machine",
            "packaging",
            "nail",
            "manicure",
            "pedicure",
        ],
        require_official_url=True,
        require_product_match=True,
        require_positioning_match=True,
        allow_unknown_country=True,
    )

    shampoo_matches = filter_candidates(
        exhibitors,
        shampoo_profile,
    )

    body_wash_matches = filter_candidates(
        exhibitors,
        body_wash_profile,
    )

    print_matches(
        title=(
            "SearchProfile A："
            "有機天然洗髮精"
        ),
        matched=shampoo_matches,
    )

    print_matches(
        title=(
            "SearchProfile B："
            "有機天然沐浴精"
        ),
        matched=body_wash_matches,
    )

    shampoo_evaluated = (
        evaluate_candidates(
            exhibitors,
            shampoo_profile,
        )
    )

    body_wash_evaluated = (
        evaluate_candidates(
            exhibitors,
            body_wash_profile,
        )
    )

    print_rejection_summary(
        title=(
            "[洗髮精排除原因統計]"
        ),
        evaluated=shampoo_evaluated,
    )

    print_rejection_summary(
        title=(
            "[沐浴精排除原因統計]"
        ),
        evaluated=body_wash_evaluated,
    )


if __name__ == "__main__":
    main()