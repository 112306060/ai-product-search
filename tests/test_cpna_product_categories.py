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

OUTPUT_PATH = Path(
    "data/cpna_debug/product_categories.json"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "x-application": "3",
    "x-lang": "en",
    "Origin": BASE_URL,
    "Referer": DIRECTORY_URL,
}


def request_endpoint(
    session: requests.Session,
    endpoint: str,
) -> dict | list | None:
    url = f"{BASE_URL}{endpoint}"

    print()
    print("=" * 80)
    print("[REQUEST]", url)
    print("=" * 80)

    response = session.get(
        url,
        timeout=30,
    )

    print(
        "[STATUS]",
        response.status_code,
    )

    print(
        "[CONTENT TYPE]",
        response.headers.get(
            "Content-Type",
            "",
        ),
    )

    response.raise_for_status()

    try:
        payload = response.json()

    except ValueError:
        print("[NOT JSON]")
        print(response.text[:3000])
        return None

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )[:10000]
    )

    return payload


def flatten_categories(
    value,
    results: list[dict],
) -> None:
    """
    遞迴找出所有帶有 id 與名稱的分類資料。
    因為目前還不知道官方 API 的巢狀格式。
    """
    if isinstance(value, dict):
        possible_id = (
            value.get("id")
            or value.get("category_id")
            or value.get("value")
        )

        possible_name = (
            value.get("name")
            or value.get("title")
            or value.get("label")
        )

        if (
            possible_id is not None
            and possible_name
        ):
            results.append(
                {
                    "id": possible_id,
                    "name": str(
                        possible_name
                    ).strip(),
                    "raw": value,
                }
            )

        for child in value.values():
            flatten_categories(
                child,
                results,
            )

    elif isinstance(value, list):
        for child in value:
            flatten_categories(
                child,
                results,
            )


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    # 先開首頁取得必要 Cookie
    print("[OPEN DIRECTORY]")

    page_response = session.get(
        DIRECTORY_URL,
        timeout=30,
    )

    print(
        "[DIRECTORY STATUS]",
        page_response.status_code,
    )

    page_response.raise_for_status()

    payload = request_endpoint(
        session=session,
        endpoint=(
            "/api/v1/dict/"
            "productCategories"
        ),
    )

    if payload is None:
        return

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    flattened = []
    flatten_categories(
        payload,
        flattened,
    )

    unique = {}

    for item in flattened:
        key = str(item["id"])

        if key not in unique:
            unique[key] = item

    print()
    print("=" * 80)
    print("[FLATTENED CATEGORY MAPPING]")
    print("=" * 80)

    for category_id, item in sorted(
        unique.items(),
        key=lambda pair: pair[0],
    ):
        print(
            f"{category_id}: "
            f"{item['name']}"
        )

    print()
    print("[CHECK TARGET IDS]")

    for target_id in (
        "531",
        "532",
    ):
        item = unique.get(target_id)

        if item:
            print(
                target_id,
                "=>",
                item["name"],
            )
        else:
            print(
                target_id,
                "=> not found",
            )

    print()
    print(
        "[SAVED]",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()