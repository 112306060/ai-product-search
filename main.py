from config import DEFAULT_CONFIG
from modules.keyword_generator import generate_keywords
from modules.search_engine import search_web
from modules.crawler import fetch_website_text
from modules.ai_analyzer import analyze_brand_page
from modules.excel_exporter import export_vendor_records
from modules.exhibition_search import search_exhibition_sources
from modules.website_classifier import classify_website


def build_records(urls_with_source, start_index, max_count):
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

    google_limit = 10
    exhibition_limit = 10

    keywords = generate_keywords(
        product="有機天然洗髮精",
        region="歐盟",
        languages=config.languages,
    )

    google_urls = []
    for keyword in keywords:
        results = search_web(keyword, exclude_domains=config.exclude_domains)
        for url in results:
            google_urls.append((url, "Google Search"))

    exhibition_results = search_exhibition_sources(
        exclude_domains=config.exclude_domains,
        num_results=5,
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
    )
    records.extend(google_records)

    exhibition_records = build_records(
        urls_with_source=exhibition_urls,
        start_index=len(records) + 1,
        max_count=exhibition_limit,
    )
    records.extend(exhibition_records)

    export_vendor_records(records, config.output_path)

    print(f"Done. Exported {len(records)} records to {config.output_path}")
    print(f"Google Search records: {len(google_records)}")
    print(f"Exhibition records: {len(exhibition_records)}")


if __name__ == "__main__":
    run()