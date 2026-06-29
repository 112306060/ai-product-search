import os
import time
from urllib.parse import (
    urlparse,
    urlunparse,
)

import requests
from dotenv import load_dotenv
from requests.exceptions import (
    ConnectionError,
    HTTPError,
    RequestException,
    Timeout,
)


load_dotenv()


BLOCK_DOMAINS = [
    "reddit.com",
    "youtube.com",
    "youtu.be",
    "elle.com",
    "mordorintelligence.com",
    "amazon.",
    "alibaba.",
    "temu.",
    "shopee.",
    "momo.",
    "pchome.",
    "ebay.",
    "ecco-verde.com",
    "notino.",
    "lookfantastic.",
    "sephora.",
    "douglas.",
    "degroenedrogist.nl",
    "salonbrandsbeauty.com",
    "the-independent.com",
    "scandinaviastandard.com",
    "oldworlditalian.com",
    "tiktok.com",
    "hpra.ie",
]


BLOCK_PATH_KEYWORDS = [
    "/blog",
    "/blogs",
    "/news",
    "/article",
    "/articles",
    "/magazine",
    "/review",
    "/reviews",
    "/forum",
    "/watch",
]


SERPAPI_URL = (
    "https://serpapi.com/search.json"
)

SERPAPI_MAX_RETRIES = 3

SERPAPI_CONNECT_TIMEOUT = 15

SERPAPI_READ_TIMEOUT = 60


def search_web(
    query: str,
    exclude_domains: list[str],
    num_results: int = 10,
) -> list[str]:
    provider = os.getenv(
        "SEARCH_PROVIDER",
        "manual",
    ).strip().lower()

    print(
        "SEARCH_PROVIDER =",
        provider,
    )

    if provider == "serpapi":
        return _search_serpapi(
            query=query,
            exclude_domains=(
                exclude_domains
            ),
            num_results=num_results,
        )

    print(
        f"[search placeholder] {query}"
    )

    return []


def _search_serpapi(
    query: str,
    exclude_domains: list[str],
    num_results: int,
) -> list[str]:
    """
    執行 SerpAPI Google 搜尋。

    支援逾時重試。連續失敗時回傳空清單，
    避免單一 Google 搜尋中斷整個流程。
    """

    api_key = os.getenv(
        "SEARCH_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "Missing SEARCH_API_KEY"
        )

    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num_results,
    }

    for attempt in range(
        1,
        SERPAPI_MAX_RETRIES + 1,
    ):
        try:
            print(
                "[SERPAPI REQUEST]",
                f"第 {attempt}/"
                f"{SERPAPI_MAX_RETRIES} 次",
                query,
            )

            response = requests.get(
                SERPAPI_URL,
                params=params,
                timeout=(
                    SERPAPI_CONNECT_TIMEOUT,
                    SERPAPI_READ_TIMEOUT,
                ),
            )

            response.raise_for_status()

            data = response.json()

            if data.get("error"):
                print(
                    "[SERPAPI API ERROR]",
                    data.get("error"),
                )

                return []

            urls = []

            for item in data.get(
                "organic_results",
                [],
            ):
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                url = item.get("link")

                if not url:
                    continue

                cleaned_url = (
                    normalize_to_homepage(
                        url
                    )
                )

                if should_block_url(
                    cleaned_url,
                    exclude_domains,
                ):
                    continue

                urls.append(
                    cleaned_url
                )

            unique_urls = list(
                dict.fromkeys(urls)
            )

            print(
                "[SERPAPI SUCCESS]",
                query,
                f"取得 {len(unique_urls)} 筆",
            )

            return unique_urls

        except Timeout as error:
            print(
                "[SERPAPI TIMEOUT]",
                f"第 {attempt} 次失敗：",
                error,
            )

        except ConnectionError as error:
            print(
                "[SERPAPI CONNECTION ERROR]",
                f"第 {attempt} 次失敗：",
                error,
            )

        except HTTPError as error:
            status_code = (
                error.response.status_code
                if error.response
                is not None
                else ""
            )

            print(
                "[SERPAPI HTTP ERROR]",
                status_code,
                error,
            )

            # 401、403 通常是金鑰或權限問題，
            # 429 通常是額度或頻率限制；
            # 這些情況繼續重試通常沒有幫助。
            if status_code in {
                400,
                401,
                403,
                429,
            }:
                return []

        except ValueError as error:
            print(
                "[SERPAPI JSON ERROR]",
                error,
            )

            return []

        except RequestException as error:
            print(
                "[SERPAPI REQUEST ERROR]",
                f"第 {attempt} 次失敗：",
                error,
            )

        if (
            attempt
            < SERPAPI_MAX_RETRIES
        ):
            wait_seconds = (
                attempt * 2
            )

            print(
                "[SERPAPI RETRY]",
                f"{wait_seconds} 秒後重試",
            )

            time.sleep(
                wait_seconds
            )

    print(
        "[SERPAPI SKIPPED]",
        f"連續 {SERPAPI_MAX_RETRIES} "
        "次失敗，略過此關鍵字：",
        query,
    )

    return []


def normalize_to_homepage(
    url: str,
) -> str:
    parsed = urlparse(url)

    if (
        not parsed.scheme
        or not parsed.netloc
    ):
        return url

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            "",
            "",
            "",
            "",
        )
    )


def should_block_url(
    url: str,
    exclude_domains: list[str],
) -> bool:
    lower_url = str(
        url or ""
    ).lower()

    parsed = urlparse(
        lower_url
    )

    domain = (
        parsed.netloc
        .replace("www.", "")
    )

    all_block_domains = (
        BLOCK_DOMAINS
        + list(
            exclude_domains or []
        )
    )

    for blocked in all_block_domains:
        blocked_text = str(
            blocked or ""
        ).lower()

        if not blocked_text:
            continue

        if (
            blocked_text in domain
            or blocked_text in lower_url
        ):
            return True

    for path_word in (
        BLOCK_PATH_KEYWORDS
    ):
        if path_word in lower_url:
            return True

    return False