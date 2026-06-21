from config import DEFAULT_CONFIG
from modules.keyword_generator import generate_keywords
from modules.search_engine import search_web
from modules.crawler import fetch_website_text
from modules.ai_analyzer import analyze_brand_page
from modules.excel_exporter import (
    export_vendor_records,
    load_recent_existing_domains,
)

from modules.url_utils import (
    dedupe_urls,
    get_main_domain,
)
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
    existing_domains=None,
    skip_existing_brands=True,
    force_refresh_brands=False,
):
    records = []
    existing_domains = existing_domains or set()
    skipped_existing_count = 0
    for url, source in urls_with_source:
        if len(records) >= max_count:
            break
        domain = get_main_domain(url)

        should_skip = (
            skip_existing_brands
            and not force_refresh_brands
            and domain
            and domain in existing_domains
        )

        if should_skip:
            skipped_existing_count += 1
            print(f"[SKIP EXISTING BRAND] {domain}")
            continue
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
    if skipped_existing_count:
        print(
            f"[EXISTING BRAND SKIPPED] "
            f"{skipped_existing_count} 個近期品牌"
        )    
    return records





def run():
    config = DEFAULT_CONFIG

    if config.test_mode:
        google_limit = 2
        exhibition_limit = 1
    else:
        google_limit = config.target_count
        exhibition_limit = 0

    keywords = generate_keywords(
        product=config.product,
        region=config.region,
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

    existing_domains = load_recent_existing_domains(
        output_path=config.output_path,
        refresh_days=config.brand_refresh_days,
    )

    print(
        f"[BRAND MASTER] "
        f"讀取到 {len(existing_domains)} 個近期已分析品牌"
    )

    records = []

    google_records = build_records(
        urls_with_source=google_urls,
        start_index=1,
        max_count=google_limit,
        check_taiwan=config.check_taiwan_distributor,
        force_refresh_taiwan=config.force_refresh_taiwan,
        taiwan_cache_days=config.taiwan_cache_days,
        existing_domains=existing_domains,
        skip_existing_brands=config.skip_existing_brands,
        force_refresh_brands=config.force_refresh_brands,
    )
    records.extend(google_records)

    exhibition_records = build_records(
        urls_with_source=exhibition_urls,
        start_index=len(records) + 1,
        max_count=exhibition_limit,
        check_taiwan=config.check_taiwan_distributor,
        force_refresh_taiwan=config.force_refresh_taiwan,
        taiwan_cache_days=config.taiwan_cache_days,
        existing_domains=existing_domains,
        skip_existing_brands=config.skip_existing_brands,
        force_refresh_brands=config.force_refresh_brands,
    )
    records.extend(exhibition_records)

    export_summary = export_vendor_records(
    records=records,
    output_path=config.output_path,
    incremental=True,
    )

    print(f"Done. Exported records to {config.output_path}")
    print(f"本次找到：{export_summary['本次找到']}")
    print(f"新增品牌：{export_summary['新增品牌']}")
    print(f"更新品牌：{export_summary['更新品牌']}")
    print(f"品牌總數：{export_summary['資料庫總數']}")
    print(f"Google Search records: {len(google_records)}")
    print(f"Exhibition records: {len(exhibition_records)}")


if __name__ == "__main__":
    run()