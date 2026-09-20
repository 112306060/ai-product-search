import dataclasses
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from datetime import datetime

from modules.ai_analyzer import analyze_brand_page
from modules.crawler import fetch_website_text
from modules.excel_exporter import (
    export_vendor_records,
    load_existing_records,
    load_recent_existing_domains,
)
from modules.exhibition_search import (
    search_exhibition_sources,
)
from modules.keyword_generator import (
    MAX_KEYWORDS,
    PER_LANGUAGE_KEYWORD_BUDGET,
    generate_keywords,
    generate_keywords_for_language,
)
from modules.language_resolver import (
    resolve_search_languages,
)
from modules.search_engine import search_web
from modules.taiwan_distributor_checker import (
    check_taiwan_distributor,
)
from modules.url_utils import (
    dedupe_urls,
    get_brand_key,
)
from modules.website_classifier import classify_website
from modules.candidate_filter import filter_candidates
# 注意：modules.exhibitions 底下四支展覽爬蟲刻意不放在檔案頂端
# import——它們是選配模組（賣給其他產業客戶時不一定會交付這個
# 資料夾），改成在各自的 collect_cosmoprof_*_urls() 函式內部
# lazy import，這樣即使 modules/exhibitions/ 整個資料夾不存在，
# 只要 config.enable_exhibition_search=False，這支檔案本身
# 依然可以正常 import、正常執行 Google-only 搜尋。
from modules.search_cost_estimator import (
    estimate_search_cost,
    format_cost_estimate,
)
from modules.coverage_tracker import (
    record_run as record_coverage_run,
    summarize_coverage,
)
from modules.search_history import (
    record_search_run,
)


EMPTY_TAIWAN_RESULT = {
    "台灣代理狀態": "未執行",
    "台灣代理商名稱": "",
    "台灣代理證據": "",
    "台灣代理來源": "",
    "台灣檢查信心分數": "",
}


def build_taiwan_check_failed_result(
    error: Exception,
) -> dict:
    """
    台灣代理查證本身出錯時（例如 API 故障）的 fallback 結果。

    跟 EMPTY_TAIWAN_RESULT（使用者主動關閉查證）分開標示，
    避免搞混「沒查」跟「查了但失敗」，方便事後篩選出需要
    重新查證的候選。
    """
    return {
        "台灣代理狀態": "查證失敗",
        "台灣代理商名稱": "",
        "台灣代理證據": (
            "台灣代理查證時發生錯誤，其餘分析結果仍正常保留，"
            f"可稍後手動查證或重新分析：{error}"
        ),
        "台灣代理來源": "",
        "台灣檢查信心分數": "",
    }


# 以下併發數為保守預設值，若 SerpAPI 方案允許更高併發，
# 可以自行調高換取更快的搜尋速度。

# Google 關鍵字搜尋（每組關鍵字互不相依）。
GOOGLE_SEARCH_WORKERS = 5

# 一種語言搜尋完後，平均每組關鍵字要挖到至少幾家
# 「先前沒看過」的新候選，才算這個語言還有搜索價值；
# 低於這個門檻視為飽和，該換下一個權重的語言。
SATURATION_MIN_YIELD_PER_KEYWORD = 1.0

# 語言擴張除了看「這個語言還挖不挖得到新候選」，
# 也要看「累積候選數，相對於這次目標家數，是否已經
# 夠寬（留給後續 AI 篩選的緩衝）」——不然目標家數設得
# 很小（例如 1 家）時，就算每種語言都還有新候選，
# 也會一路把所有語言、所有關鍵字名額用完，
# 跟「只要 1 家」的本意不符。
# 這裡刻意抓比較寬鬆的倍數／下限，是因為候選要通過
# AI 判斷（品牌官網、符合定位、符合國家…）才會被接受，
# 實際接受率常常遠低於平均值，池子太小容易變成 0 家。
SEARCH_POOL_SAFETY_MULTIPLIER = 20
SEARCH_POOL_MIN_FLOOR = 40

# 每個語言至少會被搜尋的關鍵字組數，不管候選池是否已經
# 足夠都會執行完這一輪保底搜尋，才進入「候選池夠了就停」
# 的加碼邏輯。避免排序在前面的語言（尤其是英文，永遠排
# 第一個）單靠自己就填滿候選池，導致後面的語言完全沒被
# 搜過、一次都沒被看到——不是「省下來」，是根本沒機會。
MIN_KEYWORDS_PER_LANGUAGE = 4

# Bologna 展商官網查詢（每家公司互不相依）。
BOLOGNA_WEBSITE_LOOKUP_WORKERS = 5

