import sys
from urllib.parse import urlparse

import requests


sys.stdout.reconfigure(
    encoding="utf-8",
    errors="replace",
)


BASE_URL = "https://exhibitors.informamarkets-info.com"

EVENT_CODE = "CA2025"
EVENT_NAME = "Cosmoprof Asia"
EVENT_YEAR = 2025

EVENT_URL = f"{BASE_URL}/event/{EVENT_CODE}/"
API_URL = f"{BASE_URL}/api"


# 這些是 Cosmoprof Asia 2025 官方名錄本身的識別資料，
# 不是使用者搜尋條件。
FAIR_ID = "umrrtUVxCm4v3+KipzqJ7g=="
FAIR_CODE = "b0aBxsxe1UmmHPDAvQ+OqQ=="


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Referer": EVENT_URL,
    "Accept": (
        "application/json, "
        "text/javascript, "
        "*/*; q=0.01"
    ),
    "X-Requested-With": "XMLHttpRequest",
}


def normalize_website(url: str) -> str:
    """
    將參展商名錄中的網站轉成可使用格式。

    例如：
    www.example.com
    轉成：
    https://www.example.com
    """

    cleaned = str(url or "").strip()

    if not cleaned:
        return ""

    if not cleaned.startswith(
        ("http://", "https://")
    ):
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)

    if not parsed.netloc:
        return ""

    return cleaned


def build_api_params(
    start: int = 0,
    length: int = 10000,
) -> dict:
    """
    建立官方參展商 API 所需參數。

    此處不放商品、國家或天然定位篩選，
    因為這些應由 SearchProfile 決定。
    """

    return {
        "fn": "getExhibitor",
        "orderfields": (
            '["FeaturedExhibitor",'
            '"ExhibitorNameEn",'
            '"StandNoStr",'
            '"CountryEn"]'
        ),
        "filter[country]": "",
        "filter[companyprefix]": "",
        "filter[productcategory]": "",
        "filter[hashtags]": "",
        "filter[businessnature]": "",
        "filter[exhibitortype]": "",
        "filter[venue]": "",
        "filter[fairlocation]": "",
        "filter[new]": "",
        "filter[sustainable]": "",
        "filter[besustainable]": "",
        "HideEmptyProducts": 0,
        "order[0][column]": 0,
        "order[0][dir]": "desc",
        "order[1][column]": 1,
        "order[1][dir]": "asc",
        "start": start,
        "length": length,
        "draw": 1,
        "dt": 1,
        "SearchLog": 0,
        "FairID": FAIR_ID,
        "FairCode": FAIR_CODE,
        "UseOldCountry": "False",
        "MyList": 0,
        "Email": "",
        "Url": EVENT_URL,
    }


def fetch_all_exhibitors() -> list[dict]:
    """
    從 Cosmoprof Asia 官方 API 取得原始參展商資料。

    此函式只負責取得資料，不進行商品、
    品牌定位、國家或其他商業條件篩選。
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    page_response = session.get(
        EVENT_URL,
        timeout=30,
    )
    page_response.raise_for_status()

    response = session.get(
        API_URL,
        params=build_api_params(),
        timeout=90,
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except requests.JSONDecodeError as error:
        preview = response.text[:1000]

        raise RuntimeError(
            "Cosmoprof Asia API "
            f"未回傳有效 JSON：{preview}"
        ) from error

    exhibitors = payload.get("data", [])

    if not isinstance(exhibitors, list):
        raise RuntimeError(
            "Cosmoprof Asia API 的 data "
            "欄位不是清單格式。"
        )

    print(
        f"[COSMOPROF ASIA] "
        f"取得 {len(exhibitors)} 家參展商"
    )

    return exhibitors


def normalize_exhibitor(
    raw: dict,
) -> dict:
    """
    將官方 API 欄位轉成系統共用格式。

    其他展覽來源之後也應輸出相同欄位，
    才能共同交給 candidate_filter.py。
    """

    exhibitor_id = str(
        raw.get("ExhibitorID", "")
    ).strip()

    company_name = str(
        raw.get("ExhibitorNameEn", "")
    ).strip()

    country = str(
        raw.get("CountryEn", "")
    ).strip()

    official_url = normalize_website(
        raw.get("LinkEn", "")
    )

    product_category = str(
        raw.get("ProductCategoryEn", "")
    ).strip()

    exhibitor_type = str(
        raw.get("ExhibitorTypeEn", "")
    ).strip()

    description = str(
        raw.get("DescEn", "")
    ).strip()

    booth = str(
        raw.get("StandNo", "")
    ).strip()

    return {
        "company_name": company_name,
        "country": country,
        "official_url": official_url,
        "product_category": product_category,
        "exhibitor_type": exhibitor_type,
        "description": description,
        "booth": booth,
        "exhibitor_id": exhibitor_id,
        "exhibition": EVENT_NAME,
        "exhibition_year": EVENT_YEAR,
        "source": (
            f"{EVENT_NAME} {EVENT_YEAR}"
        ),
        "source_url": EVENT_URL,
    }


def get_all_exhibitors() -> list[dict]:
    """
    取得並標準化所有參展商。

    回傳的仍是完整名錄；
    是否符合使用者條件，交給共用篩選器。
    """

    raw_exhibitors = fetch_all_exhibitors()

    return [
        normalize_exhibitor(raw)
        for raw in raw_exhibitors
    ]


if __name__ == "__main__":
    exhibitors = get_all_exhibitors()

    print(
        f"[NORMALIZED] "
        f"完成 {len(exhibitors)} 筆標準化"
    )

    print("\n[FIRST 5 EXHIBITORS]")

    for exhibitor in exhibitors[:5]:
        print("-" * 80)
        print(
            "公司：",
            exhibitor["company_name"],
        )
        print(
            "國家：",
            exhibitor["country"],
        )
        print(
            "官網：",
            exhibitor["official_url"],
        )
        print(
            "分類：",
            exhibitor["product_category"],
        )