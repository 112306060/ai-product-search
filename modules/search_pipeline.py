from modules.ai_analyzer import analyze_brand_page
from modules.crawler import fetch_website_text
from modules.excel_exporter import (
    export_vendor_records,
    load_recent_existing_domains,
)
from modules.exhibition_search import (
    search_exhibition_sources,
)
from modules.keyword_generator import generate_keywords
from modules.search_engine import search_web
from modules.taiwan_distributor_checker import (
    check_taiwan_distributor,
)
from modules.url_utils import (
    dedupe_urls,
    get_main_domain,
)
from modules.website_classifier import classify_website
from modules.candidate_filter import filter_candidates
from modules.exhibitions.cosmoprof_asia import (
    get_all_exhibitors,
)
from modules.exhibitions.cpna_dynamic_search import (
    search_cpna_candidates,
)
from datetime import datetime
EMPTY_TAIWAN_RESULT = {
    "台灣代理狀態": "未執行",
    "台灣代理商名稱": "",
    "台灣代理證據": "",
    "台灣代理來源": "",
    "台灣檢查信心分數": "",
}


def build_exhibition_fallback_record(
    url,
    source,
    source_metadata,
    index,
    search_profile,
):
    """
    當展覽候選公司的官網無法讀取時，
    仍使用官方展覽名錄建立待人工確認紀錄。
    """

    company_name = source_metadata.get(
        "展覽公司名稱",
        "",
    )

    country = source_metadata.get(
        "展覽國家",
        "",
    )

    exhibition_category = source_metadata.get(
        "展覽商品分類",
        "",
    )

    product_categories = []

    for keyword in search_profile.product_keywords:
        cleaned = str(keyword).strip()

        if not cleaned:
            continue

        display = " ".join(
            word.capitalize()
            for word in cleaned.split()
        )

        if display not in product_categories:
            product_categories.append(display)

    product_category = " / ".join(
        product_categories
    )

    if not product_category:
        product_category = (
            search_profile.query.strip()
            or "待人工確認"
        )

    return {
        "記錄日期": datetime.now().strftime(
            "%Y%m%d"
        ),
        "編號": index,
        "公司名稱": company_name,
        "網站": url,
        "國家": country,
        "資料來源": source,
        "展覽名稱": source_metadata.get(
            "展覽名稱",
            "",
        ),
        "展覽年份": source_metadata.get(
            "展覽年份",
            "",
        ),
        "展覽攤位": source_metadata.get(
            "展覽攤位",
            "",
        ),
        "展覽公司名稱": company_name,
        "展覽商品分類": exhibition_category,
        "展覽參展類型": source_metadata.get(
            "展覽參展類型",
            "",
        ),
        "展覽來源頁面": source_metadata.get(
            "展覽來源頁面",
            "",
        ),
        "商品類別": product_category,
        "商品內容": (
            exhibition_category
            or "官方展覽名錄候選，待人工確認"
        ),
        "AI分類": "待人工確認",
        "是否適合代理": "待確認",
        "代理推薦分數": "",
        "AI判斷原因": (
            "官方展覽名錄符合初步搜尋條件，"
            "但官網無法讀取，因此尚未執行完整 AI 判斷。"
        ),
        "台灣代理狀態": "未執行",
        "台灣代理商名稱": "",
        "台灣代理證據": "",
        "台灣代理來源": "",
        "台灣檢查信心分數": "",
        "評論": (
            "已保留官方展覽資料；"
            "官網爬取失敗，待人工確認"
        ),
        "後續連絡情況": "",
        "連絡人資料": "",
        "來源連結": url,
    }




