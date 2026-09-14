from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.search_profile import SearchProfile
from modules.website_classifier import classify_website


def parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


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
                raise ValueError(
                    f"Invalid JSON on line {line_number}: {error}"
                ) from error

            if "url" not in row:
                raise ValueError(f"Line {line_number} is missing 'url'.")
            if "page_text" not in row:
                raise ValueError(f"Line {line_number} is missing 'page_text'.")
            if "expected_is_candidate" not in row:
                raise ValueError(
                    f"Line {line_number} is missing 'expected_is_candidate'."
                )
            if not isinstance(row["expected_is_candidate"], bool):
                raise ValueError(
                    f"Line {line_number}: 'expected_is_candidate' must be true/false."
                )

            rows.append(row)
    return rows


def safe_divide(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def calculate_metrics(results: list[dict]) -> dict:
    tp = sum(1 for row in results if row["expected"] and row["predicted"])
    tn = sum(1 for row in results if not row["expected"] and not row["predicted"])
    fp = sum(1 for row in results if not row["expected"] and row["predicted"])
    fn = sum(1 for row in results if row["expected"] and not row["predicted"])

    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    accuracy = safe_divide(tp + tn, len(results))
    f1 = safe_divide(2 * precision * recall, precision + recall)

    return {
        "total": len(results),
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the website LLM classifier against human labels."
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--product-keywords", default="")
    parser.add_argument("--positioning-keywords", default="")
    parser.add_argument("--excluded-keywords", default="")
    parser.add_argument("--included-countries", default="")
    parser.add_argument("--excluded-countries", default="")
    parser.add_argument("--included-regions", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/evaluation_results.json"),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    profile = SearchProfile(
        query=args.query,
        product_keywords=parse_list(args.product_keywords),
        positioning_keywords=parse_list(args.positioning_keywords),
        excluded_keywords=parse_list(args.excluded_keywords),
        included_countries=parse_list(args.included_countries),
        excluded_countries=parse_list(args.excluded_countries),
        included_regions=parse_list(args.included_regions),
    )

    dataset = load_jsonl(args.dataset)
    if args.limit > 0:
        dataset = dataset[: args.limit]

    if not dataset:
        raise ValueError("Dataset is empty.")

    results: list[dict] = []

    for index, row in enumerate(dataset, start=1):
        prediction = classify_website(
            url=row["url"],
            page_text=row["page_text"],
            search_profile=profile,
        )

        expected = row["expected_is_candidate"]
        predicted = bool(prediction.get("is_candidate", False))

        result = {
            "index": index,
            "url": row["url"],
            "expected": expected,
            "predicted": predicted,
            "correct": expected == predicted,
            "site_type": prediction.get("site_type", ""),
            "agency_fit_score": prediction.get("agency_fit_score", 0),
            "country": prediction.get("country", ""),
            "reason": prediction.get("reason", ""),
            "human_note": row.get("note", ""),
        }
        results.append(result)

        mark = "PASS" if result["correct"] else "FAIL"
        print(
            f"[{index}/{len(dataset)}] {mark} "
            f"expected={expected} predicted={predicted} {row['url']}"
        )

    metrics = calculate_metrics(results)

    payload = {
        "search_profile": {
            "query": profile.query,
            "product_keywords": profile.product_keywords,
            "positioning_keywords": profile.positioning_keywords,
            "excluded_keywords": profile.excluded_keywords,
            "included_countries": profile.included_countries,
            "excluded_countries": profile.excluded_countries,
            "included_regions": profile.included_regions,
        },
        "metrics": metrics,
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n=== Evaluation Summary ===")
    for key, value in metrics.items():
        print(f"{key}: {value}")
    print(f"\nSaved detailed results to: {args.output}")


if __name__ == "__main__":
    main()
