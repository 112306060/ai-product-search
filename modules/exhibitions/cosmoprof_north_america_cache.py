import json
from pathlib import Path


DEFAULT_CACHE_PATH = Path(
    "data/exhibitions/"
    "cosmoprof_north_america_2026.json"
)


def clean_text(value) -> str:
    return " ".join(
        str(value or "").split()
    )


def normalize_cached_exhibitor(
    record: dict,
) -> dict:
    """
    將 North America 快取資料整理成
    candidate_filter.py 可直接使用的共用格式。

    欄位格式與 Cosmoprof Asia 相同：
    company_name
    country
    official_url
    product_category
    exhibitor_type
    description
    booth
    exhibitor_id
    exhibition
    exhibition_year
    source
    source_url
    """

    exhibitor_page_url = clean_text(
        record.get(
            "exhibitor_page_url",
            "",
        )
    )

    source_url = clean_text(
        record.get(
            "source_url",
            "",
        )
    )

    if not source_url:
        source_url = exhibitor_page_url

    return {
        "company_name": clean_text(
            record.get(
                "company_name",
                "",
            )
        ),
        "country": clean_text(
            record.get(
                "country",
                "",
            )
        ),
        "official_url": clean_text(
            record.get(
                "official_url",
                "",
            )
        ),
        "product_category": clean_text(
            record.get(
                "product_category",
                "",
            )
        ),
        "exhibitor_type": clean_text(
            record.get(
                "exhibitor_type",
                "",
            )
        ),
        "description": clean_text(
            record.get(
                "description",
                "",
            )
        ),
        "booth": clean_text(
            record.get(
                "booth",
                "",
            )
        ),
        "exhibitor_id": record.get(
            "exhibitor_id",
            "",
        ),
        "external_id": record.get(
            "external_id",
            "",
        ),
        "product_category_id": (
            record.get(
                "product_category_id"
            )
        ),
        "slug": clean_text(
            record.get(
                "slug",
                "",
            )
        ),
        "exhibitor_page_url": (
            exhibitor_page_url
        ),
        "exhibition": clean_text(
            record.get(
                "exhibition",
                (
                    "Cosmoprof North America "
                    "Las Vegas"
                ),
            )
        ),
        "exhibition_year": record.get(
            "exhibition_year",
            2026,
        ),
        "source": clean_text(
            record.get(
                "source",
                (
                    "Cosmoprof North America "
                    "Las Vegas 2026"
                ),
            )
        ),
        "source_url": source_url,
        "detail_fetched": bool(
            record.get(
                "detail_fetched",
                False,
            )
        ),
        "detail_fetch_error": clean_text(
            record.get(
                "detail_fetch_error",
                "",
            )
        ),
    }


def load_cached_exhibitors(
    cache_path: str | Path = (
        DEFAULT_CACHE_PATH
    ),
) -> list[dict]:
    """
    讀取完整 North America 快取。

    此函式只負責讀取及標準化，
    不進行商品、定位或地區篩選。
    """

    path = Path(cache_path)

    if not path.exists():
        raise FileNotFoundError(
            "找不到 Cosmoprof North America "
            f"快取：{path}\n"
            "請先執行 python build_cpna_cache.py"
        )

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Cosmoprof North America "
            "快取不是有效 JSON。"
        ) from error

    if not isinstance(payload, list):
        raise RuntimeError(
            "Cosmoprof North America "
            "快取最外層必須是清單。"
        )

    exhibitors = [
        normalize_cached_exhibitor(
            record
        )
        for record in payload
        if isinstance(record, dict)
    ]

    print(
        "[COSMOPROF NORTH AMERICA CACHE] "
        f"讀取 {len(exhibitors)} 家參展商"
    )

    return exhibitors


def get_cache_statistics(
    exhibitors: list[dict],
) -> dict:
    """
    統計快取資料完整度。
    """

    total = len(exhibitors)

    official_url_count = sum(
        1
        for exhibitor in exhibitors
        if exhibitor.get("official_url")
    )

    description_count = sum(
        1
        for exhibitor in exhibitors
        if exhibitor.get("description")
    )

    country_count = sum(
        1
        for exhibitor in exhibitors
        if exhibitor.get("country")
    )

    detail_fetched_count = sum(
        1
        for exhibitor in exhibitors
        if exhibitor.get(
            "detail_fetched"
        )
    )

    return {
        "total": total,
        "official_url_count": (
            official_url_count
        ),
        "description_count": (
            description_count
        ),
        "country_count": country_count,
        "detail_fetched_count": (
            detail_fetched_count
        ),
    }


if __name__ == "__main__":
    exhibitors = load_cached_exhibitors()

    statistics = get_cache_statistics(
        exhibitors
    )

    print()
    print("[CACHE STATISTICS]")

    print(
        "總數：",
        statistics["total"],
    )

    print(
        "完成詳情頁：",
        statistics[
            "detail_fetched_count"
        ],
    )

    print(
        "有官方網站：",
        statistics[
            "official_url_count"
        ],
    )

    print(
        "有描述：",
        statistics[
            "description_count"
        ],
    )

    print(
        "有國家：",
        statistics[
            "country_count"
        ],
    )