import argparse
import json
import shutil
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import requests

from modules.exhibitions.cosmoprof_north_america import (
    API_HEADERS,
    BASE_URL,
    DIRECTORY_URL,
    clean_text,
    create_session,
    enrich_exhibitors,
    get_all_exhibitor_summaries,
)


CACHE_PATH = Path(
    "data/exhibitions/"
    "cosmoprof_north_america_2026.json"
)

METADATA_PATH = Path(
    "data/exhibitions/"
    "cosmoprof_north_america_2026_metadata.json"
)

BACKUP_DIR = Path(
    "data/exhibitions/backups"
)

FILTERS_API_URL = (
    f"{BASE_URL}/api/v1/search/filters"
)

CATEGORIES_API_URL = (
    f"{BASE_URL}/api/v1/dict/productCategories"
)


# 這些欄位是人工、AI 或其他補全流程產生的，
# 官方目錄同步時不可隨便覆蓋。
PRESERVED_FIELDS = {
    "country",
    "country_id",
    "country_iso",
    "country_source",
    "country_evidence",
    "country_confidence",
    "business_area_ids",
    "business_area_names",
    "business_area_source",
    "manual_notes",
    "contact_status",
    "contact_person",
    "contact_information",
    "agency_score",
    "ai_analysis",
    "review",
}


# 這些欄位可以用官方最新清單更新。
OFFICIAL_REFRESH_FIELDS = {
    "company_name",
    "external_id",
    "slug",
    "exhibitor_page_url",
    "source_url",
    "booth",
    "exhibitor_type",
    "description",
    "product_category_id",
    "is_new",
    "exhibition",
    "exhibition_year",
    "source",
}


def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(
        timespec="seconds"
    )


def normalize_id(value) -> str:
    """
    統一轉成字串，避免 30035 與 "30035"
    被視為不同展商。
    """
    if value is None:
        return ""

    return str(value).strip()


def normalize_name(value) -> str:
    return clean_text(
        value
    ).casefold()


def exhibitor_key(record: dict) -> str:
    """
    優先使用官方 exhibitor_id。
    若官方沒有 ID，再退回公司名稱。
    """
    exhibitor_id = normalize_id(
        record.get("exhibitor_id")
    )

    if exhibitor_id:
        return f"id:{exhibitor_id}"

    company_name = normalize_name(
        record.get("company_name")
    )

    return f"name:{company_name}"


def load_json_list(
    path: Path,
) -> list[dict]:
    if not path.exists():
        return []

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, list):
        raise RuntimeError(
            f"{path} 最外層必須是 JSON list"
        )

    return [
        item
        for item in payload
        if isinstance(item, dict)
    ]


def write_json_atomic(
    path: Path,
    payload,
) -> None:
    """
    先寫入暫存檔，再取代正式檔案，
    避免寫到一半中斷造成 JSON 損壞。
    """
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        f"{path.suffix}.tmp"
    )

    temporary_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(path)


def backup_file(
    path: Path,
) -> Path | None:
    if not path.exists():
        return None

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = (
        BACKUP_DIR
        / f"{path.stem}_{timestamp}{path.suffix}"
    )

    shutil.copy2(
        path,
        backup_path,
    )

    return backup_path


def request_json_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    max_retries: int = 3,
) -> dict:
    last_error = None

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            response = session.request(
                method=method,
                url=url,
                headers=API_HEADERS,
                params=params,
                json=json_body,
                timeout=30,
            )

            response.raise_for_status()

            payload = response.json()

            if not isinstance(payload, dict):
                raise RuntimeError(
                    "API 回傳格式不是 dict"
                )

            return payload

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ) as error:
            last_error = error

            print(
                f"[API RETRY] "
                f"{attempt}/{max_retries} "
                f"{url}：{error}"
            )

            if attempt < max_retries:
                time.sleep(
                    attempt * 5
                )

    raise RuntimeError(
        f"API 連續失敗：{url}"
    ) from last_error