# 四個收集來源（Google／Asia／North America／Bologna）本身互不相依。
COLLECTION_SOURCE_WORKERS = 4


def excel_record_to_candidate_dict(
    record: dict,
) -> dict:
    """
    把 Excel 裡已累積的一筆品牌紀錄，
    轉成跟展覽候選同樣格式，讓 candidate_filter
    可以用同一套商品／定位／國家比對邏輯，
    反查「這次搜尋條件，資料庫裡已經有哪些現成符合的公司」。
    """

    description_parts = [
        str(record.get("商品內容", "") or ""),
        str(record.get("AI判斷原因", "") or ""),
        str(record.get("評論", "") or ""),
    ]

    return {
        "company_name": record.get(
            "公司名稱",
            "",
        ),
        "product_category": record.get(
            "商品類別",
            "",
        ),
        "product_content": record.get(
            "商品內容",
            "",
        ),
        "description": " ".join(
            part
            for part in description_parts
            if part
        ),
        "official_url": (
            record.get("網站", "")
            or record.get("來源連結", "")
        ),
        "country": record.get(
            "國家",
            "",
        ),
        "_original_record": record,
    }


def match_existing_database_records(
    search_profile,
    output_path,
):
    """
    用這次的搜尋條件，反查已累積的資料庫裡
    有哪些現成符合的公司——資料庫本身會變成一個
    「越用越划算」的第4個資料來源：不管當初是用
    什麼關鍵字找到的，只要商品／定位／國家符合這次
    條件，就不需要再花一次 Google／AI 查詢。

    這些紀錄已經做過完整 AI 分析與台灣代理查證，
    直接沿用既有結果，不重新處理。
    """

    existing_records = load_existing_records(
        output_path
    )

    if not existing_records:
        return []

    candidate_dicts = [
        excel_record_to_candidate_dict(record)
        for record in existing_records
    ]

    matched = filter_candidates(
        candidate_dicts,
        search_profile,
    )

    matched_records = [
        candidate["_original_record"]
        for candidate in matched
    ]

    print(
        "[EXISTING DATABASE MATCH] "
        f"資料庫既有 {len(existing_records)} 筆中，"
        f"符合這次搜尋條件 {len(matched_records)} 筆"
        "（沿用既有分析結果，不重新查詢）"
    )

    return matched_records


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
        "搜尋名稱": (
            search_profile.query or ""
        ).strip(),
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


def build_single_record(
    url,
    source,
    source_metadata,
    index,
    search_profile,
    check_taiwan,
    force_refresh_taiwan,
    taiwan_cache_days,
):
    """
    處理單一候選網址，回傳一筆紀錄或 None（略過）。

    抽成獨立函式，讓呼叫端可以用 try/except
    包住單一候選的處理，避免一個候選發生非預期錯誤
    就讓整批結果消失。
    """

    is_bologna_exhibition_page = (
        source_metadata
        and "Bologna" in str(source)
        and "cosmoprof.com" in str(url)
    )

    if is_bologna_exhibition_page:
        print(
            "[BOLOGNA FALLBACK RECORD] "
            f"{source_metadata.get('展覽公司名稱', '')}"
        )

        return build_exhibition_fallback_record(
            url=url,
            source=source,
            source_metadata=source_metadata,
            index=index,
            search_profile=search_profile,
        )

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
                "[EXHIBITION FALLBACK RECORD - NO CONTENT] "
                f"{source_metadata.get('展覽公司名稱', '')}"
            )

            return build_exhibition_fallback_record(
                url=url,
                source=source,
                source_metadata=source_metadata,
                index=index,
                search_profile=search_profile,
            )

        else:
            return None

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
        return None

    record = analyze_brand_page(
        url=url,
        page_text=page_text,
        index=index,
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
        try:
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

        except Exception as error:
            # 台灣代理查證失敗不該連累前面已經花錢做完的
            # 爬蟲與 AI 分類結果——整筆候選仍然保留匯出，
            # 只是台灣代理狀態標成「查證失敗」，需要的話
            # 之後可以單獨重新查證。
            print(
                "[TAIWAN CHECK FAILED] "
                f"{record.get('公司名稱', '')}: {error}"
            )

            taiwan_result = (
                build_taiwan_check_failed_result(
                    error
                )
            )

        record.update(taiwan_result)

    else:
        record.update(
            EMPTY_TAIWAN_RESULT
        )

    return record


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
    stage_label="",
    progress_callback=None,
    cancel_check=None,
):
    """
    處理 Google 搜尋與展覽來源資料。

    支援兩種輸入：

    Google：
        (url, source)

    展覽：
        (url, source, source_metadata)

    單一候選處理失敗（爬蟲、AI 分類等非預期錯誤）
    只會略過該候選，不會讓整批結果消失。

    progress_callback（選填）：
        每處理一筆候選就呼叫一次，回報目前進度，
        供前端顯示進度條使用。

    cancel_check（選填）：
        每筆候選處理前檢查一次，回傳 True 時立即停止，
        已處理完的結果仍會保留、回傳給呼叫端。
    """

    records = []

    existing_domains = (
        existing_domains or set()
    )

    skipped_existing_count = 0

    total_candidates = len(
        urls_with_source
    )

    for position, source_item in enumerate(
        urls_with_source,
        start=1,
    ):
        if len(records) >= max_count:
            break

        if (
            cancel_check
            and cancel_check()
        ):
            print(
                "[CANCELLED] "
                f"使用者中止搜尋（{stage_label}），"
                f"已分析 {len(records)} 筆"
            )

            break

        if progress_callback:
            progress_callback(
                {
                    "stage": stage_label,
                    "current": position,
                    "total": total_candidates,
                    "accepted": len(records),
                }
            )

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

        domain = get_brand_key(url)

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

        try:
            record = build_single_record(
                url=url,
                source=source,
                source_metadata=source_metadata,
                index=start_index + len(records),
                search_profile=search_profile,
                check_taiwan=check_taiwan,
                force_refresh_taiwan=force_refresh_taiwan,
                taiwan_cache_days=taiwan_cache_days,
            )

        except Exception as error:
            print(
                "[CANDIDATE PROCESSING ERROR] "
                f"{url}: {error}"
            )

            continue

        if record is not None:
            records.append(record)

    if skipped_existing_count:
        print(
            "[EXISTING BRAND SKIPPED] "
            f"{skipped_existing_count} "
            "個近期品牌"
        )

    return records


