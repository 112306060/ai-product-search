import json
import time
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://www.cosmoprof.com"

DIRECTORY_URL = (
    BASE_URL
    + "/en/visit/exhibitors-directory/digital-directory/"
)

API_URL = (
    BASE_URL
    + "/demo/include/CPBO/ajax/2021/cpbo_feed.cfm"
)

OUTPUT_PATH = Path(
    "data/exhibitions/cosmoprof_bologna_2026.json"
)

METADATA_PATH = Path(
    "data/exhibitions/cosmoprof_bologna_2026_metadata.json"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
    "Origin": BASE_URL,
    "Referer": DIRECTORY_URL,
    "X-Requested-With": "XMLHttpRequest",
}


TARGET_CATEGORIES = {
    "C107": "Hair wash products (lotions, powders, shampoos)",
    "C110": "Natural and bio products for hair treatment",
    "B106": "Natural Hair products",
    "B116": "Certified organic cosmetic products",
    "A112": "Hair care products",
    "F307": "Haircare",
    "F323": "Hair wash products (lotions, powders, shampoos)",
}


def save_json(
    path: Path,
    data: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def build_favorite_data(
    category_code: str,
    category_name: str,
) -> str:
    return json.dumps(
        {
            "page_id": 7530,
            "data": [
                {
                    "cod": category_code,
                    "text": category_name,
                    "el": "Category",
                }
            ],
        },
        ensure_ascii=False,
    )


def fetch_page(
    session: requests.Session,
    *,
    category_code: str,
    category_name: str,
    page: int,
    results_per_page: int = 100,
) -> dict[str, Any]:
    payload = {
        "super_search": "",
        "page_favorite_data": build_favorite_data(
            category_code,
            category_name,
        ),
        "page_exh": str(page),
        "rpp_exh": str(results_per_page),
        "page_bra": "1",
        "rpp_bra": "20",
        "page_pro": "1",
        "rpp_pro": "20",
        "method": "load_exhibitors_2025",
        "user_id": "0",
        "anno": "2026",
        "annoSQL": "2026",
        "lang": "l2",
    }

    response = session.post(
        API_URL,
        headers=HEADERS,
        data=payload,
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def normalize_record(
    record: dict[str, Any],
    category_code: str,
    category_name: str,
) -> dict[str, Any]:
    detail_url = record.get(
        "new_url",
        "",
    )

    if detail_url.startswith("/"):
        detail_url = BASE_URL + detail_url

    return {
        "company_name": record.get(
            "title",
            "",
        ),
        "detail_url": detail_url,
        "hall": record.get(
            "hall",
            "",
        ),
        "stand": record.get(
            "ubicazione",
            "",
        ),
        "sector": record.get(
            "settore",
            "",
        ),
        "activity_sector": record.get(
            "settore_attivita",
            "",
        ),
        "is_new": bool(
            record.get("is_new")
        ),
        "sponsored": bool(
            record.get("sponsored")
        ),
        "opening_dates": record.get(
            "DateApertura",
            "",
        ),
        "highlights": record.get(
            "highligts",
            [],
        ),
        "category_codes": [
            category_code
        ],
        "category_names": [
            category_name
        ],
        "source": (
            "Cosmoprof Worldwide "
            "Bologna 2026"
        ),
    }


def merge_record(
    existing: dict[str, Any],
    incoming: dict[str, Any],
) -> None:
    for code in incoming[
        "category_codes"
    ]:
        if code not in existing[
            "category_codes"
        ]:
            existing[
                "category_codes"
            ].append(code)

    for name in incoming[
        "category_names"
    ]:
        if name not in existing[
            "category_names"
        ]:
            existing[
                "category_names"
            ].append(name)

    if (
        not existing.get("activity_sector")
        and incoming.get("activity_sector")
    ):
        existing[
            "activity_sector"
        ] = incoming[
            "activity_sector"
        ]

    if (
        not existing.get("sector")
        and incoming.get("sector")
    ):
        existing["sector"] = incoming["sector"]


def main() -> None:
    session = requests.Session()

    print("[OPEN DIRECTORY PAGE]")

    response = session.get(
        DIRECTORY_URL,
        headers={
            "User-Agent": HEADERS[
                "User-Agent"
            ],
            "Accept-Language": HEADERS[
                "Accept-Language"
            ],
        },
        timeout=60,
    )

    response.raise_for_status()

    all_records: dict[
        str,
        dict[str, Any],
    ] = {}

    category_stats = {}

    for category_code, category_name in (
        TARGET_CATEGORIES.items()
    ):
        print()
        print("=" * 72)
        print(
            "[CATEGORY]",
            category_code,
            category_name,
        )

        first_response = fetch_page(
            session,
            category_code=category_code,
            category_name=category_name,
            page=1,
        )

        exhibitors = first_response.get(
            "exhibitors",
            {},
        )

        total = int(
            exhibitors.get("total", 0)
            or 0
        )

        total_pages = int(
            exhibitors.get(
                "total_page",
                0,
            )
            or 0
        )

        print("Total:", total)
        print("Pages:", total_pages)

        category_count = 0

        for page in range(
            1,
            total_pages + 1,
        ):
            if page == 1:
                page_data = first_response
            else:
                page_data = fetch_page(
                    session,
                    category_code=category_code,
                    category_name=category_name,
                    page=page,
                )

                time.sleep(0.3)

            records = (
                page_data
                .get("exhibitors", {})
                .get("data", [])
            )

            print(
                f"  Page {page}/{total_pages}:",
                len(records),
            )

            for raw_record in records:
                normalized = normalize_record(
                    raw_record,
                    category_code,
                    category_name,
                )

                unique_key = (
                    normalized.get(
                        "detail_url"
                    )
                    or normalized.get(
                        "company_name",
                        "",
                    ).strip().lower()
                )

                if not unique_key:
                    continue

                if unique_key in all_records:
                    merge_record(
                        all_records[
                            unique_key
                        ],
                        normalized,
                    )
                else:
                    all_records[
                        unique_key
                    ] = normalized

                category_count += 1

        category_stats[
            category_code
        ] = {
            "name": category_name,
            "official_total": total,
            "records_received": (
                category_count
            ),
        }

    records_list = list(
        all_records.values()
    )

    records_list.sort(
        key=lambda item: (
            item.get(
                "company_name",
                "",
            ).lower()
        )
    )

    output = {
        "event": (
            "Cosmoprof Worldwide "
            "Bologna 2026"
        ),
        "year": 2026,
        "source_url": DIRECTORY_URL,
        "api_url": API_URL,
        "categories": (
            TARGET_CATEGORIES
        ),
        "total_unique_exhibitors": (
            len(records_list)
        ),
        "exhibitors": records_list,
    }

    metadata = {
        "event": (
            "Cosmoprof Worldwide "
            "Bologna 2026"
        ),
        "year": 2026,
        "category_stats": (
            category_stats
        ),
        "total_unique_exhibitors": (
            len(records_list)
        ),
    }

    save_json(
        OUTPUT_PATH,
        output,
    )

    save_json(
        METADATA_PATH,
        metadata,
    )

    print()
    print("=" * 72)
    print("[BOLOGNA SYNC COMPLETE]")
    print("=" * 72)
    print(
        "Unique exhibitors:",
        len(records_list),
    )
    print(
        "Catalog:",
        OUTPUT_PATH,
    )
    print(
        "Metadata:",
        METADATA_PATH,
    )


if __name__ == "__main__":
    main()