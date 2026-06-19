import os
from urllib.parse import urlparse, urlunparse

import requests
from dotenv import load_dotenv

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


def search_web(query: str, exclude_domains: list[str], num_results: int = 10) -> list[str]:
    provider = os.getenv("SEARCH_PROVIDER", "manual")
    print("SEARCH_PROVIDER =", provider)

    if provider == "serpapi":
        return _search_serpapi(query, exclude_domains, num_results)

    print(f"[search placeholder] {query}")
    return []


def _search_serpapi(query: str, exclude_domains: list[str], num_results: int) -> list[str]:
    api_key = os.getenv("SEARCH_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SEARCH_API_KEY")

    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num_results,
    }

    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    urls = []
    for item in data.get("organic_results", []):
        url = item.get("link")
        if not url:
            continue

        cleaned_url = normalize_to_homepage(url)

        if should_block_url(cleaned_url, exclude_domains):
            continue

        urls.append(cleaned_url)

    return list(dict.fromkeys(urls))


def normalize_to_homepage(url: str) -> str:
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return url

    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def should_block_url(url: str, exclude_domains: list[str]) -> bool:
    lower_url = url.lower()
    parsed = urlparse(lower_url)
    domain = parsed.netloc.replace("www.", "")

    all_block_domains = BLOCK_DOMAINS + exclude_domains

    for blocked in all_block_domains:
        if blocked in domain or blocked in lower_url:
            return True

    for path_word in BLOCK_PATH_KEYWORDS:
        if path_word in lower_url:
            return True

    return False