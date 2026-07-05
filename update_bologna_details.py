import json
import re
import time
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


CATALOG_PATH = Path(
    "data/exhibitions/cosmoprof_bologna_2026.json"
)

BACKUP_PATH = Path(
    "data/exhibitions/cosmoprof_bologna_2026_before_details.json"
)

PROGRESS_PATH = Path(
    "data/exhibitions/cosmoprof_bologna_2026_detail_progress.json"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
}


def clean_text(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        value or "",
    ).strip()


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


def extract_detail_fields(
    soup: BeautifulSoup,
) -> dict[str, str]:
    result = {
        "country": "",
        "exhibiting_area": "",
        "sector": "",
        "hall": "",
        "stand": "",
        "opening_dates": "",
    }

    details_box = soup.select_one(
        ".details-box"
    )

    if details_box is None:
        return result

    for item in details_box.select(
        "li.nav-item"
    ):
        text = clean_text(
            item.get_text(
                " ",
                strip=True,
            )
        )

        lower_text = text.lower()

        if lower_text.startswith(
            "country:"
        ):
            result["country"] = text.split(
                ":",
                1,
            )[1].strip()

        elif lower_text.startswith(
            "exhibiting area:"
        ):
            result["exhibiting_area"] = (
                text.split(
                    ":",
                    1,
                )[1].strip()
            )

        elif lower_text.startswith(
            "sector:"
        ):
            result["sector"] = text.split(
                ":",
                1,
            )[1].strip()

        elif lower_text.startswith(
            "hall:"
        ):
            hall_text = text.split(
                ":",
                1,
            )[1].strip()

            stand_match = re.search(
                r"stand\s*no\.?\s*:\s*(.+)$",
                hall_text,
                flags=re.IGNORECASE,
            )

            if stand_match:
                result["stand"] = clean_text(
                    stand_match.group(1)
                )

                hall_text = re.sub(
                    r"stand\s*no\.?\s*:\s*.+$",
                    "",
                    hall_text,
                    flags=re.IGNORECASE,
                )

            result["hall"] = clean_text(
                hall_text
            )

        elif lower_text.startswith(
            "opening dates:"
        ):
            result["opening_dates"] = (
                text.split(
                    ":",
                    1,
                )[1].strip()
            )

    return result


def fetch_detail(
    session: requests.Session,
    detail_url: str,
) -> dict[str, str]:
    response = session.get(
        detail_url,
        headers=HEADERS,
        timeout=60,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    return extract_detail_fields(
        soup
    )


def main() -> None:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"找不到目錄：{CATALOG_PATH}"
        )

    catalog = json.loads(
        CATALOG_PATH.read_text(
            encoding="utf-8"
        )
    )

    exhibitors = catalog.get(
        "exhibitors",
        [],
    )

    if not BACKUP_PATH.exists():
        save_json(
            BACKUP_PATH,
            catalog,
        )

        print(
            "Backup created:",
            BACKUP_PATH,
        )

    session = requests.Session()

    success_count = 0
    failed_count = 0
    skipped_count = 0

    failed_records = []

    total = len(exhibitors)

    for index, exhibitor in enumerate(
        exhibitors,
        start=1,
    ):
        company_name = exhibitor.get(
            "company_name",
            "",
        )

        detail_url = exhibitor.get(
            "detail_url",
            "",
        )

        print()
        print(
            f"[{index}/{total}]",
            company_name,
        )

        if exhibitor.get("country"):
            print(
                "Skipped: country already exists"
            )

            skipped_count += 1
            continue

        if not detail_url:
            print(
                "Failed: no detail URL"
            )

            failed_count += 1

            failed_records.append(
                {
                    "company_name": (
                        company_name
                    ),
                    "error": (
                        "missing detail_url"
                    ),
                }
            )

            continue

        try:
            fields = fetch_detail(
                session,
                detail_url,
            )

            exhibitor["country"] = (
                fields["country"]
            )

            exhibitor[
                "exhibiting_area"
            ] = fields[
                "exhibiting_area"
            ]

            if fields["sector"]:
                exhibitor[
                    "detail_sector"
                ] = fields["sector"]

            if fields["hall"]:
                exhibitor["hall"] = (
                    fields["hall"]
                )

            if fields["stand"]:
                exhibitor["stand"] = (
                    fields["stand"]
                )

            if fields["opening_dates"]:
                exhibitor[
                    "opening_dates"
                ] = fields[
                    "opening_dates"
                ]

            exhibitor[
                "detail_fetch_status"
            ] = "success"

            print(
                "Country:",
                fields["country"]
                or "(none)",
            )

            success_count += 1

        except requests.RequestException as exc:
            print(
                "Request failed:",
                exc,
            )

            exhibitor[
                "detail_fetch_status"
            ] = "failed"

            exhibitor[
                "detail_fetch_error"
            ] = str(exc)

            failed_records.append(
                {
                    "company_name": (
                        company_name
                    ),
                    "detail_url": (
                        detail_url
                    ),
                    "error": str(exc),
                }
            )

            failed_count += 1

        except Exception as exc:
            print(
                "Parse failed:",
                exc,
            )

            exhibitor[
                "detail_fetch_status"
            ] = "failed"

            exhibitor[
                "detail_fetch_error"
            ] = str(exc)

            failed_records.append(
                {
                    "company_name": (
                        company_name
                    ),
                    "detail_url": (
                        detail_url
                    ),
                    "error": str(exc),
                }
            )

            failed_count += 1

        if index % 20 == 0:
            save_json(
                CATALOG_PATH,
                catalog,
            )

            print(
                "Progress saved at:",
                index,
            )

        time.sleep(0.25)

    country_count = sum(
        1
        for exhibitor in exhibitors
        if exhibitor.get("country")
    )

    catalog[
        "detail_enrichment"
    ] = {
        "total_exhibitors": total,
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "country_count": country_count,
        "website_available_publicly": False,
        "company_description_available_publicly": False,
    }

    save_json(
        CATALOG_PATH,
        catalog,
    )

    save_json(
        PROGRESS_PATH,
        {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "country_count": country_count,
            "failed_records": failed_records,
        },
    )

    print()
    print("=" * 72)
    print("[BOLOGNA DETAIL UPDATE COMPLETE]")
    print("=" * 72)
    print(
        "Total:",
        total,
    )
    print(
        "Success:",
        success_count,
    )
    print(
        "Failed:",
        failed_count,
    )
    print(
        "Skipped:",
        skipped_count,
    )
    print(
        "With country:",
        country_count,
    )
    print(
        "Updated catalog:",
        CATALOG_PATH,
    )
    print(
        "Progress report:",
        PROGRESS_PATH,
    )


if __name__ == "__main__":
    main()