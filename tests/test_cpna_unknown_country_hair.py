import requests


BASE_URL = (
    "https://lasvegas-directory."
    "cosmoprofnorthamerica.com"
)

DIRECTORY_URL = (
    f"{BASE_URL}/newfront/marketplace/exhibitors"
)

API_URL = (
    f"{BASE_URL}/api/v1/search/exhibitors"
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


COUNTRIES = {
    36: "Australia",
    56: "Belgium",
    76: "Brazil",
    124: "Canada",
    156: "China",
    203: "Czech Republic",
    214: "Dominican Republic",
    250: "France",
    276: "Germany",
    300: "Greece",
    344: "Hong Kong",
    356: "India",
    360: "Indonesia",
    372: "Ireland",
    376: "Israel",
    380: "Italy",
    392: "Japan",
    414: "Kuwait",
    428: "Latvia",
    458: "Malaysia",
    484: "Mexico",
    528: "Netherlands",
    578: "Norway",
    586: "Pakistan",
    591: "Panama",
    616: "Poland",
    620: "Portugal",
    630: "Puerto Rico",
    682: "Saudi Arabia",
    702: "Singapore",
    410: "South Korea",
    724: "Spain",
    756: "Switzerland",
    158: "Taiwan",
    792: "Turkey",
    826: "United Kingdom",
    840: "United States of America",
    704: "Vietnam",
}


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)

    response = session.get(
        DIRECTORY_URL,
        timeout=30,
    )
    response.raise_for_status()

    return session


def search_exhibitors(
    session: requests.Session,
    payload: dict,
) -> list[dict]:
    response = session.post(
        API_URL,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    response_json = response.json()
    data = response_json.get("data") or {}

    return data.get("list") or []


def exhibitor_key(exhibitor: dict) -> str:
    """
    優先使用展商 ID，比公司名稱更可靠。
    """
    exhibitor_id = exhibitor.get("id")

    if exhibitor_id is not None:
        return f"id:{exhibitor_id}"

    company_name = str(
        exhibitor.get("name") or ""
    ).strip().lower()

    return f"name:{company_name}"


def main():
    session = create_session()

    print("[取得全部 Hair Care 展商]")

    all_hair_exhibitors = search_exhibitors(
        session=session,
        payload={
            "page": 1,
            "limit": 100,
            "business_area": [
                404,
                453,
            ],
        },
    )

    all_hair_by_key = {
        exhibitor_key(exhibitor): exhibitor
        for exhibitor in all_hair_exhibitors
    }

    print(
        "全部 Hair Care 展商：",
        len(all_hair_by_key),
    )

    known_country_keys = set()
    country_mapping = {}

    for country_id, country_name in (
        COUNTRIES.items()
    ):
        exhibitors = search_exhibitors(
            session=session,
            payload={
                "page": 1,
                "limit": 100,
                "country": [country_id],
                "business_area": [
                    404,
                    453,
                ],
            },
        )

        for exhibitor in exhibitors:
            key = exhibitor_key(exhibitor)

            known_country_keys.add(key)

            country_mapping.setdefault(
                key,
                [],
            ).append(
                {
                    "country_id": country_id,
                    "country_name": country_name,
                }
            )

    unknown_keys = (
        set(all_hair_by_key)
        - known_country_keys
    )

    print()
    print("=" * 70)
    print("[已有官方國家的 Hair Care 展商]")
    print("=" * 70)

    for key in sorted(known_country_keys):
        exhibitor = all_hair_by_key.get(
            key,
            {},
        )

        company_name = exhibitor.get(
            "name",
            "",
        )

        countries = [
            item["country_name"]
            for item in country_mapping.get(
                key,
                [],
            )
        ]

        print(
            f"- {company_name}: "
            f"{', '.join(countries)}"
        )

    print()
    print("=" * 70)
    print("[國家未知的 Hair Care 展商]")
    print("=" * 70)

    for key in sorted(unknown_keys):
        exhibitor = all_hair_by_key[key]

        print()
        print(
            "公司：",
            exhibitor.get("name", ""),
        )
        print(
            "ID：",
            exhibitor.get("id"),
        )
        print(
            "slug：",
            exhibitor.get("url", ""),
        )
        print(
            "介紹：",
            str(
                exhibitor.get("about")
                or ""
            )[:300],
        )

    print()
    print("=" * 70)
    print("[統計]")
    print(
        "Hair Care 總數：",
        len(all_hair_by_key),
    )
    print(
        "已有官方國家：",
        len(known_country_keys),
    )
    print(
        "國家未知：",
        len(unknown_keys),
    )


if __name__ == "__main__":
    main()