def build_records(
    urls_with_source,
    start_index,
    max_count,
    search_profile,
    check_taiwan=True,
    force_refresh_taiwan=False,
    taiwan_cache_days=7,
    existing_domains=None,
    skip_existing_brands=True,
    force_refresh_brands=False,
):
    """
    處理 Google 搜尋與展覽來源資料。

    支援兩種輸入：

    Google：
        (url, source)

    展覽：
        (url, source, source_metadata)
    """

    records = []

    existing_domains = (
        existing_domains or set()
    )

    skipped_existing_count = 0

    for source_item in urls_with_source:
        if len(records) >= max_count:
            break

        if len(source_item) == 3:
            (
                url,
                source,
                source_metadata,
            ) = source_item
        else:
            (
                url,
                source,
            ) = source_item

            source_metadata = {}

        domain = get_main_domain(url)

        should_skip = (
            skip_existing_brands
            and not force_refresh_brands
            and domain
            and domain in existing_domains
        )

        if should_skip:
            skipped_existing_count += 1

            print(
                f"[SKIP EXISTING BRAND] {domain}"
            )

            continue
        page_text = fetch_website_text(url)

        # 官網無法讀取時，優先使用官方展覽描述，
        # 並繼續交給 website_classifier 判斷。
        if not page_text:
            exhibition_description = str(
                source_metadata.get(
                    "展覽描述",
                    "",
                )
                or ""
            ).strip()

            if exhibition_description:
                company_name = str(
                    source_metadata.get(
                        "展覽公司名稱",
                        "",
                    )
                    or ""
                ).strip()

                exhibition_category = str(
                    source_metadata.get(
                        "展覽商品分類",
                        "",
                    )
                    or ""
                ).strip()

                print(
                    "[USE EXHIBITION DESCRIPTION] "
                    f"{company_name}"
                )

                page_text = (
                    "Official exhibition company description:\n"
                    f"{exhibition_description}\n\n"
                    "Official exhibition company name:\n"
                    f"{company_name}\n\n"
                    "Official exhibition category:\n"
                    f"{exhibition_category}"
                )

            elif source_metadata:
                print(
                    "[EXHIBITION SKIPPED - NO CONTENT] "
                    f"{source_metadata.get('展覽公司名稱', '')}"
                )

                continue

            else:
                continue

        classification = classify_website(
            url=url,
            page_text=page_text,
            search_profile=search_profile,
        )

        print(
            url,
            classification,
            )

        if not classification.get(
                 "is_candidate"
            ):
                    continue

        record = analyze_brand_page(
            url=url,
            page_text=page_text,
            index=start_index + len(records),
            search_profile=search_profile,
            source=source,
        )

        # 一般來源先使用 AI 判斷國家。
        ai_country = classification.get(
            "country",
            "",
        )

        if ai_country:
            record["國家"] = ai_country

        # 官方展覽資料優先於網域推測與 AI 判斷。
        if source_metadata:
            record.update(
                {
                    key: value
                    for key, value
                    in source_metadata.items()
                    if key != "展覽國家"
                }
            )

            official_company_name = (
                source_metadata.get(
                    "展覽公司名稱",
                    "",
                )
            )

            if official_company_name:
                record["公司名稱"] = (
                    official_company_name
                )

            official_country = (
                source_metadata.get(
                    "展覽國家",
                    "",
                )
            )

            if official_country:
                record["國家"] = (
                    official_country
                )

        record["AI分類"] = (
            classification.get(
                "site_type",
                "",
            )
        )

        record["代理推薦分數"] = (
            classification.get(
                "agency_fit_score",
                "",
            )
        )

        record["AI判斷原因"] = (
            classification.get(
                "reason",
                "",
            )
        )

        record["是否適合代理"] = (
            "是"
            if classification.get(
                "is_candidate"
            )
            else "否"
        )

        if check_taiwan:
            taiwan_result = (
                check_taiwan_distributor(
                    brand_name=record.get(
                        "公司名稱",
                        "",
                    ),
                    official_url=url,
                    force_refresh=(
                        force_refresh_taiwan
                    ),
                    cache_expire_days=(
                        taiwan_cache_days
                    ),
                )
            )

            record.update(taiwan_result)

        else:
            record.update(
                EMPTY_TAIWAN_RESULT
            )

        records.append(record)

    if skipped_existing_count:
        print(
            "[EXISTING BRAND SKIPPED] "
            f"{skipped_existing_count} "
            "個近期品牌"
        )

    return records




def collect_google_urls(
    config,
    search_profile,
):
    """
    依照使用者本次的 SearchProfile，
    動態產生 Google 搜尋關鍵字。

    不再直接使用：
    config.product
    config.region
    """

    keywords = generate_keywords(
        search_profile,
        languages=config.languages,
    )

    print(
        "[SEARCH PROFILE] "
        f"{search_profile.query}"
    )

    print(
        "[GENERATED KEYWORDS] "
        f"共 {len(keywords)} 組"
    )

    for keyword in keywords:
        print(f"  - {keyword}")

    if config.test_mode:
        keywords = keywords[:2]

        print(
            "[TEST MODE] "
            "只執行前 2 組一般搜尋關鍵字"
        )

    google_urls = []

    for keyword in keywords:
        results = search_web(
            keyword,
            exclude_domains=(
                config.exclude_domains
            ),
        )

        for url in results:
            google_urls.append(
                (
                    url,
                    "Google Search",
                )
            )

    return dedupe_urls(google_urls)


