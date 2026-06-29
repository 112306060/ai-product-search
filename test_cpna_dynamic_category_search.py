from modules.exhibitions.cpna_category_matcher import (
    get_api_business_area_ids,
    get_positioning_matches,
)
from modules.exhibitions.cosmoprof_north_america import (
    get_filtered_exhibitor_summaries,
)


def main():
    query = "有機天然洗髮精"

    business_area_ids = (
        get_api_business_area_ids(
            query
        )
    )

    positioning_matches = (
        get_positioning_matches(
            query
        )
    )

    print("=" * 72)
    print("[使用者需求]")
    print(query)

    print()
    print("[傳給官方 API 的分類 ID]")
    print(business_area_ids)

    print()
    print("[定位條件，留給後續 OpenAI 分析]")

    for match in positioning_matches:
        print(
            f"- {match['name']} "
            f"(ID={match['id']})"
        )

    print()
    print("[查詢 CPNA 官方展商]")

    exhibitors = (
        get_filtered_exhibitor_summaries(
            hall_code="",
            business_area_ids=(
                business_area_ids
            ),
            max_records=None,
            page_limit=60,
        )
    )

    print()
    print("=" * 72)
    print(
        "官方候選展商數：",
        len(exhibitors),
    )
    print("=" * 72)

    for exhibitor in exhibitors:
        print(
            "-",
            exhibitor.get(
                "company_name",
                "",
            ),
        )


if __name__ == "__main__":
    main()