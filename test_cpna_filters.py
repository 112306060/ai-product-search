import json
from pathlib import Path

import requests

from modules.exhibitions.cosmoprof_north_america import (
    API_HEADERS,
    BASE_URL,
    create_session,
)


FILTER_API_URL = (
    f"{BASE_URL}/api/v1/search/filters"
)

OUTPUT_PATH = Path(
    "data/cpna_debug/exhibitor_filters.json"
)


def main():
    session = create_session()

    response = session.post(
        FILTER_API_URL,
        headers=API_HEADERS,
        json={
            "type": "exhibitors",
        },
        timeout=30,
    )

    print(
        "[STATUS]",
        response.status_code,
    )

    response.raise_for_status()

    payload = response.json()

    print(
        "[RESPONSE CODE]",
        payload.get("code"),
    )

    data = payload.get("data", {})

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

    filter_list = (
        data.get("list", {})
        if isinstance(data, dict)
        else {}
    )

    print(
        "[FILTER KEYS]",
        list(filter_list.keys())
        if isinstance(filter_list, dict)
        else type(filter_list),
    )

    if isinstance(filter_list, dict):
        for key, value in filter_list.items():
            print()
            print(
                f"[FILTER] {key}"
            )

            print(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                )[:4000]
            )

    print()
    print(
        "[SAVED]",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()