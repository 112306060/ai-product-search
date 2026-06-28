import html
import math
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = (
    "https://lasvegas-directory."
    "cosmoprofnorthamerica.com"
)

NEWFRONT_BASE_URL = f"{BASE_URL}/newfront"

EVENT_NAME = "Cosmoprof North America Las Vegas"
EVENT_YEAR = 2026

DIRECTORY_URL = (
    f"{NEWFRONT_BASE_URL}/marketplace/exhibitors"
)

API_URL = (
    f"{BASE_URL}/api/v1/search/exhibitors"
)

TEST_EXHIBITOR_URL = (
    f"{NEWFRONT_BASE_URL}/exhibitor/"
    "4ever-beauty-inc"
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


API_HEADERS = {
    **HEADERS,
    "Accept": "application/json",
    "Content-Type": "application/json",
    "x-application": "3",
    "x-lang": "en",
    "Origin": BASE_URL,
    "Referer": DIRECTORY_URL,
}


BLOCKED_EXTERNAL_DOMAINS = {
    "compusystems.com",
    "expoplatform.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "x.com",
    "twitter.com",
}


def clean_text(value: str) -> str:
    """
    清除 HTML entity、多餘空白與換行。
    """

    decoded = html.unescape(
        str(value or "")
    )

    return " ".join(
        decoded.split()
    )


def normalize_website(url: str) -> str:
    """
    將網址轉為完整格式。
    """

    cleaned = clean_text(url)

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


def is_blocked_domain(domain: str) -> bool:
    """
    排除社群網站與展覽追蹤網址。
    """

    cleaned_domain = (
        str(domain or "")
        .lower()
        .replace("www.", "")
    )

    if not cleaned_domain:
        return True

    if (
        "cosmoprofnorthamerica.com"
        in cleaned_domain
    ):
        return True

    return any(
        cleaned_domain == blocked_domain
        or cleaned_domain.endswith(
            f".{blocked_domain}"
        )
        for blocked_domain
        in BLOCKED_EXTERNAL_DOMAINS
    )


def create_session() -> requests.Session:
    """
    建立共用 HTTP Session。
    """

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    return session


def fetch_html(
    url: str,
    session: requests.Session | None = None,
) -> str:
    """
    讀取參展商詳情頁 HTML。
    """

    http = session or create_session()

    response = http.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    return response.text


def find_official_website(
    soup: BeautifulSoup,
    page_url: str,
) -> str:
    """
    尋找參展商真正官網。

    官方目錄可能將真正官網顯示在文字中，
    但 href 是 compusystems 追蹤網址。
    """

    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = clean_text(
            link.get("href", "")
        )

        visible_text = clean_text(
            link.get_text(" ")
        )

        if not href:
            continue

        visible_lower = (
            visible_text.lower()
        )

        if visible_lower.startswith(
            (
                "www.",
                "http://",
                "https://",
            )
        ):
            if visible_lower.startswith(
                ("http://", "https://")
            ):
                visible_url = visible_text

            else:
                visible_url = (
                    f"https://{visible_text}"
                )

            normalized_url = (
                normalize_website(
                    visible_url
                )
            )

            visible_domain = (
                urlparse(normalized_url)
                .netloc
                .lower()
                .replace("www.", "")
            )

            if (
                normalized_url
                and not is_blocked_domain(
                    visible_domain
                )
            ):
                return normalized_url

        absolute_url = urljoin(
            page_url,
            href,
        )

        parsed_url = urlparse(
            absolute_url
        )

        domain = (
            parsed_url.netloc
            .lower()
            .replace("www.", "")
        )

        if not domain:
            continue

        if is_blocked_domain(domain):
            continue

        if href.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return normalize_website(
                absolute_url
            )

    return ""


def find_booth(page_text: str) -> str:
    """
    從詳情頁文字解析攤位。
    """

    booth_patterns = [
        (
            r"(Main Hall\s*/\s*"
            r"[A-Za-z0-9\-]+)"
        ),
        (
            r"(Cosmopack\s*/\s*"
            r"[A-Za-z0-9\-]+)"
        ),
        (
            r"(Booth\s*(?:No\.?|#)?"
            r"\s*[:\-]?\s*"
            r"[A-Za-z0-9\-]+)"
        ),
        (
            r"(Stand\s*(?:No\.?|#)?"
            r"\s*[:\-]?\s*"
            r"[A-Za-z0-9\-]+)"
        ),
    ]

    for pattern in booth_patterns:
        match = re.search(
            pattern,
            page_text,
            flags=re.IGNORECASE,
        )

        if match:
            return clean_text(
                match.group(1)
            )

    return ""


def find_description(
    soup: BeautifulSoup,
) -> str:
    """
    尋找真正公司介紹。
    """

    description_selectors = [
        ".exhibitor-description",
        ".company-description",
        ".description",
        "[class*='description']",
        "[class*='about']",
    ]

    for selector in description_selectors:
        candidate = soup.select_one(
            selector
        )

        if not candidate:
            continue

        candidate_text = clean_text(
            candidate.get_text(" ")
        )

        if len(candidate_text) >= 40:
            return candidate_text

    valid_headings = {
        "about",
        "about us",
        "company overview",
        "company description",
        "description",
    }

    for candidate_heading in soup.find_all(
        ["h2", "h3", "h4"]
    ):
        heading_text = clean_text(
            candidate_heading.get_text(
                " "
            )
        ).lower()

        if heading_text not in valid_headings:
            continue

        description_parts = []

        current = (
            candidate_heading
            .find_next_sibling()
        )

        while current:
            if current.name in {
                "h1",
                "h2",
                "h3",
                "h4",
            }:
                break

            current_text = clean_text(
                current.get_text(" ")
            )

            if current_text:
                description_parts.append(
                    current_text
                )

            current = (
                current.find_next_sibling()
            )

        combined = clean_text(
            " ".join(
                description_parts
            )
        )

        if len(combined) >= 40:
            return combined

    meta_description = soup.find(
        "meta",
        attrs={
            "name": "description",
        },
    )

    if meta_description:
        return clean_text(
            meta_description.get(
                "content",
                "",
            )
        )

    return ""


def parse_exhibitor_page(
    html_text: str,
    page_url: str,
) -> dict:
    """
    解析單一官方參展商詳情頁。
    """

    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    heading = soup.find(
        ["h1", "h2"]
    )

    company_name = (
        clean_text(
            heading.get_text(" ")
        )
        if heading
        else ""
    )

    page_text = clean_text(
        soup.get_text(" ")
    )

    return {
        "company_name": company_name,
        "country": "",
        "official_url": (
            find_official_website(
                soup=soup,
                page_url=page_url,
            )
        ),
        "product_category": "",
        "exhibitor_type": "",
        "description": (
            find_description(soup)
        ),
        "booth": (
            find_booth(page_text)
        ),
        "exhibitor_id": (
            page_url.rstrip("/")
            .split("/")[-1]
        ),
        "exhibition": EVENT_NAME,
        "exhibition_year": EVENT_YEAR,
        "source": (
            f"{EVENT_NAME} {EVENT_YEAR}"
        ),
        "source_url": page_url,
    }


def fetch_exhibitor(
    page_url: str,
    session: requests.Session | None = None,
) -> dict:
    """
    下載並解析單一參展商詳情頁。
    """

    html_text = fetch_html(
        url=page_url,
        session=session,
    )

    return parse_exhibitor_page(
        html_text=html_text,
        page_url=page_url,
    )


def build_exhibitor_page_url(
    slug: str,
) -> str:
    """
    使用 API 的 url 欄位建立官方詳情頁。
    """

    cleaned_slug = (
        clean_text(slug)
        .strip("/")
    )

    if not cleaned_slug:
        return ""

    return (
        f"{NEWFRONT_BASE_URL}/"
        f"exhibitor/{cleaned_slug}"
    )


def build_booth_from_stands(
    stands: list,
) -> str:
    """
    將 API 的攤位資料轉為可閱讀格式。
    """

    booth_values = []

    for stand_group in stands or []:
        if not isinstance(
            stand_group,
            dict,
        ):
            continue

        hall = clean_text(
            stand_group.get("hall", "")
        )

        stand_name = clean_text(
            stand_group.get("stand", "")
        )

        if hall and stand_name:
            booth_value = (
                f"{hall} / {stand_name}"
            )

        elif stand_name:
            booth_value = stand_name

        else:
            booth_value = hall

        if (
            booth_value
            and booth_value not in booth_values
        ):
            booth_values.append(
                booth_value
            )

    return "；".join(
        booth_values
    )


def normalize_api_exhibitor(
    item: dict,
) -> dict:
    """
    將官方 API 清單資料轉為系統共用格式。
    """

    slug = clean_text(
        item.get("url", "")
    )

    return {
        "company_name": clean_text(
            item.get("name", "")
        ),
        "country": clean_text(
            item.get("country", "")
        ),
        "official_url": "",
        "product_category": "",
        "product_category_id": (
            item.get("category_id")
        ),
        "exhibitor_type": ", ".join(
            item.get("role", [])
            if isinstance(
                item.get("role"),
                list,
            )
            else []
        ),
        "description": clean_text(
            item.get("about", "")
        ),
        "booth": (
            build_booth_from_stands(
                item.get("stands", [])
            )
        ),
        "exhibitor_id": item.get("id"),
        "external_id": item.get(
            "external_id"
        ),
        "slug": slug,
        "exhibitor_page_url": (
            build_exhibitor_page_url(
                slug
            )
        ),
        "is_new": bool(
            item.get("isNew", False)
        ),
        "exhibition": EVENT_NAME,
        "exhibition_year": EVENT_YEAR,
        "source": (
            f"{EVENT_NAME} {EVENT_YEAR}"
        ),
        "source_url": (
            build_exhibitor_page_url(
                slug
            )
        ),
    }


def fetch_exhibitor_page_list(
    page: int = 1,
    limit: int = 12,
    session: requests.Session | None = None,
) -> dict:
    """
    從官方 API 取得單頁參展商清單。
    """

    http = session or create_session()

    response = http.post(
        API_URL,
        headers=API_HEADERS,
        json={
            "page": page,
            "limit": limit,
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if payload.get("code") != 200:
        raise RuntimeError(
            "Cosmoprof North America API "
            f"回傳錯誤：{payload}"
        )

    data = payload.get("data", {})

    if not isinstance(data, dict):
        data = {}

    raw_list = data.get("list", [])

    if not isinstance(raw_list, list):
        raw_list = []

    normalized_list = [
        normalize_api_exhibitor(item)
        for item in raw_list
        if isinstance(item, dict)
    ]

    return {
        "page": page,
        "limit": limit,
        "total": int(
            data.get("total", 0) or 0
        ),
        "list": normalized_list,
    }
def fetch_filtered_exhibitor_page(
    page: int = 1,
    limit: int = 60,
    hall_code: str = "",
    country_ids: list[int] | None = None,
    business_area_ids: list[int] | None = None,
    session: requests.Session | None = None,
) -> dict:
    """
    使用官方篩選條件取得參展商。

    hall_code:
        option-8 = Hair Care
        option-2 = Skin Care, Makeup & Fragrance
        option-6 = Nails
        option-1 = Cosmopack
    """

    http = session or create_session()

    payload = {
        "page": page,
        "limit": limit,
    }

    cfilters = []

    if hall_code:
        cfilters.append(
            {
                "HallCode": hall_code,
            }
        )

    if cfilters:
        payload["cfilters"] = cfilters

    if country_ids:
        payload["country"] = country_ids

    if business_area_ids:
        payload["business_area"] = (
            business_area_ids
        )

    response = http.post(
        API_URL,
        headers=API_HEADERS,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()

    if result.get("code") != 200:
        raise RuntimeError(
            "Cosmoprof North America "
            f"篩選 API 回傳錯誤：{result}"
        )

    data = result.get("data", {})

    if not isinstance(data, dict):
        data = {}

    raw_list = data.get("list", [])

    if not isinstance(raw_list, list):
        raw_list = []

    records = [
        normalize_api_exhibitor(item)
        for item in raw_list
        if isinstance(item, dict)
    ]

    return {
        "page": page,
        "limit": limit,
        "total": int(
            data.get("total", 0) or 0
        ),
        "list": records,
    }


def get_filtered_exhibitor_summaries(
    hall_code: str = "option-8",
    country_ids: list[int] | None = None,
    business_area_ids: list[int] | None = None,
    max_records: int | None = None,
    page_limit: int = 60,
) -> list[dict]:
    """
    分頁取得符合官方篩選條件的參展商。

    預設只抓 Hair Care。
    """

    session = create_session()

    first_result = (
        fetch_filtered_exhibitor_page(
            page=1,
            limit=page_limit,
            hall_code=hall_code,
            country_ids=country_ids,
            business_area_ids=(
                business_area_ids
            ),
            session=session,
        )
    )

    total = first_result["total"]

    print(
        "[COSMOPROF NORTH AMERICA FILTER]",
        f"符合官方條件共 {total} 家",
    )

    records = list(
        first_result["list"]
    )

    if (
        max_records is not None
        and len(records) >= max_records
    ):
        return records[:max_records]

    total_pages = max(
        1,
        math.ceil(
            total / page_limit
        ),
    )

    for page_number in range(
        2,
        total_pages + 1,
    ):
        print(
            "[CPNA FILTER PAGE]",
            f"{page_number}/{total_pages}",
        )

        result = (
            fetch_filtered_exhibitor_page(
                page=page_number,
                limit=page_limit,
                hall_code=hall_code,
                country_ids=country_ids,
                business_area_ids=(
                    business_area_ids
                ),
                session=session,
            )
        )

        records.extend(
            result["list"]
        )

        if (
            max_records is not None
            and len(records)
            >= max_records
        ):
            return records[:max_records]

    return records

def get_all_exhibitor_summaries(
    max_records: int | None = None,
    page_limit: int = 60,
) -> list[dict]:
    """
    分頁取得官方參展商清單。

    max_records:
        測試時可限制筆數。
        正式抓取時傳入 None。
    """

    session = create_session()

    first_result = (
        fetch_exhibitor_page_list(
            page=1,
            limit=page_limit,
            session=session,
        )
    )

    total = first_result["total"]

    print(
        "[COSMOPROF NORTH AMERICA]",
        f"官方參展商共 {total} 家",
    )

    records = list(
        first_result["list"]
    )

    if (
        max_records is not None
        and len(records) >= max_records
    ):
        return records[:max_records]

    total_pages = max(
        1,
        math.ceil(
            total / page_limit
        ),
    )

    for page_number in range(
        2,
        total_pages + 1,
    ):
        print(
            "[COSMOPROF NORTH AMERICA PAGE]",
            f"{page_number}/{total_pages}",
        )

        result = (
            fetch_exhibitor_page_list(
                page=page_number,
                limit=page_limit,
                session=session,
            )
        )

        records.extend(
            result["list"]
        )

        if (
            max_records is not None
            and len(records)
            >= max_records
        ):
            return records[:max_records]

    return records
def enrich_exhibitor_summary(
    summary: dict,
    session: requests.Session | None = None,
) -> dict:
    """
    讀取參展商詳情頁，補上官網、描述、國家等資料。
    """

    page_url = clean_text(
        summary.get("exhibitor_page_url", "")
    )

    if not page_url:
        return summary

    try:
        detail = fetch_exhibitor(
            page_url=page_url,
            session=session,
        )

    except Exception as error:
        print(
            "[CPNA DETAIL FAILED]",
            summary.get("company_name", ""),
            error,
        )

        return summary

    merged = {
        **summary,
    }

    for field in [
        "official_url",
        "country",
        "product_category",
        "exhibitor_type",
        "description",
        "booth",
    ]:
        detail_value = clean_text(
            detail.get(field, "")
        )

        if detail_value:
            merged[field] = detail_value

    # 官方 API 清單中的公司名稱較可靠，
    # 不用詳情頁標題覆蓋。
    merged["company_name"] = clean_text(
        summary.get("company_name", "")
    )

    merged["source_url"] = page_url

    return merged


def enrich_exhibitors(
    exhibitors: list[dict],
    max_records: int | None = None,
) -> list[dict]:
    """
    批次補齊參展商詳情資料。
    """

    session = create_session()

    selected = (
        exhibitors[:max_records]
        if max_records is not None
        else exhibitors
    )

    enriched = []

    total = len(selected)

    for index, summary in enumerate(
        selected,
        start=1,
    ):
        company_name = clean_text(
            summary.get("company_name", "")
        )

        print(
            "[CPNA DETAIL]",
            f"{index}/{total}",
            company_name,
        )

        record = enrich_exhibitor_summary(
            summary=summary,
            session=session,
        )

        enriched.append(record)

    return enriched

if __name__ == "__main__":
    summaries = (
        get_filtered_exhibitor_summaries(
            hall_code="option-8",
            max_records=10,
            page_limit=60,
        )
    )

    print()
    print(
        "[HAIR CARE SUMMARIES]",
        len(summaries),
    )

    for exhibitor in summaries:
        print("-" * 60)

        print(
            "公司：",
            exhibitor["company_name"],
        )

        print(
            "攤位：",
            exhibitor["booth"],
        )

        print(
            "詳情頁：",
            exhibitor[
                "exhibitor_page_url"
            ],
        )