def extract_filter_metadata(
    payload: dict,
) -> dict:
    """
    解析 /api/v1/search/filters 回傳的國家、
    business_area、HallCode 與 PavilionCode。
    """
    data = payload.get("data") or {}
    filter_list = data.get("list") or {}

    if not isinstance(filter_list, dict):
        filter_list = {}

    raw_countries = (
        filter_list.get("country")
        or []
    )

    countries = []

    for item in raw_countries:
        if not isinstance(item, dict):
            continue

        country_id = item.get("id")
        country_name = clean_text(
            item.get("name")
        )

        if not country_name:
            continue

        countries.append(
            {
                "id": country_id,
                "name": country_name,
                "iso": clean_text(
                    item.get("iso")
                ),
            }
        )

    raw_business_areas = (
        filter_list.get("business_area")
        or []
    )

    business_areas = []

    for item in raw_business_areas:
        if not isinstance(item, dict):
            continue

        area_id = item.get("id")
        area_name = clean_text(
            item.get("name")
        )

        if not area_name:
            continue

        business_areas.append(
            {
                "id": area_id,
                "name": area_name,
                "parent_id": item.get(
                    "parent_id"
                ),
            }
        )

    custom_filters = {}

    raw_custom_filters = (
        filter_list.get("cfilters")
        or []
    )

    for custom_filter in raw_custom_filters:
        if not isinstance(
            custom_filter,
            dict,
        ):
            continue

        filter_name = clean_text(
            custom_filter.get("name")
        )

        if not filter_name:
            continue

        options = []

        for option in (
            custom_filter.get("options")
            or []
        ):
            if not isinstance(
                option,
                dict,
            ):
                continue

            options.append(
                {
                    "value": option.get(
                        "value"
                    ),
                    "name": clean_text(
                        option.get("name")
                    ),
                }
            )

        custom_filters[
            filter_name
        ] = options

    return {
        "countries": countries,
        "business_areas": (
            business_areas
        ),
        "custom_filters": (
            custom_filters
        ),
    }


def flatten_categories(
    value,
    output: list[dict],
    parent_id=None,
) -> None:
    """
    官方分類 API 未來即使改成樹狀結構，
    也能遞迴整理成平面清單。
    """
    if isinstance(value, list):
        for item in value:
            flatten_categories(
                item,
                output,
                parent_id=parent_id,
            )

        return

    if not isinstance(value, dict):
        return

    category_id = (
        value.get("id")
        or value.get("value")
        or value.get("category_id")
    )

    category_name = clean_text(
        value.get("name")
        or value.get("label")
        or value.get("title")
    )

    current_parent_id = (
        value.get("parent_id")
        or value.get("parentId")
        or parent_id
    )

    if (
        category_id is not None
        and category_name
    ):
        output.append(
            {
                "id": category_id,
                "name": category_name,
                "parent_id": (
                    current_parent_id
                ),
            }
        )

    next_parent_id = (
        category_id
        if category_id is not None
        else current_parent_id
    )

    child_keys = (
        "children",
        "child",
        "items",
        "list",
        "options",
        "subcategories",
        "categories",
    )

    for child_key in child_keys:
        children = value.get(
            child_key
        )

        if children is not None:
            flatten_categories(
                children,
                output,
                parent_id=(
                    next_parent_id
                ),
            )


def extract_product_categories(
    payload: dict,
) -> list[dict]:
    data = payload.get("data")

    categories = []

    flatten_categories(
        data,
        categories,
    )

    # 避免同一分類因樹狀資料重複出現。
    deduplicated = {}

    for category in categories:
        category_id = normalize_id(
            category.get("id")
        )

        if not category_id:
            continue

        deduplicated[
            category_id
        ] = category

    return sorted(
        deduplicated.values(),
        key=lambda item: (
            clean_text(
                item.get("name")
            ).casefold()
        ),
    )


def fetch_official_metadata(
    session: requests.Session,
) -> dict:
    print(
        "[METADATA] 取得官方搜尋條件"
    )

    filter_payload = (
        request_json_with_retry(
            session=session,
            method="POST",
            url=FILTERS_API_URL,
            json_body={
                "type": "exhibitors",
            },
        )
    )

    filter_metadata = (
        extract_filter_metadata(
            filter_payload
        )
    )

    print(
        "[METADATA] 取得官方商品分類"
    )

    category_payload = (
        request_json_with_retry(
            session=session,
            method="GET",
            url=CATEGORIES_API_URL,
        )
    )

    product_categories = (
        extract_product_categories(
            category_payload
        )
    )

    category_by_id = {}

    for category in (
        product_categories
        + filter_metadata[
            "business_areas"
        ]
    ):
        category_id = normalize_id(
            category.get("id")
        )

        if not category_id:
            continue

        category_by_id[
            category_id
        ] = category

    return {
        "synced_at": utc_now_iso(),
        "source": (
            "Cosmoprof North America "
            "official API"
        ),
        "directory_url": DIRECTORY_URL,
        "countries": (
            filter_metadata["countries"]
        ),
        "business_areas": sorted(
            category_by_id.values(),
            key=lambda item: (
                clean_text(
                    item.get("name")
                ).casefold()
            ),
        ),
        "custom_filters": (
            filter_metadata[
                "custom_filters"
            ]
        ),
    }