def search_keyword_with_pagination(
    keyword,
    exclude_domains,
    enable_deep_pagination,
    max_pages_per_keyword,
):
    """
    查詢單一關鍵字，預設只拿第1頁（10筆）。

    enable_deep_pagination 開啟時，同一組關鍵字最多會
    翻到 max_pages_per_keyword 頁；只要某一頁 Google
    已經沒有結果可回傳，就代表這組關鍵字挖完了，
    直接停止，不會浪費查詢次數。
    """

    all_urls = []

    pages_to_try = (
        max_pages_per_keyword
        if enable_deep_pagination
        else 1
    )

    for page in range(1, pages_to_try + 1):
        start = (page - 1) * 10

        page_urls = search_web(
            keyword,
            exclude_domains=exclude_domains,
            start=start,
        )

        if not page_urls:
            break

        all_urls.extend(page_urls)

    return all_urls


def search_keywords_in_parallel(
    keywords,
    exclude_domains,
    enable_deep_pagination=False,
    max_pages_per_keyword=3,
):
    """
    平行查詢一批關鍵字，回傳 (url, source) 清單
    以及這批關鍵字總共貢獻了幾個先前沒看過的網域
    （由呼叫端傳入 seen_domains 集合並就地更新）。
    """

    urls_with_source = []

    with ThreadPoolExecutor(
        max_workers=GOOGLE_SEARCH_WORKERS
    ) as executor:
        future_to_keyword = {
            executor.submit(
                search_keyword_with_pagination,
                keyword,
                exclude_domains,
                enable_deep_pagination,
                max_pages_per_keyword,
            ): keyword
            for keyword in keywords
        }

        for future in as_completed(
            future_to_keyword
        ):
            keyword = future_to_keyword[
                future
            ]

            try:
                results = future.result()

            except Exception as error:
                print(
                    "[GOOGLE SEARCH ERROR] "
                    f"{keyword}: {error}"
                )
                continue

            for url in results:
                urls_with_source.append(
                    (
                        url,
                        "Google Search",
                    )
                )

    return urls_with_source


