"""
在正式執行搜尋之前，估算大概會用掉多少 SerpAPI／OpenAI 用量，
以及大概要花多少時間。

估算方式盡量不花錢：
- Google 關鍵字數量直接用 generate_keywords() 算，不實際查詢。
- Asia／North America／Bologna 的符合家數用官方名錄即時比對，
  這幾個來源本身不收費，只是花一點時間。
- 分類通過率、每候選耗時、token 用量，
  是這次開發過程中用「有機天然洗髮精／歐洲」條件實測的經驗值，
  僅供參考，不同商品類別/地區冷門程度會有落差。
"""

from modules.candidate_filter import filter_candidates
from modules.exhibitions.cosmoprof_asia import (
    get_all_exhibitors as get_all_asia_exhibitors,
)
from modules.exhibitions.cosmoprof_bologna import (
    get_all_exhibitors as get_all_bologna_exhibitors,
)
from modules.exhibitions.cpna_dynamic_search import (
    search_cpna_candidates,
)
from modules.keyword_generator import generate_keywords


# 以下經驗值來自本次開發過程中的實測數據。
ASSUMED_ACCEPTANCE_RATE = 0.33

CLASSIFY_INPUT_TOKENS = 1500
CLASSIFY_OUTPUT_TOKENS = 200
TAIWAN_INPUT_TOKENS = 1000
TAIWAN_OUTPUT_TOKENS = 80

OPENAI_INPUT_PRICE_PER_1M_USD = 0.40
OPENAI_OUTPUT_PRICE_PER_1M_USD = 1.60

# 平行化後，用 target_count=10 實測全流程 246.9 秒
# （20 家：10 Google + 10 展覽）校正出的經驗值。
# 實際耗時會因網路狀況、Bologna 官網快取命中率而有落差，
# 這裡只取一個合理的中間值。
SECONDS_PER_CLASSIFY_ONLY_CANDIDATE = 2
SECONDS_PER_ACCEPTED_CANDIDATE_WITH_TAIWAN_CHECK = 5

# 收集階段（4 來源平行）實測耗時區間。
COLLECTION_PHASE_SECONDS_ESTIMATE = 70


def get_exhibition_candidate_limit(
    exhibition_limit: int,
) -> int:
    return max(
        exhibition_limit * 10,
        20,
    )


