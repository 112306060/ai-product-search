import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.cosmoprof.com"

CATALOG_PATH = Path(
    "data/exhibitions/cosmoprof_bologna_2026.json"
)

OUTPUT_PATH = Path(
    "data/bologna_debug/bologna_detail_test.json"
)

HTML_OUTPUT_DIR = Path(
    "data/bologna_debug/detail_html"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
}


def clean_text(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        value or "",
    ).strip()


def make_safe_filename(value: str) -> str:
    safe_name = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        value or "company",
    )

    return safe_name.strip("_")[:100] or "company"


def extract_links(
    soup: BeautifulSoup,
    page_url: str,
) -> list[dict]:
    links = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        href = clean_text(
            anchor.get("href", "")
        )

        text = clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        if not href:
            continue

        absolute_url = urljoin(
            page_url,
            href,
        )

        links.append(
            {
                "text": text,
                "url": absolute_url,
            }
        )

    return links


def find_possible_website(
    links: list[dict],
) -> str:
    excluded_domains = [
        "cosmoprof.com",
        "cosmoprofawards.com",
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "youtube.com",
        "twitter.com",
        "x.com",
        "bolognafiere.it",
        "cosmeticaitalia.it",
        "opportunitaly.gov.it",
        "esteri.it",
        "ice.it",
        "isfcert.it",
        "archimedia.it",
        "cdn.jsdelivr.net",
        "ijfumtjo.cosmoprof.com",
        "website.com",
        "site.com",
    ]

    for link in links:
        url = link["url"].strip()
        lower_url = url.lower()

        if not lower_url.startswith(
            ("http://", "https://")
        ):
            continue

        if any(
            domain in lower_url
            for domain in excluded_domains
        ):
            continue

        return url

    return ""


def extract_detail_fields(
    soup: BeautifulSoup,
) -> dict:
    result = {
        "country": "",
        "exhibiting_area": "",
        "sector": "",
        "hall": "",
        "stand": "",
        "opening_dates": "",
    }

    details_box = soup.select_one(
        ".details-box"
    )

    if details_box is None:
        return result

    for item in details_box.select(
        "li.nav-item"
    ):
        text = clean_text(
            item.get_text(
                " ",
                strip=True,
            )
        )

        lower_text = text.lower()

        if lower_text.startswith(
            "country:"
        ):
            result["country"] = text.split(
                ":",
                1,
            )[1].strip()

        elif lower_text.startswith(
            "exhibiting area:"
        ):
            result[
                "exhibiting_area"
            ] = text.split(
                ":",
                1,
            )[1].strip()

        elif lower_text.startswith(
            "sector:"
        ):
            result["sector"] = text.split(
                ":",
                1,
            )[1].strip()

        elif lower_text.startswith(
            "hall:"
        ):
            hall_text = text.split(
                ":",
                1,
            )[1].strip()

            stand_match = re.search(
                r"stand\s*no\.?\s*:\s*(.+)$",
                hall_text,
                flags=re.IGNORECASE,
            )

            if stand_match:
                result["stand"] = clean_text(
                    stand_match.group(1)
                )

                hall_text = re.sub(
                    r"stand\s*no\.?\s*:\s*.+$",
                    "",
                    hall_text,
                    flags=re.IGNORECASE,
                )

            result["hall"] = clean_text(
                hall_text
            )

        elif lower_text.startswith(
            "opening dates:"
        ):
            result[
                "opening_dates"
            ] = text.split(
                ":",
                1,
            )[1].strip()

    return result


def extract_main_content_text(
    soup: BeautifulSoup,
) -> str:
    selectors = [
        ".details-box",
        ".exhibitor-detail",
        ".exhibitor-details",
        ".bible-detail",
        "main",
        "article",
    ]

    collected = []

    for selector in selectors:
        element = soup.select_one(
            selector
        )

        if element is None:
            continue

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if text:
            collected.append(text)

    if collected:
        return max(
            collected,
            key=len,
        )

    body = soup.body

    if body is None:
        return ""

    return clean_text(
        body.get_text(
            " ",
            strip=True,
        )
    )


