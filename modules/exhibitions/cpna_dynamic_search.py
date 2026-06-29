from modules.exhibitions.cpna_category_matcher import (
    get_api_business_area_ids,
    get_positioning_matches,
)
from modules.exhibitions.cosmoprof_north_america import (
    get_filtered_exhibitor_summaries,
)
from modules.exhibitions.cosmoprof_north_america_cache import (
    load_cached_exhibitors,
)


def normalize_id(value) -> str:
    if value is None:
        return ""

    return str(value).strip()


def normalize_name(value) -> str:
    return " ".join(
        str(value or "")
        .casefold()
        .split()
    )


def build_cache_indexes(
    cached_exhibitors: list[dict],
) -> tuple[dict, dict]:
    by_id = {}
    by_name = {}

    for exhibitor in cached_exhibitors:
        exhibitor_id = normalize_id(
            exhibitor.get("exhibitor_id")
        )

        company_name = normalize_name(
            exhibitor.get("company_name")
        )

        if exhibitor_id:
            by_id[exhibitor_id] = exhibitor

        if company_name:
            by_name[company_name] = exhibitor

    return by_id, by_name


def merge_official_with_cache(
    official_exhibitor: dict,
    cache_by_id: dict,
    cache_by_name: dict,
) -> dict:
    exhibitor_id = normalize_id(
        official_exhibitor.get(
            "exhibitor_id"
        )
    )

    company_name = normalize_name(
        official_exhibitor.get(
            "company_name"
        )
    )

    cached = None

    if exhibitor_id:
        cached = cache_by_id.get(
            exhibitor_id
        )

    if (
        cached is None
        and company_name
    ):
        cached = cache_by_name.get(
            company_name
        )

    if cached is None:
        return {
            **official_exhibitor,
            "cache_matched": False,
        }

    merged = {
        **official_exhibitor,
        **cached,
    }

    # 官方本次查詢的名稱和 ID 優先保留。
    merged["company_name"] = (
        official_exhibitor.get(
            "company_name"
        )
        or cached.get(
            "company_name"
        )
        or ""
    )

    merged["exhibitor_id"] = (
        official_exhibitor.get(
            "exhibitor_id"
        )
        or cached.get(
            "exhibitor_id"
        )
    )

    merged["cache_matched"] = True

    return merged


def search_cpna_candidates(
    query: str,
    *,
    max_records: int | None = None,
) -> dict:
    """
    依照使用者需求：

    1. 動態匹配官方分類 ID。
    2. 呼叫 CPNA 官方 API。
    3. 合併本地快取中的官網、描述與國家。
    4. 回傳候選，供後續 OpenAI 分析。
    """
    business_area_ids = (
        get_api_business_area_ids(
            query
        )
    )

    if not business_area_ids:
        return {
            "query": query,
            "business_area_ids": [],
            "positioning_matches": [],
            "candidates": [],
            "error": (
                "找不到適合的 CPNA "
                "官方商品分類"
            ),
        }

    positioning_matches = (
        get_positioning_matches(
            query
        )
    )

    official_candidates = (
        get_filtered_exhibitor_summaries(
            hall_code="",
            business_area_ids=(
                business_area_ids
            ),
            max_records=max_records,
            page_limit=60,
        )
    )

    cached_exhibitors = (
        load_cached_exhibitors()
    )

    (
        cache_by_id,
        cache_by_name,
    ) = build_cache_indexes(
        cached_exhibitors
    )

    merged_candidates = [
        merge_official_with_cache(
            official_exhibitor=(
                exhibitor
            ),
            cache_by_id=cache_by_id,
            cache_by_name=cache_by_name,
        )
        for exhibitor
        in official_candidates
    ]

    return {
        "query": query,
        "business_area_ids": (
            business_area_ids
        ),
        "positioning_matches": [
            {
                "id": match.get("id"),
                "name": match.get("name"),
                "score": match.get(
                    "score"
                ),
            }
            for match in positioning_matches
        ],
        "candidates": merged_candidates,
        "error": "",
    }


def print_search_result(
    result: dict,
) -> None:
    print("=" * 72)
    print("[CPNA DYNAMIC SEARCH]")
    print("=" * 72)

    print(
        "搜尋需求：",
        result.get("query", ""),
    )

    print(
        "官方分類 ID：",
        result.get(
            "business_area_ids",
            [],
        ),
    )

    if result.get("error"):
        print(
            "錯誤：",
            result["error"],
        )
        return

    print()
    print("[定位條件]")

    positioning_matches = (
        result.get(
            "positioning_matches",
            [],
        )
    )

    if positioning_matches:
        for match in positioning_matches:
            print(
                f"- {match['name']} "
                f"(ID={match['id']})"
            )
    else:
        print("- 無")

    candidates = result.get(
        "candidates",
        [],
    )

    print()
    print(
        "候選展商數：",
        len(candidates),
    )

    matched_count = sum(
        1
        for candidate in candidates
        if candidate.get(
            "cache_matched"
        )
    )

    print(
        "成功合併本地快取：",
        matched_count,
    )

    print()
    print("[候選展商]")

    for candidate in candidates:
        print()
        print(
            "-",
            candidate.get(
                "company_name",
                "",
            ),
        )

        print(
            "  國家：",
            candidate.get(
                "country",
                "",
            )
            or "未知",
        )

        print(
            "  官網：",
            candidate.get(
                "official_url",
                "",
            )
            or "無",
        )

        description = str(
            candidate.get(
                "description",
                "",
            )
            or ""
        )

        if description:
            print(
                "  描述：",
                description[:160],
            )

        print(
            "  快取合併：",
            candidate.get(
                "cache_matched",
                False,
            ),
        )


if __name__ == "__main__":
    search_result = (
        search_cpna_candidates(
            query="有機天然洗髮精"
        )
    )

    print_search_result(
        search_result
    )