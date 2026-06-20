import re
from urllib.parse import urlparse


INVALID_BRAND_NAMES = {
    "www",
    "eu",
    "uk",
    "us",
    "en",
    "de",
    "fr",
    "it",
    "es",
    "nl",
    "shop",
    "store",
    "official",
    "global",
    "international",
    "home",
    "website",
}


SPECIAL_BRAND_NAMES = {
    "vieloe": "Vielö",
    "lapurative": "La Purative",
    "unique-beauty": "Unique Beauty",
    "unique beauty": "Unique Beauty",
    "greenpeople": "Green People",
    "greenpeople.co": "Green People",
    "evolvebeauty": "Evolve Beauty",
    "harklinikken": "Hårklinikken",
    "muehle-shaving": "MÜHLE",
    "muehle shaving": "MÜHLE",
    "100percentpure": "100% PURE",
    "paulmitchell": "Paul Mitchell",
    "screenhaircare": "Screen Hair Care",
    "oserth": "Oserth",
}


COMMON_SECOND_LEVEL_DOMAINS = {
    "co.uk",
    "com.au",
    "co.nz",
    "com.tw",
    "com.cn",
    "co.jp",
}


def clean_brand_name(name: str) -> str:
    if not isinstance(name, str):
        return ""

    cleaned = re.sub(r"\s+", " ", name).strip()
    return cleaned


def is_suspicious_brand_name(name: str) -> bool:
    cleaned = clean_brand_name(name)
    normalized = cleaned.lower()

    if not cleaned:
        return True

    if normalized in INVALID_BRAND_NAMES:
        return True

    if len(cleaned) <= 2:
        return True

    if cleaned.isdigit():
        return True

    return False


def get_main_domain_part(url: str) -> str:
    """
    取得主要網域名稱。

    eu.oserth.com -> oserth
    www.greenpeople.co.uk -> greenpeople
    """
    parsed = urlparse(url)
    hostname = parsed.netloc.lower()

    if not hostname:
        hostname = parsed.path.lower()

    hostname = hostname.split(":")[0]

    if hostname.startswith("www."):
        hostname = hostname[4:]

    parts = [
        part
        for part in hostname.split(".")
        if part
    ]

    if not parts:
        return ""

    last_two = ".".join(parts[-2:])

    if last_two in COMMON_SECOND_LEVEL_DOMAINS and len(parts) >= 3:
        return parts[-3]

    if len(parts) >= 2:
        return parts[-2]

    return parts[0]


def format_domain_brand(domain_part: str) -> str:
    normalized = domain_part.lower().strip()

    if normalized in SPECIAL_BRAND_NAMES:
        return SPECIAL_BRAND_NAMES[normalized]

    readable = normalized.replace("-", " ").replace("_", " ")
    readable = " ".join(
        word.capitalize()
        for word in readable.split()
    )

    return readable


def validate_brand_name(
    proposed_name: str,
    url: str,
) -> str:
    """
    驗證程式產生的品牌名稱。

    名稱合理時保留；
    名稱可疑時改用主要網域名稱。
    """
    cleaned_name = clean_brand_name(proposed_name)
    normalized_name = cleaned_name.lower()

    if normalized_name in SPECIAL_BRAND_NAMES:
        return SPECIAL_BRAND_NAMES[normalized_name]

    if not is_suspicious_brand_name(cleaned_name):
        return cleaned_name

    domain_part = get_main_domain_part(url)

    return format_domain_brand(domain_part)