def official_data_changed(
    old_record: dict,
    new_record: dict,
) -> bool:
    """
    只比較官方業務資料，
    不比較同步時間與 catalog 狀態欄位。
    """
    fields_to_compare = {
        "company_name",
        "external_id",
        "slug",
        "exhibitor_page_url",
        "source_url",
        "booth",
        "exhibitor_type",
        "description",
        "product_category_id",
        "is_new",
        "exhibition",
        "exhibition_year",
        "source",
    }

    for field in fields_to_compare:
        old_value = old_record.get(field)
        new_value = new_record.get(field)

        if isinstance(
            old_value,
            str,
        ):
            old_value = clean_text(
                old_value
            )

        if isinstance(
            new_value,
            str,
        ):
            new_value = clean_text(
                new_value
            )

        # 官方空值不會覆蓋原本資料，
        # 因此也不視為資料變更。
        if new_value in (
            None,
            "",
            [],
            {},
        ):
            continue

        if old_value != new_value:
            return True

    official_country = clean_text(
        new_record.get("country")
    )

    old_country = clean_text(
        old_record.get("country")
    )

    if (
        official_country
        and official_country != old_country
    ):
        return True

    return False

def merge_record(
    old_record: dict | None,
    official_record: dict,
    sync_time: str,
) -> dict:
    """
    官方資料更新，但保留人工與 AI 補充欄位。
    """
    if old_record is None:
        merged = deepcopy(
            official_record
        )

        merged.update(
            {
                "catalog_first_seen_at": (
                    sync_time
                ),
                "catalog_last_seen_at": (
                    sync_time
                ),
                "catalog_active": True,
                "catalog_sync_source": (
                    "CPNA official exhibitors API"
                ),
            }
        )

        return merged

    merged = deepcopy(
        old_record
    )

    for field in (
        OFFICIAL_REFRESH_FIELDS
    ):
        new_value = official_record.get(
            field
        )

        # 空值不覆蓋原本較完整的資料。
        if new_value not in (
            None,
            "",
            [],
            {},
        ):
            merged[field] = new_value

    # 新清單中的 API country 若有值，可更新；
    # 若 API 仍是空白，保留人工補好的 country。
    official_country = clean_text(
        official_record.get("country")
    )

    if official_country:
        existing_source = clean_text(
            merged.get("country_source")
        )

        # 人工確認的資料優先級最高。
        if existing_source != (
            "manual confirmed"
        ):
            merged["country"] = (
                official_country
            )
            merged["country_source"] = (
                "CPNA official exhibitor API"
            )
            merged[
                "country_confidence"
            ] = 100

    # 明確再次寫回保留欄位。
    for field in PRESERVED_FIELDS:
        if field in old_record:
            merged[field] = (
                old_record[field]
            )

    merged[
        "catalog_first_seen_at"
    ] = old_record.get(
        "catalog_first_seen_at",
        sync_time,
    )

    merged[
        "catalog_last_seen_at"
    ] = sync_time

    merged["catalog_active"] = True

    merged[
        "catalog_sync_source"
    ] = (
        "CPNA official exhibitors API"
    )

    return merged


def build_updated_catalog(
    old_records: list[dict],
    official_records: list[dict],
) -> tuple[
    list[dict],
    list[dict],
    list[dict],
]:
    sync_time = utc_now_iso()

    old_by_key = {
        exhibitor_key(record): record
        for record in old_records
    }

    official_by_key = {
        exhibitor_key(record): record
        for record in official_records
    }

    updated_records = []
    new_records = []
    changed_records = []

    for key, official_record in (
        official_by_key.items()
    ):
        old_record = old_by_key.get(
            key
        )

        merged = merge_record(
            old_record=old_record,
            official_record=(
                official_record
            ),
            sync_time=sync_time,
        )

        updated_records.append(
            merged
        )

        if old_record is None:
            new_records.append(
                merged
            )

        elif official_data_changed(
            old_record=old_record,
            new_record=official_record,
        ):
            changed_records.append(
                merged
            )
    # 官方此次沒有回傳的舊展商不刪除，
    # 只標記 inactive，避免聯絡紀錄或人工資料消失。
    for key, old_record in (
        old_by_key.items()
    ):
        if key in official_by_key:
            continue

        inactive_record = deepcopy(
            old_record
        )

        inactive_record[
            "catalog_active"
        ] = False

        inactive_record[
            "catalog_missing_since"
        ] = sync_time

        updated_records.append(
            inactive_record
        )

    updated_records.sort(
        key=lambda record: (
            normalize_name(
                record.get(
                    "company_name"
                )
            )
        )
    )

    return (
        updated_records,
        new_records,
        changed_records,
    )


