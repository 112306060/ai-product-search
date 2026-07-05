import re

from modules.cache_manager import load_cache, save_cache
from modules.search_engine import search_web
from modules.url_utils import get_main_domain


CACHE_TYPE = "bologna_official_website"

# Bologna 官方目錄本身沒有公開展商官網，
# 只能透過公司名稱查詢，查詢結果長期有效，
# 快取天數設長一點以減少重複查詢。
CACHE_EXPIRE_DAYS = 180


# 這些不是展商自己的品牌官網，
# 而是展覽平台、社群媒體或 B2B 名錄／徵信網站。
EXTRA_EXCLUDE_DOMAINS = [
    "cosmoprof.com",
    "cosmoprofawards.com",
    "cosmoprofworldwidebologna.com",
    "bolognafiere.it",
    "cosmeticaitalia.it",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "pinterest.com",
    "wikipedia.org",
    "crunchbase.com",
    "kompass.com",
    "europages.",
    "dnb.com",
    "glassdoor.com",
    "indeed.com",
    "opencorporates.com",
    "bloomberg.com",
    "zoominfo.com",
    "rocketreach.co",
    "yellowpages.",
    "manta.com",
    "cylex-",
    "exhibitorsdata.com",
    "bizprospex.com",
    "tradekey.com",
    "made-in-china.com",
    "globalsources.com",
]


GENERIC_COMPANY_WORDS = {
    "spa",
    "srl",
    "sl",
    "sa",
    "inc",
    "ltd",
    "llc",
    "gmbh",
    "co",
    "corp",
    "corporation",
    "company",
    "group",
    "since",
    "cosmetics",
    "cosmetic",
    "professional",
    "international",
    "labs",
    "laboratories",
    "the",
    "and",
    "of",
    "for",
    "b",
}


def build_query(company_name: str) -> str:
    cleaned = str(company_name or "").strip()

    return f'"{cleaned}" official website'


def normalize_name_tokens(
    company_name: str,
) -> set[str]:
    cleaned = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(company_name or "").lower(),
    )

    return {
        token
        for token in cleaned.split()
        if len(token) >= 4
        and token not in GENERIC_COMPANY_WORDS
    }


def domain_matches_company_name(
    url: str,
    company_name: str,
) -> bool:
    """
    避免搜尋抓到跟公司名稱完全無關的網站
    （例如公司名稱裡剛好包含 "B Corp" 之類的
    認證字樣，結果搜到認證機構官網）。

    只有在網域主要部分跟公司名稱有明顯字詞重疊時，
    才視為可信的官網候選。
    """

    domain = get_main_domain(url)

    if not domain:
        return False

    domain_core = domain.split(".")[0]

    name_tokens = normalize_name_tokens(
        company_name
    )

    if not name_tokens:
        return True

    return any(
        token in domain_core
        or domain_core in token
        for token in name_tokens
    )


def find_official_website(
    company_name: str,
) -> str:
    """
    用公司名稱搜尋 Google，取第一個非展覽平台／
    非社群媒體／非 B2B 名錄，且網域與公司名稱
    有字詞關聯的結果，當作候選官網。
    """

    query = build_query(company_name)

    results = search_web(
        query=query,
        exclude_domains=EXTRA_EXCLUDE_DOMAINS,
        num_results=5,
    )

    for url in results:
        if url and domain_matches_company_name(
            url,
            company_name,
        ):
            return url

    return ""


def resolve_official_website(
    company_name: str,
    force_refresh: bool = False,
    cache_expire_days: int = CACHE_EXPIRE_DAYS,
) -> str:
    """
    Bologna 展商官網查詢的主要入口。

    先讀取未過期快取；沒有快取、快取過期，
    或 force_refresh=True 時才重新搜尋。
    找不到官網時也會快取「未找到」結果，
    避免同一家公司每次都重新查詢。
    """

    cache_key = str(company_name or "").strip()

    if not cache_key:
        return ""

    if not force_refresh:
        cached = load_cache(
            cache_type=CACHE_TYPE,
            cache_key=cache_key,
            expire_days=cache_expire_days,
        )

        if cached is not None:
            return str(
                cached.get("official_website", "")
                or ""
            )

    print(
        f"[Bologna Website Lookup] {cache_key}"
    )

    website = find_official_website(cache_key)

    save_cache(
        cache_type=CACHE_TYPE,
        cache_key=cache_key,
        data={
            "official_website": website,
            "found": bool(website),
        },
    )

    print(
        f"[Bologna Website Result] {cache_key}: "
        f"{website or '(not found)'}"
    )

    return website


if __name__ == "__main__":
    test_names = [
        "4MASS S.A.",
        "abyssian",
        "ALAMA PROFESSIONAL // Pettenon Cosmetics SpA",
        "ALOE COLORS",
        "ANTICA ERBORISTERIA SPA SB I B Corp since 2016",
    ]

    for name in test_names:
        website = resolve_official_website(name)

        print("-" * 60)
        print("公司：", name)
        print("官網：", website or "(not found)")
