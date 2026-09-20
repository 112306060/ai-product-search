import json
from pathlib import Path

import requests

from modules.exhibitions.cosmoprof_north_america import (
    BASE_URL,
    DIRECTORY_URL,
    HEADERS,
)


API_URL = (
    f"{BASE_URL}/api/v1/search/exhibitors"
)

OUTPUT_PATH = Path(
    "data/cpna_debug/exhibitors_api_response.json"
)


def main():
    session = requests.Session()

    session.headers.update(
        {
            **HEADERS,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-application": "3",
            "x-lang": "en",
            "Origin": BASE_URL,
            "Referer": DIRECTORY_URL,
        }
    )

    payload = {
        "page": 1,
        "limit": 12,
    }

    print(
        "[API URL]",
        API_URL,
    )

    print(
        "[REQUEST PAYLOAD]",
        payload,
    )

    response = session.post(
        API_URL,
        json=payload,
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
        data = response.json()

    except ValueError:
        print(
            "[NOT JSON]"
        )

        print(
            response.text[:2000]
        )

        return

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "[RESPONSE CODE]",
        data.get("code"),
    )

    response_data = (
        data.get("data")
        if isinstance(
            data.get("data"),
            dict,
        )
        else {}
    )

    exhibitors = (
        response_data.get("list")
        if isinstance(
            response_data.get("list"),
            list,
        )
        else []
    )

    print(
        "[TOTAL]",
        response_data.get("total"),
    )

    print(
        "[LIST COUNT]",
        len(exhibitors),
    )

    print(
        "[NEXT RESULT]",
        response_data.get("nextResult"),
    )

    print()
    print(
        "[FIRST EXHIBITOR RAW]"
    )

    if exhibitors:
        print(
            json.dumps(
                exhibitors[0],
                ensure_ascii=False,
                indent=2,
            )[:5000]
        )

    else:
        print(
            "No exhibitors returned."
        )

    print()
    print(
        "[SAVED]",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()