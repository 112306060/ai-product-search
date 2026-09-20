import json
from pathlib import Path

from modules.exhibitions.cosmoprof_north_america import (
    API_HEADERS,
    API_URL,
    create_session,
)


OUTPUT_PATH = Path(
    "data/cpna_debug/hair_care_exhibitors.json"
)


def main():
    session = create_session()

    payload = {
        "page": 1,
        "limit": 60,
        "cfilters": [
            {
                "HallCode": "option-8",
            }
        ],
    }

    print(
        "[REQUEST PAYLOAD]",
        payload,
    )

    response = session.post(
        API_URL,
        headers=API_HEADERS,
        json=payload,
        timeout=30,
    )

    print(
        "[STATUS]",
        response.status_code,
    )

    response.raise_for_status()

    result = response.json()

    print(
        "[RESPONSE CODE]",
        result.get("code"),
    )

    data = result.get("data", {})

    if not isinstance(data, dict):
        data = {}

    exhibitors = data.get("list", [])

    if not isinstance(exhibitors, list):
        exhibitors = []

    print(
        "[TOTAL HAIR CARE]",
        data.get("total"),
    )

    print(
        "[LIST COUNT]",
        len(exhibitors),
    )

    print()
    print(
        "[FIRST 10]"
    )

    for item in exhibitors[:10]:
        stands = item.get(
            "stands",
            [],
        )

        booth_values = []

        for stand_group in stands:
            if not isinstance(
                stand_group,
                dict,
            ):
                continue

            hall = stand_group.get(
                "hall",
                "",
            )

            stand = stand_group.get(
                "stand",
                "",
            )

            booth = (
                f"{hall} / {stand}"
            ).strip(" /")

            if booth:
                booth_values.append(
                    booth
                )

        print(
            "-",
            item.get("name"),
            "|",
            "；".join(booth_values),
            "|",
            item.get("url"),
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "[SAVED]",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()