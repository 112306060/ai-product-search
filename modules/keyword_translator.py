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
) -> str:
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

        return term


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