def collect_cosmoprof_asia_urls(
    search_profile,
    max_count,
):
    """
    從 Cosmoprof Asia 官方名錄取得參展商，
    依照 SearchProfile 篩選，並保留展覽資料。
    """

    if max_count <= 0:
        print(
            "[COSMOPROF ASIA DISABLED] "
            "本次未啟用官方展覽來源"
        )
        return []

    exhibitors = get_all_exhibitors()

    matched_exhibitors = filter_candidates(
        exhibitors,
        search_profile,
    )

    print(
        "[COSMOPROF ASIA FILTER] "
        f"{len(exhibitors)} 筆中符合 "
        f"{len(matched_exhibitors)} 筆"
    )

    source_items = []

    for exhibitor in matched_exhibitors:
        official_url = exhibitor.get(
            "official_url",
            "",
        )

        if not official_url:
            continue

        source = exhibitor.get(
            "source",
            "Cosmoprof Asia",
        )

        metadata = {
            "展覽名稱": exhibitor.get(
                "exhibition",
                "",
            ),
            "展覽年份": exhibitor.get(
                "exhibition_year",
                "",
            ),
            "展覽攤位": exhibitor.get(
                "booth",
                "",
            ),
            "展覽公司名稱": exhibitor.get(
                "company_name",
                "",
            ),
            "展覽商品分類": exhibitor.get(
                "product_category",
                "",
            ),
            "展覽參展類型": exhibitor.get(
                "exhibitor_type",
                "",
            ),
            "展覽來源頁面": exhibitor.get(
                "source_url",
                "",
            ),
            "展覽國家": exhibitor.get(
                "country",
                "",
            ),
        }

        source_items.append(
            (
                official_url,
                source,
                metadata,
            )
        )

        if len(source_items) >= max_count:
            break

    print(
        "[COSMOPROF ASIA URLS] "
        f"送入後續分析 {len(source_items)} 筆"
    )

    return source_items

