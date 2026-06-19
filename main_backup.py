from config import DEFAULT_CONFIG
from modules.keyword_generator import generate_keywords
from modules.search_engine import search_web
from modules.crawler import fetch_website_text
from modules.ai_analyzer import analyze_brand_page
from modules.excel_exporter import export_vendor_records

def run():
    config = DEFAULT_CONFIG

    keywords = generate_keywords(
        product="有機天然洗髮精",
        region="歐盟",
        languages=config.languages,
    )

    urls = []
    for keyword in keywords:
        results = search_web(keyword, exclude_domains=config.exclude_domains)
        urls.extend(results)

    # 去重，保留順序
    urls = list(dict.fromkeys(urls))

    records = []
    for idx, url in enumerate(urls, start=1):
        if len(records) >= config.target_count:
            break

        page_text = fetch_website_text(url)
        if not page_text:
            continue

        record = analyze_brand_page(
            url=url,
            page_text=page_text,
            index=len(records) + 1,
        )

        if record:
            records.append(record)

    export_vendor_records(records, config.output_path)
    print(f"Done. Exported {len(records)} records to {config.output_path}")

if __name__ == "__main__":
    run()