def estimate_search_cost(
    config,
    search_profile,
    *,
    fetch_live_exhibitor_counts: bool = True,
) -> dict:
    """
    估算一次搜尋大概的 API 用量、花費與時間。

    fetch_live_exhibitor_counts=True 時會即時向
    Cosmoprof Asia／North America 官方 API 取得符合條件的家數，
    這兩個 API 本身不收費，但需要幾秒到十幾秒的時間；
    設為 False 可以完全不花時間，但展覽端數字會用保守假設代替。
    """

    if config.test_mode:
        google_limit, exhibition_limit = 2, 2
    else:
        google_limit = config.target_count
        exhibition_limit = config.target_count

    exhibition_candidate_limit = (
        get_exhibition_candidate_limit(
            exhibition_limit
        )
    )

    keywords = generate_keywords(
        search_profile,
        languages=config.languages,
    )

    google_keyword_count = len(keywords)

    asia_matched_count = 0
    north_america_matched_count = 0
    bologna_matched_count = 0

    live_fetch_error = ""

    if fetch_live_exhibitor_counts:
        try:
            asia_exhibitors = (
                get_all_asia_exhibitors()
            )

            asia_matched_count = len(
                filter_candidates(
                    asia_exhibitors,
                    search_profile,
                )
            )

        except Exception as error:
            live_fetch_error += (
                f"Asia 名錄查詢失敗：{error}；"
            )

        try:
            query = (
                search_profile.query.strip()
                or " ".join(
                    search_profile.product_keywords
                )
            )

            cpna_result = search_cpna_candidates(
                query=query,
                max_records=(
                    exhibition_candidate_limit
                ),
            )

            north_america_matched_count = len(
                cpna_result.get("candidates", [])
            )

        except Exception as error:
            live_fetch_error += (
                "North America 名錄查詢失敗："
                f"{error}；"
            )

    try:
        bologna_exhibitors = (
            get_all_bologna_exhibitors()
        )

        bologna_matched_count = len(
            filter_candidates(
                bologna_exhibitors,
                search_profile,
            )
        )

    except Exception as error:
        live_fetch_error += (
            f"Bologna 名錄查詢失敗：{error}；"
        )

    total_exhibition_supply = (
        asia_matched_count
        + north_america_matched_count
        + bologna_matched_count
    )

    exhibition_pool_size = min(
        total_exhibition_supply,
        exhibition_candidate_limit,
    )

    # 需要檢視多少候選，才能湊到目標通過家數
    # （以實測通過率反推，並受限於實際候選池大小）。
    google_examined_estimate = min(
        round(
            google_limit
            / ASSUMED_ACCEPTANCE_RATE
        ),
        # Google 候選池大小無法事先得知，用關鍵字數*平均每組
        # 結果數(10)當作粗略上限。
        google_keyword_count * 10,
    )

    exhibition_examined_estimate = min(
        round(
            exhibition_limit
            / ASSUMED_ACCEPTANCE_RATE
        ),
        exhibition_pool_size,
    )

    accepted_google_estimate = min(
        google_limit,
        round(
            google_examined_estimate
            * ASSUMED_ACCEPTANCE_RATE
        ),
    )

    accepted_exhibition_estimate = min(
        exhibition_limit,
        round(
            exhibition_examined_estimate
            * ASSUMED_ACCEPTANCE_RATE
        ),
    )

    accepted_total_estimate = (
        accepted_google_estimate
        + accepted_exhibition_estimate
    )

    classify_calls_estimate = (
        google_examined_estimate
        + exhibition_examined_estimate
    )

    taiwan_check_calls_estimate = (
        accepted_total_estimate
        if config.check_taiwan_distributor
        else 0
    )

    bologna_website_lookup_estimate = min(
        bologna_matched_count,
        exhibition_candidate_limit,
    )

    serpapi_calls_estimate = (
        google_keyword_count
        + bologna_website_lookup_estimate
        + taiwan_check_calls_estimate * 3
    )

    openai_calls_estimate = (
        classify_calls_estimate
        + taiwan_check_calls_estimate
    )

    input_tokens_estimate = (
        classify_calls_estimate
        * CLASSIFY_INPUT_TOKENS
        + taiwan_check_calls_estimate
        * TAIWAN_INPUT_TOKENS
    )

    output_tokens_estimate = (
        classify_calls_estimate
        * CLASSIFY_OUTPUT_TOKENS
        + taiwan_check_calls_estimate
        * TAIWAN_OUTPUT_TOKENS
    )

    openai_cost_usd_estimate = (
        input_tokens_estimate
        / 1_000_000
        * OPENAI_INPUT_PRICE_PER_1M_USD
        + output_tokens_estimate
        / 1_000_000
        * OPENAI_OUTPUT_PRICE_PER_1M_USD
    )

    analysis_seconds_estimate = (
        (
            classify_calls_estimate
            - accepted_total_estimate
        )
        * SECONDS_PER_CLASSIFY_ONLY_CANDIDATE
        + accepted_total_estimate
        * SECONDS_PER_ACCEPTED_CANDIDATE_WITH_TAIWAN_CHECK
    )

    total_seconds_estimate = (
        COLLECTION_PHASE_SECONDS_ESTIMATE
        + analysis_seconds_estimate
    )

    return {
        "google_keyword_count": (
            google_keyword_count
        ),
        "asia_matched_count": (
            asia_matched_count
        ),
        "north_america_matched_count": (
            north_america_matched_count
        ),
        "bologna_matched_count": (
            bologna_matched_count
        ),
        "exhibition_pool_size": (
            exhibition_pool_size
        ),
        "accepted_total_estimate": (
            accepted_total_estimate
        ),
        "serpapi_calls_estimate": (
            serpapi_calls_estimate
        ),
        "openai_calls_estimate": (
            openai_calls_estimate
        ),
        "openai_cost_usd_estimate": (
            round(
                openai_cost_usd_estimate,
                3,
            )
        ),
        "total_seconds_estimate": (
            round(total_seconds_estimate)
        ),
        "live_fetch_error": (
            live_fetch_error
        ),
    }


def format_cost_estimate(
    estimate: dict,
) -> str:
    minutes = (
        estimate["total_seconds_estimate"]
        / 60
    )

    lines = [
        "=" * 60,
        "[搜尋用量預估]",
        "=" * 60,
        f"Google 關鍵字組數："
        f"{estimate['google_keyword_count']} 組",
        "展覽候選符合數："
        f"Asia {estimate['asia_matched_count']} 家 / "
        "North America "
        f"{estimate['north_america_matched_count']} 家 / "
        f"Bologna {estimate['bologna_matched_count']} 家",
        "預估通過 AI 篩選家數："
        f"約 {estimate['accepted_total_estimate']} 家",
        "-" * 60,
        "預估 SerpAPI 查詢次數："
        f"約 {estimate['serpapi_calls_estimate']} 次",
        "預估 OpenAI 呼叫次數："
        f"約 {estimate['openai_calls_estimate']} 次",
        "預估 OpenAI 費用："
        f"約 US${estimate['openai_cost_usd_estimate']:.3f}",
        "預估總耗時："
        f"約 {estimate['total_seconds_estimate']} 秒"
        f"（約 {minutes:.1f} 分鐘）",
        "=" * 60,
    ]

    if estimate.get("live_fetch_error"):
        lines.append(
            "[注意] 部分官方名錄查詢失敗，"
            "以下數字可能不準確："
        )
        lines.append(
            estimate["live_fetch_error"]
        )
        lines.append("=" * 60)

    return "\n".join(lines)
