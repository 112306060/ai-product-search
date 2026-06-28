import json
import time
from pathlib import Path

from modules.exhibitions.cosmoprof_north_america import (
    create_session,
    enrich_exhibitor_summary,
    get_all_exhibitor_summaries,
)


CACHE_PATH = Path(
    "data/exhibitions/"
    "cosmoprof_north_america_2026.json"
)

# 第一次先測試 5 家。
# 測試成功後再改成 None，建立完整快取。
MAX_NEW_RECORDS = None

# 每個詳情頁之間稍微暫停，避免請求過快。
REQUEST_DELAY_SECONDS = 0.6


def clean_key(value) -> str:
    return str(value or "").strip()


def get_record_key(record: dict) -> str:
    """
    優先使用官方 exhibitor_id；
    若沒有，才用 slug 或公司名稱。
    """

    exhibitor_id = clean_key(
        record.get("exhibitor_id")
    )

    if exhibitor_id:
        return f"id:{exhibitor_id}"

    slug = clean_key(
        record.get("slug")
    ).lower()

    if slug:
        return f"slug:{slug}"

    company_name = clean_key(
        record.get("company_name")
    ).lower()

    return f"name:{company_name}"


def load_cache() -> dict[str, dict]:
    """
    讀取既有快取。

    快取不存在或格式錯誤時，
    回傳空字典。
    """

    if not CACHE_PATH.exists():
        return {}

    try:
        content = CACHE_PATH.read_text(
            encoding="utf-8"
        )

        records = json.loads(content)

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(
            "[CPNA CACHE LOAD FAILED]",
            error,
        )

        return {}

    if not isinstance(records, list):
        print(
            "[CPNA CACHE INVALID] "
            "快取內容不是清單格式"
        )

        return {}

    cache = {}

    for record in records:
        if not isinstance(record, dict):
            continue

        key = get_record_key(record)

        if key:
            cache[key] = record

    return cache


def save_cache(
    cache: dict[str, dict],
) -> None:
    """
    儲存快取。

    每處理一家公司就更新，
    中斷後可以繼續執行。
    """

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    records = list(
        cache.values()
    )

    records.sort(
        key=lambda item: (
            clean_key(
                item.get("company_name")
            ).lower()
        )
    )

    temporary_path = CACHE_PATH.with_suffix(
        ".tmp"
    )

    temporary_path.write_text(
        json.dumps(
            records,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        CACHE_PATH
    )


def record_is_complete(
    record: dict,
) -> bool:
    """
    只有明確完成過詳情頁請求，
    才視為已有完整快取。

    官方清單 API 本身可能提供 about 描述，
    但仍不代表已讀取詳情頁或取得品牌官網。
    """

    return bool(
        record.get("detail_fetched")
    )


def merge_summary_with_cache(
    summary: dict,
    cached_record: dict | None,
) -> dict:
    """
    清單 API 的最新官方欄位優先；
    詳情頁快取欄位則保留下來。
    """

    if not cached_record:
        return dict(summary)

    merged = {
        **cached_record,
        **summary,
    }

    detail_fields = [
        "official_url",
        "description",
        "country",
        "product_category",
        "exhibitor_type",
        "detail_fetched",
        "detail_fetch_error",
        "detail_updated_at",
    ]

    for field in detail_fields:
        cached_value = cached_record.get(
            field
        )

        if cached_value not in (
            None,
            "",
            [],
        ):
            merged[field] = cached_value

    return merged


def build_cache() -> None:
    print(
        "[CPNA CACHE] "
        "讀取官方完整參展商清單"
    )

    summaries = (
        get_all_exhibitor_summaries(
            max_records=None,
            page_limit=60,
        )
    )

    print(
        "[CPNA CACHE] "
        f"官方摘要共 {len(summaries)} 家"
    )

    cache = load_cache()

    print(
        "[CPNA CACHE] "
        f"既有快取 {len(cache)} 家"
    )

    session = create_session()

    processed_count = 0
    skipped_count = 0
    failed_count = 0

    total = len(summaries)

    for index, summary in enumerate(
        summaries,
        start=1,
    ):
        key = get_record_key(summary)

        if not key:
            print(
                "[CPNA CACHE SKIP] "
                "缺少公司識別欄位"
            )
            continue

        cached_record = cache.get(key)

        merged_summary = (
            merge_summary_with_cache(
                summary=summary,
                cached_record=cached_record,
            )
        )

        if record_is_complete(
            merged_summary
        ):
            cache[key] = merged_summary
            skipped_count += 1

            print(
                "[CPNA CACHE EXISTS]",
                f"{index}/{total}",
                merged_summary.get(
                    "company_name",
                    "",
                ),
            )

            continue

        if (
            MAX_NEW_RECORDS is not None
            and processed_count
            >= MAX_NEW_RECORDS
        ):
            break

        company_name = clean_key(
            summary.get("company_name")
        )

        print(
            "[CPNA CACHE DETAIL]",
            f"{index}/{total}",
            company_name,
        )

        try:
            enriched = (
                enrich_exhibitor_summary(
                    summary=merged_summary,
                    session=session,
                )
            )

            enriched[
                "detail_fetched"
            ] = True

            enriched[
                "detail_fetch_error"
            ] = ""

        except Exception as error:
            failed_count += 1

            enriched = {
                **merged_summary,
                "detail_fetched": True,
                "detail_fetch_error": (
                    str(error)
                ),
            }

            print(
                "[CPNA CACHE FAILED]",
                company_name,
                error,
            )

        cache[key] = enriched

        save_cache(cache)

        processed_count += 1

        time.sleep(
            REQUEST_DELAY_SECONDS
        )

    # 即使沒有新增，也同步儲存最新摘要。
    save_cache(cache)

    print()
    print(
        "[CPNA CACHE FINISHED]"
    )

    print(
        "官方摘要：",
        total,
    )

    print(
        "本次新增詳情：",
        processed_count,
    )

    print(
        "沿用既有快取：",
        skipped_count,
    )

    print(
        "失敗：",
        failed_count,
    )

    print(
        "目前快取總數：",
        len(cache),
    )

    print(
        "快取位置：",
        CACHE_PATH,
    )


if __name__ == "__main__":
    build_cache()