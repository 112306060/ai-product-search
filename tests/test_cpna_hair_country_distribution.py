import time

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

    print("[OPEN DIRECTORY]")

    response = session.get(
        DIRECTORY_URL,
        timeout=30,
    )

    print(
        "[DIRECTORY STATUS]",
        response.status_code,
    )

    response.raise_for_status()

    return session


def search_country_hair_exhibitors(
    session: requests.Session,
    country_id: int,
    country_name: str,
    max_retries: int = 3,
) -> dict | None:
    payload = {
        "page": 1,
        "limit": 100,
        "country": [country_id],
        "business_area": [
            404,  # Hair Care
            453,  # Shampoos + Conditioners
        ],
    }

    print()
    print(
        f"[查詢中] {country_name} "
        f"(country_id={country_id})"
    )

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            response = session.post(
                API_URL,
                json=payload,
                timeout=30,
            )

            print(
                f"  [STATUS] "
                f"{response.status_code}"
            )

            response.raise_for_status()

            response_json = response.json()

            if not isinstance(
                response_json,
                dict,
            ):
                print(
                    "  [錯誤] API 回傳不是字典格式"
                )
                return None

            return response_json

        except requests.Timeout as error:
            print(
                f"  [重試 {attempt}/{max_retries}] "
                f"查詢逾時：{error}"
            )

        except requests.HTTPError as error:
            status_code = (
                error.response.status_code
                if error.response is not None
                else "unknown"
            )

            print(
                f"  [重試 {attempt}/{max_retries}] "
                f"HTTP 錯誤 {status_code}：{error}"
            )

        except requests.RequestException as error:
            print(
                f"  [重試 {attempt}/{max_retries}] "
                f"連線錯誤：{error}"
            )

        except ValueError as error:
            print(
                f"  [錯誤] JSON 解析失敗：{error}"
            )
            return None

        if attempt < max_retries:
            wait_seconds = 5 * attempt

            print(
                f"  [等待] {wait_seconds} 秒後重試"
            )

            time.sleep(
                wait_seconds
            )

    print(
        f"  [略過] {country_name} "
        f"連續 {max_retries} 次查詢失敗"
    )

    return None


def main():
    session = create_session()

    total_found = 0
    successful_country_count = 0
    failed_countries = []
    country_results = []

    print()
    print(
        "CPNA Hair Care 國家分布"
    )
    print("=" * 70)

    for country_id, country_name in (
        COUNTRIES.items()
    ):
        response_json = (
            search_country_hair_exhibitors(
                session=session,
                country_id=country_id,
                country_name=country_name,
            )
        )

        if response_json is None:
            failed_countries.append(
                country_name
            )

            time.sleep(2)
            continue

        successful_country_count += 1

        data = (
            response_json.get("data")
            or {}
        )

        total = int(
            data.get("total")
            or 0
        )

        exhibitors = (
            data.get("list")
            or []
        )

        if total > 0:
            total_found += total

            country_results.append(
                {
                    "country_id": country_id,
                    "country_name": (
                        country_name
                    ),
                    "total": total,
                    "exhibitors": [
                        exhibitor.get(
                            "name",
                            "",
                        )
                        for exhibitor
                        in exhibitors
                    ],
                }
            )

            print(
                f"  [找到] "
                f"{country_name}: {total}"
            )

            for exhibitor in exhibitors:
                company_name = (
                    exhibitor.get(
                        "name",
                        "",
                    )
                )

                print(
                    "    -",
                    company_name,
                )

        else:
            print(
                f"  [無結果] {country_name}"
            )

        # 避免短時間內大量請求造成 502
        time.sleep(2)

    print()
    print("=" * 70)
    print("[查詢摘要]")
    print(
        "成功查詢國家數：",
        successful_country_count,
    )
    print(
        "失敗國家數：",
        len(failed_countries),
    )
    print(
        "有髮品展商的國家數：",
        len(country_results),
    )
    print(
        "各國查詢結果加總：",
        total_found,
    )

    if failed_countries:
        print()
        print("[失敗國家]")

        for country_name in (
            failed_countries
        ):
            print(
                "-",
                country_name,
            )

    print()
    print("[有髮品展商的國家]")

    for result in country_results:
        print(
            f"- {result['country_name']}: "
            f"{result['total']}"
        )

    print()
    print(
        "官方 Hair Care API 總數應為：28"
    )

    if (
        not failed_countries
        and total_found == 28
    ):
        print(
            "[完成] 所有 28 家髮品展商"
            "皆可透過官方國家條件識別。"
        )

    elif not failed_countries:
        difference = 28 - total_found

        print(
            "[注意] 各國加總與官方總數不同。"
        )
        print(
            "差額：",
            difference,
        )
        print(
            "可能有展商未設定國家，"
            "或一家公司被登記在多個國家。"
        )

    else:
        print(
            "[未完成] 有國家查詢失敗，"
            "請稍後重新執行補測。"
        )


if __name__ == "__main__":
    main()