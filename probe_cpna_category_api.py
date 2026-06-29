import re
from urllib.parse import urljoin

import requests


BASE_URL = (
    "https://lasvegas-directory."
    "cosmoprofnorthamerica.com"
)

DIRECTORY_URL = (
    f"{BASE_URL}/newfront/marketplace/exhibitors"
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


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    print("[OPEN DIRECTORY]")
    response = session.get(
        DIRECTORY_URL,
        timeout=30,
    )
    response.raise_for_status()

    html = response.text

    script_urls = []

    for src in re.findall(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    ):
        script_url = urljoin(
            DIRECTORY_URL,
            src,
        )

        if script_url not in script_urls:
            script_urls.append(script_url)

    print(
        f"[FOUND SCRIPTS] {len(script_urls)}"
    )

    endpoint_pattern = re.compile(
        r"""["'](
            /api/
            [A-Za-z0-9_./?=&{}\-\[\]]+
        )["']""",
        flags=re.VERBOSE,
    )

    category_keywords = (
        "categor",
        "product",
        "filter",
        "taxonomy",
        "sector",
        "marketplace",
    )

    found_endpoints = set()

    for index, script_url in enumerate(
        script_urls,
        start=1,
    ):
        print(
            f"[SCRIPT {index}/{len(script_urls)}] "
            f"{script_url}"
        )

        try:
            script_response = session.get(
                script_url,
                timeout=60,
            )
            script_response.raise_for_status()

        except requests.RequestException as error:
            print(
                "[SCRIPT ERROR]",
                error,
            )
            continue

        javascript = script_response.text

        for match in endpoint_pattern.findall(
            javascript
        ):
            cleaned = match.strip()

            if any(
                keyword in cleaned.lower()
                for keyword in category_keywords
            ):
                found_endpoints.add(cleaned)

        # 額外找包含分類關鍵字附近的程式碼
        lower_script = javascript.lower()

        for keyword in category_keywords:
            start = 0

            while True:
                position = lower_script.find(
                    keyword,
                    start,
                )

                if position == -1:
                    break

                preview_start = max(
                    0,
                    position - 200,
                )
                preview_end = min(
                    len(javascript),
                    position + 300,
                )

                preview = javascript[
                    preview_start:preview_end
                ]

                if "/api/" in preview:
                    print()
                    print(
                        f"[MATCH: {keyword}]"
                    )
                    print(preview[:500])

                start = position + len(keyword)

    print()
    print("=" * 80)
    print("[POSSIBLE API ENDPOINTS]")
    print("=" * 80)

    if not found_endpoints:
        print(
            "沒有直接找到 API 字串，"
            "可能是由多段字串動態組合。"
        )

    for endpoint in sorted(
        found_endpoints
    ):
        print(endpoint)


if __name__ == "__main__":
    main()