def collect_cosmoprof_north_america_urls(
    search_profile,
    max_count,
):
    """
    根據本次 SearchProfile 動態匹配 CPNA 官方分類，
    再透過官方 API 取得最新展商。

    流程：
    1. 將搜尋需求匹配成最新 business_area ID。
    2. 即時查詢 CPNA 官方 API。
    3. 合併本地快取的官網、描述與國家。
    4. 送入既有網站爬取與分析流程。
    """
    if max_count <= 0:
        print(
            "[COSMOPROF NORTH AMERICA DISABLED] "
            "本次未啟用 North America 展覽來源"
        )
        return []

    query = str(
        search_profile.query
        or ""
    ).strip()

    if not query:
        query_parts = []

        query_parts.extend(
            str(keyword).strip()
            for keyword
            in search_profile.positioning_keywords
            if str(keyword).strip()
        )

        query_parts.extend(
            str(keyword).strip()
            for keyword
            in search_profile.product_keywords
            if str(keyword).strip()
        )

        query = " ".join(
            query_parts
        ).strip()

    if not query:
        print(
            "[CPNA DYNAMIC SEARCH SKIPPED] "
            "本次沒有可用的商品搜尋需求"
        )
        return []

    try:
        result = search_cpna_candidates(
            query=query,
            max_records=None,
        )

    except Exception as error:
        print(
            "[CPNA DYNAMIC SEARCH ERROR]",
            error,
        )
        return []

    if result.get("error"):
        print(
            "[CPNA DYNAMIC SEARCH ERROR]",
            result["error"],
        )
        return []

    business_area_ids = result.get(
        "business_area_ids",
        [],
    )

    candidates = result.get(
        "candidates",
        [],
    )

    print(
        "[CPNA DYNAMIC CATEGORIES] "
        f"{business_area_ids}"
    )

    print(
        "[CPNA DYNAMIC CANDIDATES] "
        f"官方候選共 {len(candidates)} 家"
    )

    positioning_names = [
        str(
            match.get("name")
            or ""
        ).strip()
        for match in result.get(
            "positioning_matches",
            [],
        )
        if str(
            match.get("name")
            or ""
        ).strip()
    ]

    source_items = []
    skipped_without_url = 0

    for exhibitor in candidates:
        official_url = str(
            exhibitor.get(
                "official_url",
                "",
            )
            or ""
        ).strip()

        if not official_url:
            skipped_without_url += 1
            continue

        source = str(
            exhibitor.get(
                "source",
                "",
            )
            or (
                "Cosmoprof North America "
                "Las Vegas 2026"
            )
        ).strip()

        official_category_names = []

        for category_id in (
            business_area_ids
        ):
            category_text = str(
                category_id
            )

            if (
                category_text
                not in official_category_names
            ):
                official_category_names.append(
                    category_text
                )

        exhibition_category = (
            str(
                exhibitor.get(
                    "product_category",
                    "",
                )
                or ""
            ).strip()
        )

        if not exhibition_category:
            exhibition_category = (
                "CPNA business_area IDs: "
                + ", ".join(
                    official_category_names
                )
            )

        metadata = {
            "展覽名稱": exhibitor.get(
                "exhibition",
                "",
            ),
            "展覽年份": exhibitor.get(
                "exhibition_year",
                "",
            ),
            "展覽攤位": exhibitor.get(
                "booth",
                "",
            ),
            "展覽公司名稱": exhibitor.get(
                "company_name",
                "",
            ),
            "展覽商品分類": (
                exhibition_category
            ),
            "展覽參展類型": exhibitor.get(
                "exhibitor_type",
                "",
            ),
            "展覽來源頁面": exhibitor.get(
                "source_url",
                "",
            ),
            "展覽國家": exhibitor.get(
                "country",
                "",
            ),
            "展覽描述": exhibitor.get(
                "description",
                "",
            ),
            "展覽官方網站": exhibitor.get(
                "official_url",
                "",
            ),
            "CPNA官方分類ID": (
                ", ".join(
                    str(category_id)
                    for category_id
                    in business_area_ids
                )
            ),
            "CPNA定位條件": (
                " / ".join(
                    positioning_names
                )
            ),
        }

        source_items.append(
            (
                official_url,
                source,
                metadata,
            )
        )

        if len(source_items) >= max_count:
            break

    print(
        "[COSMOPROF NORTH AMERICA URLS] "
        f"送入後續分析 {len(source_items)} 筆"
    )

    if skipped_without_url:
        print(
            "[CPNA WITHOUT OFFICIAL URL] "
            f"略過 {skipped_without_url} 家"
        )

    return source_items

def merge_exhibition_source_items(
    source_groups,
    max_count,
):
    """
    將不同展覽來源交錯合併並依網域去重。

    避免 Asia 排在前面時，
    在測試模式把全部名額用完，
    導致 North America 沒有進入後續分析。
    """

    if max_count <= 0:
        return []

    merged = []
    seen_domains = set()

    largest_group_size = max(
        (
            len(group)
            for group in source_groups
        ),
        default=0,
    )

    for index in range(
        largest_group_size
    ):
        for group in source_groups:
            if index >= len(group):
                continue

            source_item = group[index]

            if not source_item:
                continue

            url = source_item[0]
            domain = get_main_domain(url)

            dedupe_key = (
                domain
                or str(url).strip().lower()
            )

            if not dedupe_key:
                continue

            if dedupe_key in seen_domains:
                continue

            seen_domains.add(
                dedupe_key
            )

            merged.append(
                source_item
            )

            if len(merged) >= max_count:
                return merged

    return merged
def collect_exhibition_urls(
    config,
    exhibition_limit,
):
    """
    舊版展覽關鍵字搜尋。

    正式模式目前停用；
    後續會改成串接 Cosmoprof 官方名錄。
    """

    if exhibition_limit <= 0:
        print(
            "[EXHIBITION DISABLED] "
            "暫停舊展覽關鍵字搜尋"
        )

        return []

    exhibition_results = (
        search_exhibition_sources(
            exclude_domains=(
                config.exclude_domains
            ),
            num_results=(
                3
                if config.test_mode
                else 5
            ),
            test_mode=config.test_mode,
        )
    )

    exhibition_urls = [
        (
            url,
            "Exhibition / Keyword Search",
        )
        for url in exhibition_results
    ]

    return dedupe_urls(exhibition_urls)