def enrich_new_records_only(
    catalog: list[dict],
    new_records: list[dict],
) -> list[dict]:
    """
    只抓新增廠商的詳情頁，
    不重抓既有 951 家。
    """
    if not new_records:
        return catalog

    print(
        "[DETAIL] 開始補抓新增廠商詳情：",
        len(new_records),
    )

    enriched_new_records = (
        enrich_exhibitors(
            new_records
        )
    )

    enriched_by_key = {
        exhibitor_key(record): record
        for record
        in enriched_new_records
    }

    output = []

    for record in catalog:
        key = exhibitor_key(
            record
        )

        detail_record = (
            enriched_by_key.get(key)
        )

        if detail_record is None:
            output.append(record)
            continue

        merged = deepcopy(record)

        for field in (
            "official_url",
            "description",
            "booth",
            "exhibitor_type",
        ):
            detail_value = clean_text(
                detail_record.get(field)
            )

            if detail_value:
                merged[field] = (
                    detail_value
                )

        merged[
            "detail_fetched"
        ] = True

        merged[
            "detail_fetch_error"
        ] = ""

        output.append(merged)

    return output


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "同步 Cosmoprof North America "
            "最新展商與官方分類資料"
        )
    )

    parser.add_argument(
        "--enrich-new",
        action="store_true",
        help=(
            "同步後只抓新增展商的詳情頁"
        ),
    )

    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help=(
            "測試用，只抓前 N 家；"
            "正式同步不要使用"
        ),
    )

    return parser.parse_args()


def main():
    arguments = parse_arguments()

    print("=" * 72)
    print(
        "[CPNA CATALOG SYNC]"
    )
    print("=" * 72)

    old_records = load_json_list(
        CACHE_PATH
    )

    print(
        "目前本地展商：",
        len(old_records),
    )

    session = create_session()

    # 先開官方目錄，建立正常 Session。
    directory_response = session.get(
        DIRECTORY_URL,
        timeout=30,
    )
    directory_response.raise_for_status()

    metadata = fetch_official_metadata(
        session
    )

    print(
        "官方國家數：",
        len(metadata["countries"]),
    )
    print(
        "官方商品分類數：",
        len(
            metadata[
                "business_areas"
            ]
        ),
    )

    print()
    print(
        "[EXHIBITORS] 取得最新官方展商"
    )

    official_records = (
        get_all_exhibitor_summaries(
            max_records=(
                arguments.max_records
            ),
            page_limit=60,
        )
    )

    print(
        "官方目前展商：",
        len(official_records),
    )

    (
        updated_catalog,
        new_records,
        changed_records,
    ) = build_updated_catalog(
        old_records=old_records,
        official_records=(
            official_records
        ),
    )

    if arguments.enrich_new:
        updated_catalog = (
            enrich_new_records_only(
                catalog=updated_catalog,
                new_records=new_records,
            )
        )

    active_count = sum(
        1
        for record in updated_catalog
        if record.get(
            "catalog_active",
            True,
        )
    )

    inactive_count = (
        len(updated_catalog)
        - active_count
    )

    backup_path = backup_file(
        CACHE_PATH
    )

    write_json_atomic(
        CACHE_PATH,
        updated_catalog,
    )

    write_json_atomic(
        METADATA_PATH,
        metadata,
    )

    print()
    print("=" * 72)
    print("[SYNC COMPLETE]")
    print("=" * 72)

    if backup_path:
        print(
            "舊快取備份：",
            backup_path,
        )

    print(
        "最新快取：",
        CACHE_PATH,
    )
    print(
        "官方 metadata：",
        METADATA_PATH,
    )
    print(
        "新增展商：",
        len(new_records),
    )
    print(
        "有官方資料變化：",
        len(changed_records),
    )
    print(
        "目前有效展商：",
        active_count,
    )
    print(
        "本次未出現在官方清單：",
        inactive_count,
    )

    if new_records:
        print()
        print("[新增展商]")

        for record in new_records:
            print(
                "-",
                record.get(
                    "company_name",
                    "",
                ),
            )


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print()
        print("[CANCELLED] 使用者中止")
        sys.exit(130)

    except Exception as error:
        print()
        print(
            "[SYNC FAILED]",
            error,
        )
        sys.exit(1)