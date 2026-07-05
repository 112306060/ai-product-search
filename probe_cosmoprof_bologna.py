import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests


DIRECTORY_URLS = [
    (
        "https://www.cosmoprof.com/en/visit/"
        "exhibitors-directory/digital-directory/"
    ),
    (
        "https://my.cosmoprof.com/en/visit/"
        "exhibitors-directory/digital-directory/"
    ),
    (
        "https://www.cosmoprof.com/en/visit/"
        "exhibitors-directory/exhibitors-list/"
    ),
    (
        "https://my.cosmoprof.com/en/visit/"
        "exhibitors-directory/exhibitors-list/"
    ),
]

OUTPUT_DIR = Path(
    "data/bologna_debug"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "en-US,en;q=0.9,it;q=0.8"
    ),
}


def safe_filename(value: str) -> str:
    cleaned = re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        value,
    ).strip("_")

    return cleaned[:100] or "page"


def extract_script_urls(
    html: str,
    base_url: str,
) -> list[str]:
    patterns = [
        r'<script[^>]+src=["\']([^"\']+)["\']',
        r'<link[^>]+href=["\']([^"\']+\.js[^"\']*)["\']',
    ]

    results = []

    for pattern in patterns:
        for match in re.findall(
            pattern,
            html,
            flags=re.IGNORECASE,
        ):
            absolute_url = urljoin(
                base_url,
                match,
            )

            if absolute_url not in results:
                results.append(
                    absolute_url
                )

    return results


def extract_possible_endpoints(
    text: str,
) -> list[str]:
    patterns = [
        r'https?://[^"\s\'<>]+',
        r'["\'](/api/[^"\']+)["\']',
        r'["\']([^"\']*graphql[^"\']*)["\']',
        r'["\']([^"\']*exhibitor[^"\']*)["\']',
        r'["\']([^"\']*search[^"\']*)["\']',
        r'["\']([^"\']*directory[^"\']*)["\']',
    ]

    keywords = {
        "api",
        "graphql",
        "exhibitor",
        "exhibitors",
        "directory",
        "search",
        "filter",
        "product",
        "company",
    }

    results = []

    for pattern in patterns:
        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:
            if isinstance(match, tuple):
                match = next(
                    (
                        item
                        for item in match
                        if item
                    ),
                    "",
                )

            cleaned = str(
                match
            ).strip()

            lower = cleaned.lower()

            if not any(
                keyword in lower
                for keyword in keywords
            ):
                continue

            if cleaned not in results:
                results.append(
                    cleaned
                )

    return results


def fetch_url(
    session: requests.Session,
    url: str,
) -> requests.Response | None:
    try:
        response = session.get(
            url,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True,
        )

    except requests.RequestException as error:
        print(
            "[REQUEST FAILED]",
            url,
            error,
        )
        return None

    print(
        "[REQUEST]",
        response.status_code,
        response.url,
        f"{len(response.content)} bytes",
    )

    return response


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    session = requests.Session()

    report = {
        "pages": [],
        "script_urls": [],
        "possible_endpoints": [],
    }

    all_script_urls = []

    for index, url in enumerate(
        DIRECTORY_URLS,
        start=1,
    ):
        response = fetch_url(
            session,
            url,
        )

        if response is None:
            continue

        content_type = response.headers.get(
            "content-type",
            "",
        )

        html = response.text

        output_path = (
            OUTPUT_DIR
            / f"page_{index}.html"
        )

        output_path.write_text(
            html,
            encoding="utf-8",
        )

        scripts = extract_script_urls(
            html,
            response.url,
        )

        endpoints = extract_possible_endpoints(
            html
        )

        report["pages"].append(
            {
                "requested_url": url,
                "final_url": response.url,
                "status_code": (
                    response.status_code
                ),
                "content_type": content_type,
                "size_bytes": len(
                    response.content
                ),
                "saved_to": str(
                    output_path
                ),
                "script_count": len(
                    scripts
                ),
                "possible_endpoint_count": (
                    len(endpoints)
                ),
            }
        )

        for script_url in scripts:
            if script_url not in all_script_urls:
                all_script_urls.append(
                    script_url
                )

        for endpoint in endpoints:
            if (
                endpoint
                not in report[
                    "possible_endpoints"
                ]
            ):
                report[
                    "possible_endpoints"
                ].append(
                    endpoint
                )

    print()
    print(
        "[SCRIPT FILES]",
        len(all_script_urls),
    )

    for index, script_url in enumerate(
        all_script_urls,
        start=1,
    ):
        response = fetch_url(
            session,
            script_url,
        )

        if response is None:
            continue

        script_name = (
            f"script_{index}_"
            + safe_filename(
                script_url
            )
            + ".js"
        )

        script_path = (
            OUTPUT_DIR
            / script_name
        )

        script_text = response.text

        script_path.write_text(
            script_text,
            encoding="utf-8",
        )

        report["script_urls"].append(
            {
                "url": script_url,
                "status_code": (
                    response.status_code
                ),
                "size_bytes": len(
                    response.content
                ),
                "saved_to": str(
                    script_path
                ),
            }
        )

        endpoints = extract_possible_endpoints(
            script_text
        )

        for endpoint in endpoints:
            if (
                endpoint
                not in report[
                    "possible_endpoints"
                ]
            ):
                report[
                    "possible_endpoints"
                ].append(
                    endpoint
                )

    report_path = (
        OUTPUT_DIR
        / "probe_report.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    endpoint_path = (
        OUTPUT_DIR
        / "possible_endpoints.txt"
    )

    endpoint_path.write_text(
        "\n".join(
            report["possible_endpoints"]
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("[BOLOGNA PROBE COMPLETE]")
    print("=" * 72)

    print(
        "成功取得頁面：",
        len(report["pages"]),
    )

    print(
        "成功取得 JS：",
        len(report["script_urls"]),
    )

    print(
        "可能端點數：",
        len(
            report[
                "possible_endpoints"
            ]
        ),
    )

    print(
        "報告：",
        report_path,
    )

    print(
        "端點清單：",
        endpoint_path,
    )

    print()
    print("[前 30 個可能端點]")

    for endpoint in (
        report["possible_endpoints"][:30]
    ):
        print("-", endpoint)


if __name__ == "__main__":
    main()