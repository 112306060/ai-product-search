import json
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

OUTPUT_DIR = Path("data/bologna_debug")


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


def save_json(
    path: Path,
    data: Any,
) -> None:
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def request_exhibitors(
    session: requests.Session,
    *,
    category: str = "",
    search_text: str = "",
    page: int = 1,
    results_per_page: int = 20,
) -> requests.Response:
    payload = {
        "super_search": search_text,
        "_Country": "",
        "_Category": category,
        "_Sector": "",
        "_Hall": "",
        "page_favorite_data": "",
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

    print()
    print("=" * 70)
    print("[BOLOGNA OFFICIAL API REQUEST]")
    print("=" * 70)
    print("Category:", category or "(all)")
    print("Search:", search_text or "(none)")
    print("Page:", page)
    print("Results per page:", results_per_page)
    print("API:", API_URL)

    response = session.post(
        API_URL,
        headers=HEADERS,
        data=payload,
        timeout=60,
    )

    print("Status:", response.status_code)
    print(
        "Content-Type:",
        response.headers.get(
            "content-type",
            "",
        ),
    )
    print(
        "Response bytes:",
        len(response.content),
    )

    return response


def inspect_response(
    response: requests.Response,
    output_name: str,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_path = OUTPUT_DIR / f"{output_name}_raw.txt"

    raw_path.write_text(
        response.text,
        encoding="utf-8",
    )

    print("Raw response saved:", raw_path)

    try:
        data = response.json()

    except requests.JSONDecodeError:
        print()
        print("[INVALID JSON]")
        print(response.text[:2000])
        return

    json_path = OUTPUT_DIR / f"{output_name}.json"

    save_json(
        json_path,
        data,
    )

    print("JSON saved:", json_path)
    print()

    if not isinstance(data, dict):
        print(
            "Unexpected JSON type:",
            type(data).__name__,
        )
        print(str(data)[:2000])
        return

    print("Top-level keys:", list(data.keys()))
    print("Code:", data.get("code"))

    exhibitors = data.get("exhibitors")

    if not isinstance(exhibitors, dict):
        print("No exhibitors object found.")
        print(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )[:3000]
        )
        return

    records = exhibitors.get("data") or []

    print(
        "Total records:",
        exhibitors.get("total"),
    )
    print(
        "Total pages:",
        exhibitors.get("total_page"),
    )
    print(
        "Current page records:",
        len(records),
    )

    print()
    print("[FIRST RECORDS]")

    for index, record in enumerate(
        records[:5],
        start=1,
    ):
        print()
        print("-" * 70)
        print("Record", index)
        print(
            json.dumps(
                record,
                ensure_ascii=False,
                indent=2,
            )[:3000]
        )


def main() -> None:
    session = requests.Session()

    print("[OPEN DIRECTORY PAGE]")

    page_response = session.get(
        DIRECTORY_URL,
        headers={
            "User-Agent": HEADERS["User-Agent"],
            "Accept-Language": HEADERS[
                "Accept-Language"
            ],
        },
        timeout=60,
    )

    print(
        "Directory status:",
        page_response.status_code,
    )

    page_response.raise_for_status()

    favorite_data = json.dumps(
        {
            "page_id": 7530,
            "data": [
                {
                    "cod": "C107",
                    "text": (
                        "Hair wash products "
                        "(lotions, powders, shampoos)"
                    ),
                    "el": "Category",
                }
            ],
        },
        ensure_ascii=False,
    )

    test_cases = [
        {
            "name": "category_with_underscore",
            "extra_payload": {
                "_Category": "C107",
            },
        },
        {
            "name": "category_without_underscore",
            "extra_payload": {
                "Category": "C107",
            },
        },
        {
            "name": "lowercase_category",
            "extra_payload": {
                "category": "C107",
            },
        },
        {
            "name": "favorite_data_only",
            "extra_payload": {
                "page_favorite_data": favorite_data,
            },
        },
        {
            "name": "category_and_favorite_data",
            "extra_payload": {
                "Category": "C107",
                "page_favorite_data": favorite_data,
            },
        },
        {
            "name": "underscore_and_favorite_data",
            "extra_payload": {
                "_Category": "C107",
                "page_favorite_data": favorite_data,
            },
        },
    ]

    for test_case in test_cases:
        payload = {
            "super_search": "",
            "page_favorite_data": "",
            "page_exh": "1",
            "rpp_exh": "20",
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

        payload.update(
            test_case["extra_payload"]
        )

        print()
        print("=" * 72)
        print("[TEST]", test_case["name"])
        print(
            "Extra payload:",
            test_case["extra_payload"],
        )

        response = session.post(
            API_URL,
            headers=HEADERS,
            data=payload,
            timeout=60,
        )

        print("Status:", response.status_code)
        print(
            "Response bytes:",
            len(response.content),
        )

        try:
            data = response.json()

        except requests.JSONDecodeError:
            print("[INVALID JSON]")
            print(response.text[:500])
            continue

        exhibitors = data.get(
            "exhibitors",
            {},
        )

        records = exhibitors.get(
            "data",
            [],
        )

        print(
            "Total:",
            exhibitors.get("total"),
        )
        print(
            "Total pages:",
            exhibitors.get("total_page"),
        )

        print(
            "First titles:",
            [
                item.get("title")
                for item in records[:3]
            ],
        )

        save_json(
            OUTPUT_DIR
            / (
                "bologna_test_"
                + test_case["name"]
                + ".json"
            ),
            data,
        )

if __name__ == "__main__":
    main()