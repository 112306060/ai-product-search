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


def get_brand_key(url: str) -> str:
    """
    取得品牌識別用的核心名稱，忽略頂級網域（TLD），
    讓同一品牌的不同國別網站被視為同一家公司。

    例如：
    paulmitchell.com -> paulmitchell
    paulmitchell.it -> paulmitchell
    paulmitchell.de -> paulmitchell

    這是因為很多歐洲品牌會用不同國別網域經營同一品牌
    （brand.de / brand.fr / brand.com），只看主網域
    （含 TLD）會把它們誤判成不同公司。
    """
    main_domain = get_main_domain(url)

    if not main_domain:
        return ""

    parts = main_domain.split(".")

    if len(parts) <= 1:
        return main_domain

    last_two = ".".join(parts[-2:])

    if (
        last_two in COMMON_SECOND_LEVEL_DOMAINS
        and len(parts) >= 3
    ):
        return parts[-3]

    return parts[-2]


def dedupe_urls(urls_with_source: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    依品牌識別鍵去除重複搜尋結果（忽略頂級網域差異）。

    同一品牌的不同頁面、不同國別網域只保留第一筆。
    """
    seen_brands: set[str] = set()
    unique_urls: list[tuple[str, str]] = []

    for url, source in urls_with_source:
        brand_key = get_brand_key(url)

        if not brand_key:
            continue

        if brand_key in seen_brands:
            continue

        seen_brands.add(brand_key)
        unique_urls.append((url, source))

    return unique_urls