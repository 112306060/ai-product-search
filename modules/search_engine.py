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
    # 用「結尾有點」的寫法（而非固定 .com），
    # 才能同時擋掉同一個零售商的不同國別網域
    # （例如 ecco-verde.ch / ecco-verde.it），
    # 跟下面 notino. / lookfantastic. 等寫法一致。
    "ecco-verde.",
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
    # 以下為歐洲各語言市場常見的美妝零售/藥妝連鎖，
    # 之前只涵蓋英語系（Sephora/Notino/Lookfantastic/
    # Douglas），非英文搜尋結果容易混入這些雜訊。
    "dm-drogeriemarkt.",  # 德國/奧地利/義大利藥妝連鎖
    "rossmann.",  # 德國/中東歐大型藥妝連鎖
    "flaconi.",  # 德國線上美妝零售
    "nocibe.",  # 法國香水/美妝連鎖
    "marionnaud.",  # 法國/歐洲多國香水專賣連鎖
    "primor.",  # 西班牙/歐洲美妝零售連鎖
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
    start: int = 0,
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
            start=start,
        )

    print(
        f"[search placeholder] {query}"
    )

    return []


def _search_serpapi(
    query: str,
    exclude_domains: list[str],
    num_results: int,
    start: int = 0,
) -> list[str]:
    """
    執行 SerpAPI Google 搜尋。

    start 用來翻頁（例如 start=10 拿第2頁、
    start=20 拿第3頁），讓同一組關鍵字能挖得更深，
    不會每次都只看第1頁。

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

    if start:
        params["start"] = start

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
                    normalize_search_result_url(
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


def normalize_search_result_url(
    url: str,
) -> str:
    """
    清理 Google 搜尋結果網址，只去掉查詢字串／片段
    （通常是追蹤參數，例如 ?utm_source=...），
    保留路徑本身。

    Google 排到前面，通常是因為某個深層頁面
    （例如 brand.com/products/organic-shampoo）
    內容真的符合搜尋字，而不是首頁。之前會把網址
    直接壓成首頁，導致後續爬蟲抓到的是首頁的品牌
    形象文案，不是 Google 當初判斷相關的那個頁面，
    可能讓 AI 誤判拒絕本來該通過的候選。
    """

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
            parsed.path,
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