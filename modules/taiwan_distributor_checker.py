import json
import os
from typing import Any

import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SERPAPI_URL = "https://serpapi.com/search.json"

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def build_taiwan_queries(brand_name: str) -> list[str]:
    """
    產生台灣代理商相關搜尋字。

    第一版限制為三組搜尋，避免每個品牌消耗過多 SerpAPI 額度。
    """
    clean_name = brand_name.strip()

    return [
        f'"{clean_name}" 台灣 總代理 OR 官方代理',
        f'"{clean_name}" 台灣 經銷商 OR 進口商',
        f'"{clean_name}" Taiwan distributor OR Taiwan importer',
    ]


def search_taiwan_distributor(
    brand_name: str,
    results_per_query: int = 5,
) -> list[dict[str, str]]:
    """
    使用 SerpAPI 搜尋品牌在台灣的代理、進口與銷售資訊。

    回傳每筆搜尋結果的標題、摘要及原始網址。
    """
    api_key = os.getenv("SEARCH_API_KEY")

    if not api_key:
        raise RuntimeError("Missing SEARCH_API_KEY")

    collected_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for query in build_taiwan_queries(brand_name):
        params = {
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "num": results_per_query,
            "hl": "zh-tw",
            "gl": "tw",
        }

        try:
            response = requests.get(
                SERPAPI_URL,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as exc:
            print(f"[Taiwan checker search failed] {brand_name}: {exc}")
            continue

        for item in data.get("organic_results", []):
            url = item.get("link", "").strip()

            if not url or url in seen_urls:
                continue

            seen_urls.add(url)

            collected_results.append(
                {
                    "query": query,
                    "title": item.get("title", "").strip(),
                    "snippet": item.get("snippet", "").strip(),
                    "url": url,
                }
            )

    return collected_results


def format_search_evidence(
    search_results: list[dict[str, str]],
    max_results: int = 12,
) -> str:
    """
    將搜尋結果整理成提供給 AI 判斷的文字。
    """
    evidence_blocks = []

    for index, item in enumerate(search_results[:max_results], start=1):
        evidence_blocks.append(
            "\n".join(
                [
                    f"Result {index}",
                    f"Title: {item.get('title', '')}",
                    f"Snippet: {item.get('snippet', '')}",
                    f"URL: {item.get('url', '')}",
                ]
            )
        )

    return "\n\n".join(evidence_blocks)


def default_checker_result() -> dict[str, Any]:
    return {
        "台灣代理狀態": "無法判斷",
        "台灣代理商名稱": "",
        "台灣代理證據": "",
        "台灣代理來源": "",
        "台灣檢查信心分數": 0,
    }


def analyze_taiwan_distributor(
    brand_name: str,
    official_url: str,
    search_results: list[dict[str, str]],
) -> dict[str, Any]:
    """
    使用 AI 判斷搜尋結果是否能證明品牌在台灣已有正式代理商。
    """
    if not search_results:
        return {
            "台灣代理狀態": "未找到代理證據",
            "台灣代理商名稱": "",
            "台灣代理證據": "Google 搜尋未找到足夠的台灣代理或進口資訊。",
            "台灣代理來源": "",
            "台灣檢查信心分數": 70,
        }

    evidence_text = format_search_evidence(search_results)

    prompt = f"""
You are checking whether an overseas beauty or hair care brand already has
an official distributor, importer, subsidiary, or agent in Taiwan.

Brand name:
{brand_name}

Official brand website:
{official_url}

Google Taiwan search results:
{evidence_text}

Important rules:

1. A Taiwan shopping website selling the product does NOT automatically mean
   there is an official distributor.
2. Shopee, MOMO, PChome, marketplaces, parallel imports, purchasing agents,
   and individual sellers should normally be classified as retail only.
3. Strong official distributor evidence includes:
   - 台灣總代理
   - 官方代理
   - 獨家代理
   - authorized distributor
   - official importer
   - the brand's official website naming a Taiwan distributor
   - a Taiwan company clearly identifying itself as the brand's official agent
4. A company merely saying it sells, imports, or carries the product is weaker
   evidence and may only qualify as suspected distribution.
5. Do not invent a distributor name.
6. The status must be exactly one of:
   - 已有官方代理
   - 疑似已有代理
   - 僅有零售販售
   - 未找到代理證據
   - 無法判斷
7. If the only evidence comes from Instagram, Facebook, TikTok,
   Threads, or other social media, the status must not be
   "已有官方代理". Use "疑似已有代理" at most.

8. If the status is "未找到代理證據", source_url must be an empty string.
   Do not use the official brand homepage as proof that no distributor exists.
Return ONLY valid JSON:

{{
  "status": "已有官方代理",
  "distributor_name": "代理商公司名稱",
  "evidence": "簡短說明判斷依據",
  "source_url": "最重要的證據網址",
  "confidence_score": 90
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You verify Taiwan distributor evidence. "
                        "Be conservative and return only valid JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
        )

        content = response.choices[0].message.content.strip()
        result = json.loads(content)

    except Exception as exc:
        print(f"[Taiwan checker AI failed] {brand_name}: {exc}")
        return default_checker_result()

    allowed_statuses = {
        "已有官方代理",
        "疑似已有代理",
        "僅有零售販售",
        "未找到代理證據",
        "無法判斷",
    }

    status = result.get("status", "無法判斷")

    if status not in allowed_statuses:
        status = "無法判斷"

    try:
        confidence_score = int(result.get("confidence_score", 0))
        confidence_score = max(0, min(confidence_score, 100))
    except (TypeError, ValueError):
        confidence_score = 0
    source_url = result.get("source_url", "").strip()
    source_url_lower = source_url.lower()

    social_domains = [
        "instagram.com",
        "facebook.com",
        "threads.net",
        "tiktok.com",
    ]

    if (
        status == "已有官方代理"
        and any(domain in source_url_lower for domain in social_domains)
    ):
        status = "疑似已有代理"
        confidence_score = min(confidence_score, 80)

    if status == "未找到代理證據":
        source_url = ""
    return {
    "台灣代理狀態": status,
    "台灣代理商名稱": result.get("distributor_name", ""),
    "台灣代理證據": result.get("evidence", ""),
    "台灣代理來源": source_url,
    "台灣檢查信心分數": confidence_score,
    }


def check_taiwan_distributor(
    brand_name: str,
    official_url: str = "",
) -> dict[str, Any]:
    """
    Taiwan Distributor Checker 的主要入口。

    搜尋台灣相關資料，並交由 AI 判斷。
    """
    print(f"[Taiwan Distributor Checker] {brand_name}")

    search_results = search_taiwan_distributor(
        brand_name=brand_name,
        results_per_query=5,
    )

    result = analyze_taiwan_distributor(
        brand_name=brand_name,
        official_url=official_url,
        search_results=search_results,
    )

    print(
        f"[Taiwan Checker Result] "
        f"{brand_name}: {result.get('台灣代理狀態')}"
    )

    return result