from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.crawler import fetch_website_text
from modules.search_profile import SearchProfile
from modules.website_classifier import classify_website


LIST_FIELDS = (
    "product_keywords",
    "positioning_keywords",
    "excluded_keywords",
    "included_countries",
    "excluded_countries",
    "included_regions",
)


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number}: {error}") from error

            for field in ("url", "expected_is_candidate", "search_profile"):
                if field not in row:
                    raise ValueError(f"Line {line_number} is missing '{field}'.")

            if not isinstance(row["expected_is_candidate"], bool):
                raise ValueError(
                    f"Line {line_number}: 'expected_is_candidate' must be true/false."
                )

            profile = row["search_profile"]
            if not isinstance(profile, dict) or not str(profile.get("query", "")).strip():
                raise ValueError(f"Line {line_number}: search_profile.query is required.")
            for field in LIST_FIELDS:
                value = profile.get(field, [])
                if not isinstance(value, list):
                    raise ValueError(
                        f"Line {line_number}: search_profile.{field} must be a list."
                    )
            rows.append(row)
    return rows


def build_profile(data: dict) -> SearchProfile:
    return SearchProfile(
        query=str(data["query"]).strip(),
        product_keywords=data.get("product_keywords", []),
        positioning_keywords=data.get("positioning_keywords", []),
        excluded_keywords=data.get("excluded_keywords", []),
        included_countries=data.get("included_countries", []),
        excluded_countries=data.get("excluded_countries", []),
        included_regions=data.get("included_regions", []),
        require_official_url=data.get("require_official_url", True),
        require_product_match=data.get("require_product_match", True),
        require_positioning_match=data.get("require_positioning_match", True),
        allow_unknown_country=data.get("allow_unknown_country", True),
    )


def safe_divide(numerator: int | float, denominator: int | float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def calculate_metrics(results: list[dict]) -> dict:
    evaluable = [row for row in results if row["status"] == "evaluated"]
    tp = sum(1 for row in evaluable if row["expected"] and row["predicted"])
    tn = sum(1 for row in evaluable if not row["expected"] and not row["predicted"])
    fp = sum(1 for row in evaluable if not row["expected"] and row["predicted"])
    fn = sum(1 for row in evaluable if row["expected"] and not row["predicted"])

    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    accuracy = safe_divide(tp + tn, len(evaluable))
    f1 = safe_divide(2 * precision * recall, precision + recall)

    return {
        "dataset_total": len(results),
        "evaluated": len(evaluable),
        "fetch_failed": sum(1 for row in results if row["status"] == "fetch_failed"),
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the website LLM classifier against human labels."
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--use-saved-text",
        action="store_true",
        help="Use page_text stored in JSONL instead of fetching the current website.",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("evaluation/evaluation_results.json")
    )
    args = parser.parse_args()

    dataset = load_jsonl(args.dataset)
    if args.limit > 0:
        dataset = dataset[: args.limit]
    if not dataset:
        raise ValueError("Dataset is empty.")

    results: list[dict] = []
    for index, row in enumerate(dataset, start=1):
        profile = build_profile(row["search_profile"])
        page_text = str(row.get("page_text", "")).strip() if args.use_saved_text else ""
        text_source = "saved" if page_text else "live"

        if not page_text:
            page_text = fetch_website_text(row["url"])

        base = {
            "index": index,
            "name": row.get("name", ""),
            "url": row["url"],
            "query": profile.query,
            "expected": row["expected_is_candidate"],
            "human_note": row.get("note", ""),
            "text_source": text_source,
        }

        if not page_text.strip():
            result = {
                **base,
                "status": "fetch_failed",
                "predicted": None,
                "correct": None,
                "site_type": "",
                "agency_fit_score": None,
                "country": "",
                "reason": "Website text could not be fetched; excluded from classifier metrics.",
            }
            results.append(result)
            print(f"[{index}/{len(dataset)}] FETCH_FAILED {row['url']}")
            continue

        prediction = classify_website(
            url=row["url"], page_text=page_text, search_profile=profile
        )
        expected = row["expected_is_candidate"]
        predicted = bool(prediction.get("is_candidate", False))
        result = {
            **base,
            "status": "evaluated",
            "predicted": predicted,
            "correct": expected == predicted,
            "site_type": prediction.get("site_type", ""),
            "agency_fit_score": prediction.get("agency_fit_score", 0),
            "country": prediction.get("country", ""),
            "reason": prediction.get("reason", ""),
        }
        results.append(result)
        mark = "PASS" if result["correct"] else "FAIL"
        print(
            f"[{index}/{len(dataset)}] {mark} expected={expected} "
            f"predicted={predicted} query={profile.query!r} {row['url']}"
        )

    metrics = calculate_metrics(results)
    payload = {"metrics": metrics, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== Evaluation Summary ===")
    for key, value in metrics.items():
        print(f"{key}: {value}")
    print(f"\nSaved detailed results to: {args.output}")


if __name__ == "__main__":
    main()
