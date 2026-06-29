import json
from pathlib import Path

import requests


BASE_URL = (
    "https://lasvegas-directory."
    "cosmoprofnorthamerica.com"
)

DIRECTORY_URL = (
    f"{BASE_URL}/newfront/marketplace/exhibitors"
)

API_URL = (
    f"{BASE_URL}/api/v1/search/filters"
)

OUTPUT_DIR = Path(
    "data/cpna_debug/search_filters"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "x-application": "3",
    "x-lang": "en",
    "Origin": BASE_URL,
    "Referer": DIRECTORY_URL,
}


FILTER_TYPES = [
    "exhibitors",
    "exhibitor",
    "products",
    "product",
    "marketplace",
]


def test_filter_type(
    session: requests.Session,
    filter_type: str,
) -> None:
    print()
    print("=" * 80)
    print(
        "[FILTER TYPE]",
        filter_type,
    )
    print("=" * 80)

    payload = {
        "type": filter_type,
    }

    response = session.post(
        API_URL,
        json=payload,
        timeout=30,
    )

    print(
        "[STATUS]",
        response.status_code,
    )

    try:
        data = response.json()

    except ValueError:
        print(
            response.text[:3000]
        )
        return

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )[:12000]
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        OUTPUT_DIR
        / f"{filter_type}.json"
    )

    output_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    response_data = data.get(
        "data",
        {},
    )

    filter_list = response_data.get(
        "list",
        {},
    )

    if isinstance(filter_list, dict):
        print()
        print(
            "[RETURNED FILTER KEYS]"
        )

        for key, value in (
            filter_list.items()
        ):
            if isinstance(value, list):
                print(
                    f"{key}: "
                    f"{len(value)} items"
                )
            else:
                print(
                    f"{key}: "
                    f"{type(value).__name__}"
                )


def main():
    session = requests.Session()
    session.headers.update(
        HEADERS
    )

    page_response = session.get(
        DIRECTORY_URL,
        timeout=30,
    )

    print(
        "[DIRECTORY STATUS]",
        page_response.status_code,
    )

    page_response.raise_for_status()

    for filter_type in FILTER_TYPES:
        try:
            test_filter_type(
                session=session,
                filter_type=filter_type,
            )

        except requests.RequestException as error:
            print(
                "[REQUEST ERROR]",
                filter_type,
                error,
            )


if __name__ == "__main__":
    main()