def get_search_limits(config):
    """
    測試模式只處理少量結果，
    正式模式依 config.target_count 執行。
    """

    if config.test_mode:
        return 2, 2

    return config.target_count, config.target_count


def run_search_pipeline(
    config,
    search_profile,
):
    """
    執行完整搜尋流程。

    config：
        系統執行設定，例如輸出路徑、
        測試模式、API 快取設定。

    search_profile：
        使用者本次搜尋條件，例如商品、
        定位、國家與地區條件。
    """

    google_limit, exhibition_limit = (
        get_search_limits(config)
    )
    # 展覽來源需要先準備較大的候選池。
    # exhibition_limit 代表最後要留下的合格筆數，
    # 不是前期只准取多少候選網址。
    exhibition_candidate_limit = max(
        exhibition_limit * 10,
        20,
    )
    google_urls = collect_google_urls(
        config=config,
        search_profile=search_profile,
    )

    asia_exhibition_urls = (
        collect_cosmoprof_asia_urls(
            search_profile=search_profile,
            max_count=(
                exhibition_candidate_limit
            ),
        )
    )

    north_america_exhibition_urls = (
        collect_cosmoprof_north_america_urls(
            search_profile=search_profile,
            max_count=(
                exhibition_candidate_limit
            ),
        )
    )

    exhibition_urls = (
        merge_exhibition_source_items(
            source_groups=[
                asia_exhibition_urls,
                north_america_exhibition_urls,
            ],
            max_count=(
                exhibition_candidate_limit
            ),
        )
    )

    print(
        "[EXHIBITION SOURCES MERGED] "
        f"Asia {len(asia_exhibition_urls)} 筆，"
        "North America "
        f"{len(north_america_exhibition_urls)} 筆，"
        f"合併後 {len(exhibition_urls)} 筆"
    )
    existing_domains = (
        load_recent_existing_domains(
            output_path=config.output_path,
            refresh_days=(
                config.brand_refresh_days
            ),
        )
    )

    print(
        "[BRAND MASTER] "
        f"讀取到 {len(existing_domains)} "
        "個近期已分析品牌"
    )

    google_records = build_records(
        urls_with_source=google_urls,
        start_index=1,
        max_count=google_limit,
        search_profile=search_profile,
        check_taiwan=(
            config.check_taiwan_distributor
        ),
        force_refresh_taiwan=(
            config.force_refresh_taiwan
        ),
        taiwan_cache_days=(
            config.taiwan_cache_days
        ),
        existing_domains=existing_domains,
        skip_existing_brands=(
            config.skip_existing_brands
        ),
        force_refresh_brands=(
            config.force_refresh_brands
        ),
    )

    exhibition_records = build_records(
        urls_with_source=exhibition_urls,
        start_index=(
            len(google_records) + 1
        ),
        max_count=exhibition_limit,
        search_profile=search_profile,
        check_taiwan=(
            config.check_taiwan_distributor
        ),
        force_refresh_taiwan=(
            config.force_refresh_taiwan
        ),
        taiwan_cache_days=(
            config.taiwan_cache_days
        ),
        existing_domains=existing_domains,
        skip_existing_brands=(
            config.skip_existing_brands
        ),
        force_refresh_brands=(
            config.force_refresh_brands
        ),
    )

    records = (
        google_records
        + exhibition_records
    )

    export_summary = export_vendor_records(
        records=records,
        output_path=config.output_path,
        incremental=True,
    )

    print(
        f"Done. Exported records to "
        f"{config.output_path}"
    )

    print(
        "本次找到："
        f"{export_summary['本次找到']}"
    )

    print(
        "新增品牌："
        f"{export_summary['新增品牌']}"
    )

    print(
        "更新品牌："
        f"{export_summary['更新品牌']}"
    )

    print(
        "品牌總數："
        f"{export_summary['資料庫總數']}"
    )

    print(
        "Google Search records: "
        f"{len(google_records)}"
    )

    print(
    "Official exhibition records: "
    f"{len(exhibition_records)}"
)
    return export_summary

