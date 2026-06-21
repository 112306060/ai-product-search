from urllib.parse import urlparse


COMMON_SECOND_LEVEL_DOMAINS = {
    "co.uk",
    "com.au",
    "co.nz",
    "com.tw",
    "com.cn",
    "co.jp",
}


def normalize_domain(url: str) -> str:
    """
    將網址轉成標準網域。

    例如：
    https://www.brand.com/products/shampoo
    -> brand.com
    """
    if not isinstance(url, str):
        return ""

    cleaned_url = url.strip().lower()

    if not cleaned_url:
        return ""

    if not cleaned_url.startswith(("http://", "https://")):
        cleaned_url = f"https://{cleaned_url}"

    try:
        parsed = urlparse(cleaned_url)
        domain = parsed.netloc.lower().split(":")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except ValueError:
        return ""


def get_main_domain(url: str) -> str:
    """
    取得主網域，忽略地區子網域。

    例如：
    eu.brand.com -> brand.com
    shop.brand.co.uk -> brand.co.uk
    """
    domain = normalize_domain(url)

    if not domain:
        return ""

    parts = domain.split(".")

    if len(parts) <= 2:
        return domain

    last_two = ".".join(parts[-2:])

    if last_two in COMMON_SECOND_LEVEL_DOMAINS and len(parts) >= 3:
        return ".".join(parts[-3:])

    return ".".join(parts[-2:])


def dedupe_urls(urls_with_source: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    依主網域去除重複搜尋結果。

    同一品牌的不同頁面只保留第一筆。
    """
    seen_domains: set[str] = set()
    unique_urls: list[tuple[str, str]] = []

    for url, source in urls_with_source:
        domain = get_main_domain(url)

        if not domain:
            continue

        if domain in seen_domains:
            continue

        seen_domains.add(domain)
        unique_urls.append((url, source))

    return unique_urls