def collect_google_urls(
    config,
    search_profile,
):
    """
    依照使用者本次的 SearchProfile，
    動態決定搜尋語言並產生 Google 搜尋關鍵字。

    不再直接使用：
    config.product
    config.region
    config.languages（固定語言清單，已由動態語言解析取代）

    測試模式維持原本行為（只用英文、只取前 2 組），
    正式模式改成依國家/地區動態解析出的語言優先順序，
    一次搜一種語言，依該語言的實際成效（每組關鍵字
    平均挖到幾家新候選）決定要不要繼續換下一種語言，
    而不是一開始就固定用幾種語言。
    """

    print(
        "[SEARCH PROFILE] "
        f"{search_profile.query}"
    )

    if config.test_mode:
        keywords = generate_keywords(
            search_profile,
            languages=config.languages,
        )[:2]

        print(
            "[TEST MODE] "
            "只執行前 2 組英文關鍵字"
        )

        google_urls = (
            search_keywords_in_parallel(
                keywords,
                config.exclude_domains,
                enable_deep_pagination=(
                    config.enable_deep_pagination
                ),
                max_pages_per_keyword=(
                    config.max_pages_per_keyword
                ),
            )
        )

        return dedupe_urls(google_urls)

    languages = (
        resolve_search_languages(
            search_profile
        )
    )

    print(
        "[SEARCH LANGUAGES] "
        f"依搜尋條件解析出優先順序：{languages}"
    )

    google_limit, _ = get_search_limits(
        config
    )

    required_candidate_pool = max(
        google_limit
        * SEARCH_POOL_SAFETY_MULTIPLIER,
        SEARCH_POOL_MIN_FLOOR,
    )

    print(
        "[SEARCH POOL TARGET] "
        f"目標家數 {google_limit}，"
        f"預計累積約 {required_candidate_pool} "
        "家候選即可停止擴張語言"
    )

    google_urls = []
    seen_domains = set()
    keywords_used_total = 0

    def run_language_batch(
        language,
        language_keywords,
    ):
        """
        執行單一語言的一批關鍵字搜尋，
        更新累積結果，回傳這批關鍵字的
        新候選數（給呼叫端判斷是否飽和）。
        """

        nonlocal keywords_used_total

        print(
            "[LANGUAGE SEARCH] "
            f"目前使用語言：{language}"
            f"（{len(language_keywords)} "
            "組關鍵字）"
        )

        language_results = (
            search_keywords_in_parallel(
                language_keywords,
                config.exclude_domains,
                enable_deep_pagination=(
                    config.enable_deep_pagination
                ),
                max_pages_per_keyword=(
                    config.max_pages_per_keyword
                ),
            )
        )

        new_domains_this_batch = 0

        for (
            url,
            source,
        ) in language_results:
            domain = get_brand_key(url)

            if (
                domain
                and domain
                not in seen_domains
            ):
                seen_domains.add(domain)
                new_domains_this_batch += 1

            google_urls.append(
                (url, source)
            )

        keywords_used_total += len(
            language_keywords
        )

        return new_domains_this_batch

    if (
        len(languages) == 1
        and languages[0] == "english"
    ):
        # 只解析出英文（例如只選英美加）時，
        # 沒有其他語言需要保底，維持原本行為：
        # 不用省名額，直接用完整版本
        # （含 brand/professional/distributor）。
        remaining_budget = MAX_KEYWORDS

        language_keywords = (
            generate_keywords(
                search_profile,
                languages=(
                    config.languages
                ),
            )[:remaining_budget]
        )

        if language_keywords:
            new_domains = run_language_batch(
                "english",
                language_keywords,
            )

            print(
                "[LANGUAGE RESULT] "
                f"english 貢獻 {new_domains} "
                "家新候選（用了 "
                f"{len(language_keywords)} "
                "組關鍵字，累計 "
                f"{len(seen_domains)} 家）"
            )

        return dedupe_urls(google_urls)

    # 多語言情境：先讓每個語言各自的關鍵字清單
    # 一次生成好（同一語言的保底輪、加碼輪從同一份
    # 清單依序取用，不會因為分兩輪呼叫而重複生成、
    # 重複搜尋同一組關鍵字）。
    language_keyword_pool = {
        language: generate_keywords_for_language(
            search_profile,
            language,
            max_count=PER_LANGUAGE_KEYWORD_BUDGET,
        )
        for language in languages
    }

    language_stats = {}

    print(
        "[保底輪開始] "
        f"每個語言至少搜尋 "
        f"{MIN_KEYWORDS_PER_LANGUAGE} "
        "組關鍵字，確保後面的語言不會"
        "因為前面語言已經填滿候選池"
        "而完全沒被搜過"
    )

    for language in languages:
        remaining_budget = (
            MAX_KEYWORDS
            - keywords_used_total
        )

        if remaining_budget <= 0:
            print(
                "[KEYWORD LIMIT] "
                "已用完全部關鍵字名額，"
                "保底輪提前結束"
            )
            break

        full_list = language_keyword_pool.get(
            language,
            [],
        )

        floor_count = min(
            MIN_KEYWORDS_PER_LANGUAGE,
            len(full_list),
            remaining_budget,
        )

        language_keywords = full_list[
            :floor_count
        ]

        if not language_keywords:
            language_stats[language] = {
                "keywords_used": 0,
                "is_saturated": True,
            }
            continue

        new_domains = run_language_batch(
            language,
            language_keywords,
        )

        yield_rate = (
            new_domains
            / len(language_keywords)
        )

        is_low_yield = (
            yield_rate
            < SATURATION_MIN_YIELD_PER_KEYWORD
        )

        language_stats[language] = {
            "keywords_used": len(
                language_keywords
            ),
            "is_saturated": is_low_yield,
        }

        print(
            "[保底輪] "
            f"{language} 貢獻 {new_domains} "
            "家新候選（用了 "
            f"{len(language_keywords)} "
            "組關鍵字，累計 "
            f"{len(seen_domains)} 家）"
            + (
                "，判定飽和"
                if is_low_yield
                else ""
            )
        )

    # 加碼輪：保底輪跑完之後，如果候選池還不夠，
    # 才依語言優先順序繼續加碼，判定飽和的語言
    # 保底輪已經看過一次，直接跳過不加碼。
    for language_index, language in (
        enumerate(languages)
    ):
        pool_is_sufficient = (
            len(seen_domains)
            >= required_candidate_pool
        )

        if pool_is_sufficient:
            print(
                "[POOL SUFFICIENT] "
                f"已累積 {len(seen_domains)} "
                "家候選，相對目標家數 "
                f"{google_limit} 已足夠，"
                "停止加碼"
            )
            break

        stats = language_stats.get(
            language,
            {
                "keywords_used": 0,
                "is_saturated": True,
            },
        )

        if stats["is_saturated"]:
            continue

        remaining_budget = (
            MAX_KEYWORDS
            - keywords_used_total
        )

        if remaining_budget <= 0:
            print(
                "[KEYWORD LIMIT] "
                "已用完全部關鍵字名額，"
                "停止加碼"
            )
            break

        full_list = language_keyword_pool.get(
            language,
            [],
        )

        already_used = stats[
            "keywords_used"
        ]

        topup_count = min(
            len(full_list) - already_used,
            remaining_budget,
        )

        if topup_count <= 0:
            continue

        language_keywords = full_list[
            already_used:
            already_used + topup_count
        ]

        new_domains = run_language_batch(
            language,
            language_keywords,
        )

        yield_rate = (
            new_domains
            / len(language_keywords)
        )

        is_low_yield = (
            yield_rate
            < SATURATION_MIN_YIELD_PER_KEYWORD
        )

        print(
            "[加碼輪] "
            f"{language} 貢獻 {new_domains} "
            "家新候選（用了 "
            f"{len(language_keywords)} "
            "組關鍵字，累計 "
            f"{len(seen_domains)} 家）"
            + (
                "，判定飽和"
                if is_low_yield
                else ""
            )
        )

        is_last_language = (
            language_index
            == len(languages) - 1
        )

        should_continue = (
            not is_last_language
            and keywords_used_total
            < MAX_KEYWORDS
        )

        if (
            should_continue
            and config.require_language_switch_confirmation
        ):
            next_language = languages[
                language_index + 1
            ]

            status = (
                "已飽和"
                if is_low_yield
                else "仍有成效"
            )

            answer = input(
                f"[語言切換確認] {language} "
                f"搜尋{status}，目前累計 "
                f"{len(seen_domains)} "
                "家候選。是否切換至 "
                f"{next_language} "
                "繼續搜尋？(y/N): "
            ).strip().lower()

            if answer not in (
                "y",
                "yes",
            ):
                print(
                    "[STOPPED] "
                    "使用者選擇停止語言擴張"
                )
                break

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

    try:
        from modules.exhibitions.cosmoprof_asia import (
            get_all_exhibitors,
        )

        exhibitors = get_all_exhibitors()

    except Exception as error:
        print(
            "[COSMOPROF ASIA ERROR] "
            "展覽名錄模組未安裝或查詢失敗："
            f"{error}"
        )
        return []

    # Asia 的公司描述雖然是真實文案，但定位詞清單
    # （organic/natural/vegan…）終究有限，公司可能用
    # 其他說法描述定位（例如 eco-conscious、clean
    # beauty），字面比對不到就會被誤刷掉。跟 Bologna
    # 一樣，先只用商品詞篩選候選，定位判斷交給後面
    # AI 讀取真實官網內容時再做，避免預篩階段誤傷。
    asia_filter_profile = dataclasses.replace(
        search_profile,
        require_positioning_match=False,
    )

    matched_exhibitors = filter_candidates(
        exhibitors,
        asia_filter_profile,
    )

    print(
        "[COSMOPROF ASIA FILTER] "
        f"{len(exhibitors)} 筆中符合 "
        f"{len(matched_exhibitors)} 筆"
        "（此來源定位詞判斷交由後續 AI 分析）"
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


def collect_cosmoprof_bologna_urls(
    search_profile,
    max_count,
    resolve_official_website=True,
):
    """
    從 Cosmoprof Bologna 官方 cache 取得展商，
    依照 SearchProfile 篩選，並保留展覽資料。

    resolve_official_website：
        Bologna 官方名錄本身沒有公開展商官網，
        預設會用公司名稱查詢 Google 找出真正官網，
        找到的話就能走一般爬取與 AI 分析流程；
        找不到才維持原本的展覽描述 fallback。
    """

    if max_count <= 0:
        print(
            "[COSMOPROF BOLOGNA DISABLED] "
            "本次未啟用 Bologna 官方展覽來源"
        )
        return []

    try:
        from modules.exhibitions.cosmoprof_bologna import (
            get_all_exhibitors as get_all_bologna_exhibitors,
        )

        exhibitors = (
            get_all_bologna_exhibitors()
        )

    except Exception as error:
        print(
            "[COSMOPROF BOLOGNA ERROR] "
            "展覽名錄模組未安裝或查詢失敗：",
            error,
        )
        return []

    # Bologna 官方名錄的 description 完全是合成文字
    # （分類名稱＋展區＋場次日期），沒有任何真實品牌介紹，
    # 定位詞（organic/natural/vegan）比對在這裡並不可靠——
    # 只有剛好被歸類在名稱本身含有這些字的分類下才會通過，
    # 會誤刷掉許多真正符合定位、但被歸在通用分類的公司。
    # 因此先只用商品詞篩選，定位判斷交給後面「找到真官網
    # →AI 讀真實內容」那一步（跟 North America 的作法一致：
    # North America 本來就不在這裡做文字定位比對）。
    bologna_filter_profile = dataclasses.replace(
        search_profile,
        require_positioning_match=False,
    )

    matched_exhibitors = filter_candidates(
        exhibitors,
        bologna_filter_profile,
    )

    print(
        "[COSMOPROF BOLOGNA FILTER] "
        f"{len(exhibitors)} 筆中符合 "
        f"{len(matched_exhibitors)} 筆"
        "（此來源定位詞判斷交由後續 AI 分析）"
    )

    # Bologna 每家展商的 official_url 目前一定非空
    # （沒有真官網時會 fallback 成 detail_url），
    # 所以先截斷到 max_count 家，跟原本逐一計數 break
    # 的結果完全一致，之後才平行查詢官網，
    # 避免平行化多查超過原本需要的家數。
    exhibitors_to_process = (
        matched_exhibitors[:max_count]
    )

    resolved_websites = [
        "" for _ in exhibitors_to_process
    ]

    if resolve_official_website:
        from modules.exhibitions.cosmoprof_bologna_website_finder import (
            resolve_official_website as resolve_bologna_official_website,
        )

        with ThreadPoolExecutor(
            max_workers=(
                BOLOGNA_WEBSITE_LOOKUP_WORKERS
            )
        ) as executor:
            future_to_index = {}

            for index, exhibitor in enumerate(
                exhibitors_to_process
            ):
                company_name = exhibitor.get(
                    "company_name",
                    "",
                )

                if not company_name:
                    continue

                future = executor.submit(
                    resolve_bologna_official_website,
                    company_name,
                )

                future_to_index[future] = index

            for future in as_completed(
                future_to_index
            ):
                index = future_to_index[future]

                try:
                    resolved_websites[index] = (
                        future.result()
                    )

                except Exception as error:
                    company_name = (
                        exhibitors_to_process[
                            index
                        ].get(
                            "company_name",
                            "",
                        )
                    )

                    print(
                        "[BOLOGNA WEBSITE LOOKUP ERROR] "
                        f"{company_name}: {error}"
                    )

    source_items = []

    for index, exhibitor in enumerate(
        exhibitors_to_process
    ):
        official_url = exhibitor.get(
            "official_url",
            "",
        )

        if not official_url:
            continue

        found_website = resolved_websites[
            index
        ]

        if found_website:
            official_url = found_website

        source = exhibitor.get(
            "source",
            "Cosmoprof Bologna",
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
            "展覽描述": exhibitor.get(
                "description",
                "",
            ),
            "Bologna官方分類代碼": (
                ", ".join(
                    str(code)
                    for code in exhibitor.get(
                        "bologna_category_codes",
                        [],
                    )
                )
            ),
            "Bologna官方分類名稱": (
                " / ".join(
                    str(name)
                    for name in exhibitor.get(
                        "bologna_category_names",
                        [],
                    )
                )
            ),
            "BolognaHall": exhibitor.get(
                "bologna_hall",
                "",
            ),
            "BolognaStand": exhibitor.get(
                "bologna_stand",
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

    print(
        "[COSMOPROF BOLOGNA URLS] "
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
        from modules.exhibitions.cpna_dynamic_search import (
            search_cpna_candidates,
        )

        result = search_cpna_candidates(
            query=query,
            max_records=None,
            included_countries=list(
                search_profile.normalized_included_countries()
            ),
        )

    except Exception as error:
        print(
            "[CPNA DYNAMIC SEARCH ERROR] "
            "展覽名錄模組未安裝或查詢失敗：",
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
            domain = get_brand_key(url)

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
    progress_callback=None,
    cancel_check=None,
):
    """
    執行完整搜尋流程。

    config：
        系統執行設定，例如輸出路徑、
        測試模式、API 快取設定。

    search_profile：
        使用者本次搜尋條件，例如商品、
        定位、國家與地區條件。

    progress_callback（選填）：
        接收 dict（stage/current/total/accepted），
        供前端顯示即時進度。

    cancel_check（選填）：
        回傳 True 時中止搜尋。收集階段（Google 關鍵字
        搜尋、展覽名錄比對）本身無法立即中斷，但一結束
        就會檢查一次；逐一分析候選的階段（最花 API 額度）
        則每筆之間都會檢查，可以在數秒內停止。
        中止前已分析、已存檔的結果都會保留，不會浪費。
    """

    def report_progress(stage):
        if progress_callback:
            progress_callback(
                {
                    "stage": stage,
                    "current": 0,
                    "total": 0,
                    "accepted": 0,
                }
            )

    def is_cancelled():
        return bool(
            cancel_check
            and cancel_check()
        )

    def build_cancelled_summary(
        records_found,
        added,
        updated,
        total_in_database,
    ):
        return {
            "本次找到": records_found,
            "新增品牌": added,
            "更新品牌": updated,
            "資料庫總數": total_in_database,
            "cancelled": True,
        }

    if config.show_cost_estimate:
        try:
            estimate = estimate_search_cost(
                config,
                search_profile,
            )

            print(
                format_cost_estimate(
                    estimate
                )
            )

        except Exception as error:
            print(
                "[COST ESTIMATE FAILED] "
                f"{error}"
            )

        try:
            match_existing_database_records(
                search_profile,
                config.output_path,
            )

        except Exception as error:
            print(
                "[EXISTING DATABASE MATCH FAILED] "
                f"{error}"
            )

        if config.require_run_confirmation:
            answer = input(
                "是否繼續執行搜尋？(y/N): "
            ).strip().lower()

            if answer not in (
                "y",
                "yes",
            ):
                print(
                    "[CANCELLED] "
                    "使用者取消本次搜尋"
                )

                return {
                    "本次找到": 0,
                    "新增品牌": 0,
                    "更新品牌": 0,
                    "資料庫總數": 0,
                    "cancelled": True,
                }

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

    report_progress(
        "正在收集候選名單"
        "（Google 搜尋 + 三大展覽名錄）..."
    )

    print(
        "[SOURCE TOGGLE] "
        f"Google 搜尋："
        f"{'開啟' if config.enable_google_search else '關閉'}，"
        "展覽名錄（Asia／North America／Bologna）："
        f"{'開啟' if config.enable_exhibition_search else '關閉'}"
    )

    # 四個收集來源互不相依，平行執行以節省時間，
    # 而不是依序一個接一個等待。
    # 此階段本身無法立即中斷，結束後才會檢查是否已中止。
    # 使用者可以透過 config 關閉 Google 或展覽名錄其中一種，
    # 關閉的來源直接不送出查詢，不會產生任何 API 用量。
    with ThreadPoolExecutor(
        max_workers=COLLECTION_SOURCE_WORKERS
    ) as executor:
        google_future = (
            executor.submit(
                collect_google_urls,
                config=config,
                search_profile=search_profile,
            )
            if config.enable_google_search
            else None
        )

        asia_future = (
            executor.submit(
                collect_cosmoprof_asia_urls,
                search_profile=search_profile,
                max_count=(
                    exhibition_candidate_limit
                ),
            )
            if config.enable_exhibition_search
            else None
        )

        north_america_future = (
            executor.submit(
                collect_cosmoprof_north_america_urls,
                search_profile=search_profile,
                max_count=(
                    exhibition_candidate_limit
                ),
            )
            if config.enable_exhibition_search
            else None
        )

        bologna_future = (
            executor.submit(
                collect_cosmoprof_bologna_urls,
                search_profile=search_profile,
                max_count=(
                    exhibition_candidate_limit
                ),
                resolve_official_website=(
                    config.resolve_bologna_official_websites
                ),
            )
            if config.enable_exhibition_search
            else None
        )

        google_urls = (
            google_future.result()
            if google_future
            else []
        )
        asia_exhibition_urls = (
            asia_future.result()
            if asia_future
            else []
        )
        north_america_exhibition_urls = (
            north_america_future.result()
            if north_america_future
            else []
        )
        bologna_exhibition_urls = (
            bologna_future.result()
            if bologna_future
            else []
        )

    exhibition_urls = (
        merge_exhibition_source_items(
            source_groups=[
                asia_exhibition_urls,
                north_america_exhibition_urls,
                bologna_exhibition_urls,
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
        "Bologna "
        f"{len(bologna_exhibition_urls)} 筆，"
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

    if is_cancelled():
        print(
            "[CANCELLED] "
            "使用者中止搜尋（收集階段結束後、"
            "尚未開始分析任何候選）"
        )

        summary = build_cancelled_summary(
            records_found=0,
            added=0,
            updated=0,
            total_in_database=len(
                load_existing_records(
                    config.output_path
                )
            ),
        )
        record_search_run(
            search_profile, config, summary
        )
        return summary

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
        stage_label="Google 搜尋候選",
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )

    # Google 端結果先立即存檔，
    # 避免展覽端分析途中出狀況時，
    # 前面已經跑完的結果整批消失。
    google_export_summary = (
        export_vendor_records(
            records=google_records,
            output_path=config.output_path,
            incremental=True,
        )
    )

    print(
        "[INCREMENTAL SAVE] "
        f"Google 搜尋結果已先儲存："
        f"{len(google_records)} 筆"
    )

    if is_cancelled():
        print(
            "[CANCELLED] "
            "使用者中止搜尋（Google 端已存檔，"
            "尚未開始分析展覽名錄候選）"
        )

        summary = build_cancelled_summary(
            records_found=len(
                google_records
            ),
            added=google_export_summary[
                "新增品牌"
            ],
            updated=google_export_summary[
                "更新品牌"
            ],
            total_in_database=(
                google_export_summary[
                    "資料庫總數"
                ]
            ),
        )
        record_search_run(
            search_profile, config, summary
        )
        return summary

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
        stage_label="展覽名錄候選",
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )

    exhibition_export_summary = (
        export_vendor_records(
            records=exhibition_records,
            output_path=config.output_path,
            incremental=True,
        )
    )

    records = (
        google_records
        + exhibition_records
    )

    export_summary = {
        "本次找到": len(records),
        "新增品牌": (
            google_export_summary["新增品牌"]
            + exhibition_export_summary[
                "新增品牌"
            ]
        ),
        "更新品牌": (
            google_export_summary["更新品牌"]
            + exhibition_export_summary[
                "更新品牌"
            ]
        ),
        "鎖定跳過": (
            google_export_summary.get(
                "鎖定跳過", 0
            )
            + exhibition_export_summary.get(
                "鎖定跳過", 0
            )
        ),
        "資料庫總數": (
            exhibition_export_summary[
                "資料庫總數"
            ]
        ),
    }

    if is_cancelled():
        # 展覽名錄分析途中被中止，
        # 已處理完的部分仍已存檔（見上方 build_records
        # 的 cancel_check），這裡只是把結果標記為中止，
        # 讓前端知道這不是完整跑完的結果。
        export_summary["cancelled"] = True

        print(
            "[CANCELLED] "
            "使用者中止搜尋（展覽名錄分析階段），"
            "已保留目前已分析結果"
        )

        record_search_run(
            search_profile,
            config,
            export_summary,
        )

        return export_summary

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

    try:
        coverage_history = (
            record_coverage_run(
                profile=search_profile,
                new_count=(
                    export_summary["新增品牌"]
                ),
                total_count=(
                    export_summary["資料庫總數"]
                ),
            )
        )

        print()
        print(
            summarize_coverage(
                coverage_history
            )
        )

    except Exception as error:
        print(
            "[COVERAGE TRACKING FAILED] "
            f"{error}"
        )

    record_search_run(
        search_profile, config, export_summary
    )

    return export_summary