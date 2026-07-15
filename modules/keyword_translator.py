"""
把商品／定位關鍵字翻譯成目標語言。

策略：
1. 先查內建詞庫（人工校對過，常見歐洲語言準確且零成本）。
2. 詞庫沒有的組合，才呼叫 OpenAI 即時翻譯，並快取結果，
   同一個詞之後不會再重複翻譯、不會重複花錢。
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from modules.cache_manager import load_cache, save_cache


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# 翻譯快取長期有效——「shampoo 的德文怎麼講」
# 不會隨時間改變。
TRANSLATION_CACHE_EXPIRE_DAYS = 3650


# 人工校對過的常用詞彙，涵蓋目前商品/定位詞
# 最常遇到的歐洲語言。沒收錄的語言或詞彙，
# 由 translate_term() 自動用 AI 補上。
BUILTIN_TRANSLATIONS: dict[
    str, dict[str, str]
] = {
    "shampoo": {
        "german": "shampoo",
        "french": "shampooing",
        "italian": "shampoo",
        "spanish": "champú",
        "dutch": "shampoo",
        "polish": "szampon",
        "swedish": "schampo",
        "portuguese": "champô",
        "danish": "shampoo",
        "norwegian": "sjampo",
        "finnish": "shampoo",
    },
    "conditioner": {
        "german": "spülung",
        "french": "après-shampoing",
        "italian": "balsamo",
        "spanish": "acondicionador",
        "dutch": "conditioner",
        "polish": "odżywka",
        "swedish": "balsam",
        "portuguese": "condicionador",
        "danish": "balsam",
        "norwegian": "balsam",
        "finnish": "hoitoaine",
    },
    "hair care": {
        "german": "haarpflege",
        "french": "soin capillaire",
        "italian": "cura dei capelli",
        "spanish": "cuidado capilar",
        "dutch": "haarverzorging",
        "polish": "pielęgnacja włosów",
        "swedish": "hårvård",
        "portuguese": "cuidados capilares",
        "danish": "hårpleje",
        "norwegian": "hårpleie",
        "finnish": "hiustenhoito",
    },
    "scalp care": {
        "german": "kopfhautpflege",
        "french": "soin du cuir chevelu",
        "italian": (
            "cura del cuoio capelluto"
        ),
        "spanish": (
            "cuidado del cuero cabelludo"
        ),
        "dutch": (
            "hoofdhuidverzorging"
        ),
        "polish": (
            "pielęgnacja skóry głowy"
        ),
        "swedish": "hårbottenvård",
        "portuguese": (
            "cuidado do couro cabeludo"
        ),
        "danish": "hovedbundpleje",
        "norwegian": "hodebunnpleie",
        "finnish": "hiuspohjan hoito",
    },
    "organic": {
        "german": "bio",
        "french": "biologique",
        "italian": "biologico",
        "spanish": "orgánico",
        "dutch": "biologisch",
        "polish": "organiczny",
        "swedish": "ekologisk",
        "portuguese": "orgânico",
        "danish": "økologisk",
        "norwegian": "økologisk",
        "finnish": "luonnonmukainen",
    },
    "natural": {
        "german": "natürlich",
        "french": "naturel",
        "italian": "naturale",
        "spanish": "natural",
        "dutch": "natuurlijk",
        "polish": "naturalny",
        "swedish": "naturlig",
        "portuguese": "natural",
        "danish": "naturlig",
        "norwegian": "naturlig",
        "finnish": "luonnollinen",
    },
    "vegan": {
        "german": "vegan",
        "french": "vegan",
        "italian": "vegano",
        "spanish": "vegano",
        "dutch": "veganistisch",
        "polish": "wegański",
        "swedish": "vegansk",
        "portuguese": "vegano",
        "danish": "vegansk",
        "norwegian": "vegansk",
        "finnish": "vegaaninen",
    },
}


def normalize_key(value: str) -> str:
    return str(value or "").strip().lower()


def translate_term_with_ai(
    term: str,
    language: str,
) -> str | None:
    prompt = (
        f'Translate the beauty/cosmetics industry term "{term}" '
        f"into {language}. "
        "Return ONLY the translated term itself, "
        "no explanation, no quotes."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
        )

        translated = (
            response.choices[0]
            .message.content.strip()
            .strip('"')
            .strip()
        )

        return translated or term

    except Exception as error:
        print(
            "[TRANSLATE ERROR] "
            f"{term} -> {language}: {error}"
        )

        # 回傳 None：呼叫失敗不該永久快取成
        # 「這個詞沒有翻譯，就用原文」。
        return None


def translate_term(
    term: str,
    language: str,
) -> str:
    """
    把單一商品/定位詞翻譯成目標語言。

    English 不用翻譯，直接回傳原文。
    """

    normalized_language = normalize_key(
        language
    )

    if normalized_language in (
        "english",
        "",
    ):
        return term

    normalized_term = normalize_key(term)

    builtin = BUILTIN_TRANSLATIONS.get(
        normalized_term,
        {},
    ).get(normalized_language)

    if builtin:
        return builtin

    cache_key = (
        f"{normalized_term}::"
        f"{normalized_language}"
    )

    cached = load_cache(
        cache_type="keyword_translation",
        cache_key=cache_key,
        expire_days=(
            TRANSLATION_CACHE_EXPIRE_DAYS
        ),
    )

    if cached is not None:
        return cached.get(
            "translated",
            term,
        )

    translated = translate_term_with_ai(
        term=term,
        language=language,
    )

    if translated is None:
        # AI 呼叫失敗，不快取，讓下次呼叫可以重試，
        # 這次先用原文頂替，不影響當下流程。
        return term

    save_cache(
        cache_type="keyword_translation",
        cache_key=cache_key,
        data={
            "term": term,
            "language": language,
            "translated": translated,
        },
    )

    return translated


def translate_terms(
    terms: list[str],
    language: str,
) -> list[str]:
    """
    翻譯一組關鍵字，保留原始順序，並去除翻譯後重複的詞。
    """

    translated_terms = []

    for term in terms:
        translated = translate_term(
            term=term,
            language=language,
        )

        if (
            translated
            and translated
            not in translated_terms
        ):
            translated_terms.append(
                translated
            )

    return translated_terms


# 同義詞快取長期有效，原因跟翻譯快取一樣：
# 「shampoo 在美妝產業還有哪些常見說法」不會隨時間改變。
SYNONYM_CACHE_EXPIRE_DAYS = 3650

# 每個詞最多補幾個同義詞/詞形變化，避免無限擴張。
MAX_SYNONYMS_PER_TERM = 3


# 人工校對過的常見詞形變化與同義詞。
# 這些大多不是「完全不同的詞」，而是英文詞尾變化
# （conditioner/conditioning）、有無空格
# （hair care/haircare）等差異，實測證實這類差異
# 會讓字面比對完全漏掉大量真正符合的展商。
BUILTIN_SYNONYMS: dict[
    str, list[str]
] = {
    "shampoo": [
        "hair wash",
        "hair cleanser",
    ],
    "conditioner": [
        "conditioning",
        "hair conditioning",
    ],
    "hair care": [
        "haircare",
    ],
    "scalp care": [
        "scalp treatment",
        "scalp",
    ],
    "organic": [
        "bio",
    ],
    "natural": [
        "naturals",
    ],
    "vegan": [
        "plant-based",
    ],
}


def get_synonyms_with_ai(
    term: str,
) -> list[str] | None:
    prompt = (
        "List up to "
        f"{MAX_SYNONYMS_PER_TERM} "
        "common alternate words, spelling "
        "variants, or word-form variants "
        "(e.g. singular/plural, with/"
        "without space) used in the "
        "cosmetics/beauty industry for the "
        f'term "{term}". Only very close, '
        "direct alternatives — not broader "
        "or unrelated category terms. "
        "Return ONLY a JSON array of "
        "lowercase strings, no explanation. "
        'Example: ["term1", "term2"]'
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
        )

        content = (
            response.choices[0]
            .message.content.strip()
        )

        synonyms = json.loads(content)

        if not isinstance(
            synonyms,
            list,
        ):
            return []

        return [
            str(synonym).strip().lower()
            for synonym in synonyms
            if str(synonym).strip()
        ][:MAX_SYNONYMS_PER_TERM]

    except Exception as error:
        print(
            "[SYNONYM ERROR] "
            f"{term}: {error}"
        )

        # 回傳 None（不是空清單）：呼叫端要能分辨
        # 「AI 真的判斷沒有同義詞」跟「呼叫失敗」，
        # 失敗的話不該永久快取成「沒有同義詞」。
        return None


def get_synonyms(
    term: str,
) -> list[str]:
    """
    取得單一商品/定位詞的同義詞／詞形變化。

    先查內建詞庫，沒有才用 AI 產生並快取，
    同一個詞之後不會重複花錢查詢。
    """

    normalized_term = normalize_key(term)

    if not normalized_term:
        return []

    if (
        normalized_term
        in BUILTIN_SYNONYMS
    ):
        return BUILTIN_SYNONYMS[
            normalized_term
        ]

    cached = load_cache(
        cache_type="keyword_synonyms",
        cache_key=normalized_term,
        expire_days=(
            SYNONYM_CACHE_EXPIRE_DAYS
        ),
    )

    if cached is not None:
        return cached.get(
            "synonyms",
            [],
        )

    synonyms = get_synonyms_with_ai(
        term
    )

    if synonyms is None:
        # AI 呼叫失敗（例如連線錯誤），不快取，
        # 讓下次呼叫可以重試，而不是永久記成「沒有同義詞」。
        return []

    save_cache(
        cache_type="keyword_synonyms",
        cache_key=normalized_term,
        data={
            "term": term,
            "synonyms": synonyms,
        },
    )

    return synonyms


def expand_with_synonyms(
    terms: list[str],
) -> list[str]:
    """
    把一組關鍵字擴充成「原詞 + 同義詞／詞形變化」，
    保留原始順序並去除重複。

    只花錢／花時間在詞庫沒收錄的詞（會快取），
    詞庫已收錄的詞完全零成本。
    """

    expanded = []

    for term in terms:
        cleaned = str(term).strip()

        if (
            cleaned
            and cleaned not in expanded
        ):
            expanded.append(cleaned)

        for synonym in get_synonyms(
            cleaned
        ):
            if (
                synonym
                and synonym
                not in expanded
            ):
                expanded.append(
                    synonym
                )

    return expanded
