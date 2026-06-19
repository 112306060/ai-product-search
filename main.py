from config import DEFAULT_CONFIG
from modules.keyword_generator import generate_keywords
from modules.search_engine import search_web
from modules.crawler import fetch_website_text
from modules.ai_analyzer import analyze_brand_page
from modules.excel_exporter import export_vendor_records
from modules.exhibition_search import search_exhibition_sources
from modules.website_classifier import classify_website
from modules.taiwan_distributor_checker import check_taiwan_distributor

def build_records(
    urls_with_source,
    start_index,
    max_count,
    check_taiwan=True,
    force_refresh_taiwan=False,
    taiwan_cache_days=7,
):
    records = []

    for url, source in urls_with_source:
        if len(records) >= max_count:
            break

        page_text = fetch_website_text(url)
        if not page_text:
            continue

        classification = classify_website(url, page_text)
        print(url, classification)

        if not classification.get("is_candidate"):
            continue

        record = analyze_brand_page(
            url=url,
            page_text=page_text,
            index=start_index + len(records),
            source=source,
        )

        if classification.get("country"):
            record["國家"] = classification.get("country")

        record["AI分類"] = classification.get("site_type", "")
        record["代理推薦分數"] = classification.get("agency_fit_score", "")
        record["AI判斷原因"] = classification.get("reason", "")
        record["是否適合代理"] = "是" if classification.get("is_candidate") else "否"

        if check_taiwan:
            taiwan_result = check_taiwan_distributor(
                brand_name=record.get("公司名稱", ""),
                official_url=url,
                force_refresh=force_refresh_taiwan,
                cache_expire_days=taiwan_cache_days,
            )
            

            record.update(taiwan_result)
        else:
            record.update(
                {
                    "台灣代理狀態": "未執行",
                    "台灣代理商名稱": "",
                    "台灣代理證據": "",
                    "台灣代理來源": "",
                    "台灣檢查信心分數": "",
                }
            )

        records.append(record)

    return records


def dedupe_urls(urls_with_source):
    seen = set()
    unique = []

    for url, source in urls_with_source:
        if url in seen:
            continue
        seen.add(url)
        unique.append((url, source))

    return unique


def run():
    config = DEFAULT_CONFIG

    if config.test_mode:
        google_limit = 2
        exhibition_limit = 1
    else:
        google_limit = 10
        exhibition_limit = 10

    keywords = generate_keywords(
        product="有機天然洗髮精",
        region="歐盟",
        languages=config.languages,
        
    )
    if config.test_mode:
            keywords = keywords[:2]
            print("[TEST MODE] 只執行前 2 組一般搜尋關鍵字")

    google_urls = []
    for keyword in keywords:
        results = search_web(keyword, exclude_domains=config.exclude_domains)
        for url in results:
            google_urls.append((url, "Google Search"))

    exhibition_results = search_exhibition_sources(
        exclude_domains=config.exclude_domains,
        num_results=3 if config.test_mode else 5,
        test_mode=config.test_mode,
    )
    exhibition_urls = [
        (url, "Exhibition / Cosmoprof")
        for url in exhibition_results
    ]

    google_urls = dedupe_urls(google_urls)
    exhibition_urls = dedupe_urls(exhibition_urls)

    records = []

    google_records = build_records(
        urls_with_source=google_urls,
        start_index=1,
        max_count=google_limit,
        check_taiwan=config.check_taiwan_distributor,
        force_refresh_taiwan=config.force_refresh_taiwan,
        taiwan_cache_days=config.taiwan_cache_days,
    )
    records.extend(google_records)

    exhibition_records = build_records(
        urls_with_source=exhibition_urls,
        start_index=len(records) + 1,
        max_count=exhibition_limit,
        check_taiwan=config.check_taiwan_distributor,
        force_refresh_taiwan=config.force_refresh_taiwan,
        taiwan_cache_days=config.taiwan_cache_days,
    )
    records.extend(exhibition_records)

    export_vendor_records(records, config.output_path)

    print(f"Done. Exported {len(records)} records to {config.output_path}")
    print(f"Google Search records: {len(google_records)}")
    print(f"Exhibition records: {len(exhibition_records)}")


if __name__ == "__main__":
    run()