def inspect_detail_page(
    session: requests.Session,
    exhibitor: dict,
) -> dict:
    company_name = exhibitor.get(
        "company_name",
        "",
    )

    detail_url = exhibitor.get(
        "detail_url",
        "",
    )

    print()
    print("=" * 72)
    print(
        "[DETAIL]",
        company_name,
    )
    print(detail_url)

    response = session.get(
        detail_url,
        headers=HEADERS,
        timeout=60,
    )

    print(
        "Status:",
        response.status_code,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    HTML_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_name = make_safe_filename(
        company_name
    )

    html_path = (
        HTML_OUTPUT_DIR
        / f"{safe_name}.html"
    )

    html_path.write_text(
        response.text,
        encoding="utf-8",
    )

    print(
        "HTML saved:",
        html_path,
    )

    detail_fields = extract_detail_fields(
        soup
    )

    links = extract_links(
        soup,
        response.url,
    )

    possible_website = (
        find_possible_website(
            links
        )
    )

    page_title = clean_text(
        soup.title.get_text(
            " ",
            strip=True,
        )
        if soup.title
        else ""
    )

    page_text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    main_content_text = (
        extract_main_content_text(
            soup
        )
    )

    print(
        "Title:",
        page_title,
    )

    print(
        "Country:",
        detail_fields["country"]
        or "(none)",
    )

    print(
        "Exhibiting area:",
        detail_fields[
            "exhibiting_area"
        ]
        or "(none)",
    )

    print(
        "Sector:",
        detail_fields["sector"]
        or "(none)",
    )

    print(
        "Hall:",
        detail_fields["hall"]
        or "(none)",
    )

    print(
        "Stand:",
        detail_fields["stand"]
        or "(none)",
    )

    print(
        "Possible website:",
        possible_website
        or "(none)",
    )

    print(
        "Text length:",
        len(page_text),
    )

    return {
        "company_name": company_name,
        "detail_url": detail_url,
        "status_code": (
            response.status_code
        ),
        "page_title": page_title,
        "country": (
            detail_fields["country"]
        ),
        "exhibiting_area": (
            detail_fields[
                "exhibiting_area"
            ]
        ),
        "detail_sector": (
            detail_fields["sector"]
        ),
        "detail_hall": (
            detail_fields["hall"]
        ),
        "detail_stand": (
            detail_fields["stand"]
        ),
        "detail_opening_dates": (
            detail_fields[
                "opening_dates"
            ]
        ),
        "possible_website": (
            possible_website
        ),
        "main_content_preview": (
            main_content_text[:3000]
        ),
        "page_text_preview": (
            page_text[:3000]
        ),
        "links": links[:150],
        "saved_html": str(
            html_path
        ),
    }


def main() -> None:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"找不到目錄檔案：{CATALOG_PATH}"
        )

    catalog = json.loads(
        CATALOG_PATH.read_text(
            encoding="utf-8"
        )
    )

    exhibitors = catalog.get(
        "exhibitors",
        [],
    )

    if not exhibitors:
        raise ValueError(
            "目錄中沒有 exhibitors 資料"
        )

    session = requests.Session()

    results = []

    for exhibitor in exhibitors[:5]:
        try:
            result = inspect_detail_page(
                session,
                exhibitor,
            )

        except requests.RequestException as exc:
            print(
                "Request failed:",
                exc,
            )

            result = {
                "company_name": (
                    exhibitor.get(
                        "company_name",
                        "",
                    )
                ),
                "detail_url": (
                    exhibitor.get(
                        "detail_url",
                        "",
                    )
                ),
                "error": str(exc),
            }

        results.append(result)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("[DETAIL TEST COMPLETE]")
    print("=" * 72)
    print(
        "Saved:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()