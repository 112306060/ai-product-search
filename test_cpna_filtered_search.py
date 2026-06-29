import json

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


TEST_PAYLOADS = {
    "baseline": {
        "page": 1,
        "limit": 20,
    },

    "hair_care_direct": {
        "page": 1,
        "limit": 20,
        "business_area": [404, 453],
    },

    "hair_care_selected_filters": {
        "page": 1,
        "limit": 20,
        "selectedFilters": {
            "business_area": [404, 453],
        },
    },

    "hair_hall_direct": {
        "page": 1,
        "limit": 20,
        "HallCode": ["option-8"],
    },

    "italy_direct": {
        "page": 1,
        "limit": 20,
        "country": [380],
    },

    "italy_selected_filters": {
        "page": 1,
        "limit": 20,
        "selectedFilters": {
            "country": [380],
        },
    },
    "shampoo_only": {
        "page": 1,
        "limit": 100,
        "business_area": [453],
    },

    "italy_hair_care": {
        "page": 1,
        "limit": 100,
        "country": [380],
        "business_area": [404, 453],
    },

    "europe_hair_natural": {
        "page": 1,
        "limit": 100,
        "country": [
            56,   # Belgium
            203,  # Czech Republic
            250,  # France
            276,  # Germany
            300,  # Greece
            372,  # Ireland
            380,  # Italy
            428,  # Latvia
            528,  # Netherlands
            578,  # Norway
            616,  # Poland
            620,  # Portugal
            724,  # Spain
            756,  # Switzerland
            826,  # United Kingdom
        ],
        "business_area": [
            404,  # Hair Care
            453,  # Shampoos + Conditioners
            419,  # Vegan
            503,  # Natural, Vegan, Bio and Halal
        ],
    },
}


def summarize_response(
    name: str,
    payload: dict,
    response_data: dict,
) -> None:
    data = response_data.get("data") or {}

    result_list = data.get("list") or []

    print()
    print("=" * 80)
    print("[TEST]", name)
    print("[PAYLOAD]")
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("[TOTAL]", data.get("total"))
    print("[RESULT COUNT]", len(result_list))

    for item in result_list[:5]:
        print(
            "-",
            item.get("name"),
            "| country:",
            item.get("country"),
            "| category_id:",
            item.get("category_id"),
        )


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    page_response = session.get(
        DIRECTORY_URL,
        timeout=30,
    )
    page_response.raise_for_status()

    for name, payload in TEST_PAYLOADS.items():
        try:
            response = session.post(
                API_URL,
                json=payload,
                timeout=30,
            )

            print()
            print(
                "[STATUS]",
                name,
                response.status_code,
            )

            response.raise_for_status()

            response_data = response.json()

            summarize_response(
                name=name,
                payload=payload,
                response_data=response_data,
            )

        except requests.RequestException as error:
            print(
                "[REQUEST ERROR]",
                name,
                error,
            )

        except ValueError:
            print(
                "[JSON ERROR]",
                name,
                response.text[:1000],
            )


if __name__ == "__main__":
    main()