#!/usr/bin/env python
"""
Phase 2 evaluation script.

Computes:
  - Aspect extraction precision, recall, F1
  - Aspect-level sentiment accuracy

Usage
-----
    python scripts/evaluate.py                          # default CSV
    python scripts/evaluate.py --csv data/eval/labeled_sample.csv
    python scripts/evaluate.py --model lexicon          # force lexicon
    python scripts/evaluate.py --verbose                # show per-row details

IMPORTANT — accuracy limitations
---------------------------------
The labeled_sample.csv contains 20 HAND-WRITTEN placeholder examples.
These are NOT randomly sampled from production data and are NOT a
statistically valid benchmark.  Do NOT cite these numbers as production
model accuracy.  Replace the CSV rows with real hand-labeled production
examples before drawing any conclusions.

The synthetic demo dataset (source="demo", metadata.synthetic=true) is
explicitly excluded from this evaluation.  Accuracy on synthetic data
does not reflect performance on real reviews.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from pathlib import Path

# ── Make sure the project root is on sys.path ─────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Force lexicon unless overridden — avoids requiring torch in CI
os.environ.setdefault("SENTIMENT_MODEL", "lexicon")


def _load_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _parse_aspects(raw: str) -> list[str]:
    """Parse pipe-separated aspect list, strip whitespace."""
    return [a.strip() for a in raw.split("|") if a.strip()]


def _run_pipeline(
    text: str,
    aspect_config: dict,
    sentiment_model: str,
) -> tuple[list[str], dict[str, str]]:
    """
    Run aspect extraction + sentiment on *text*.
    Returns (predicted_aspects, {aspect: sentiment_label}).
    """
    from backend.nlp.sentiment import get_sentiment_analyzer, reset_sentiment_analyzer
    from backend.nlp.aspects import AspectExtractor

    reset_sentiment_analyzer()
    os.environ["SENTIMENT_MODEL"] = sentiment_model
    analyzer  = get_sentiment_analyzer(sentiment_model)
    extractor = AspectExtractor(aspect_config, analyzer)
    matches   = extractor.extract(text)

    pred_aspects = [m.aspect for m in matches]
    pred_sentiment = {m.aspect: (m.sentiment_label or "neutral") for m in matches}
    return pred_aspects, pred_sentiment


def _aspect_metrics(
    true_lists:  list[list[str]],
    pred_lists:  list[list[str]],
) -> dict:
    tp = fp = fn = 0
    for true, pred in zip(true_lists, pred_lists):
        true_set = set(true)
        pred_set = set(pred)
        tp += len(true_set & pred_set)
        fp += len(pred_set - true_set)
        fn += len(true_set - pred_set)

    precision  = tp / (tp + fp) if (tp + fp) else 0.0
    recall     = tp / (tp + fn) if (tp + fn) else 0.0
    f1         = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) else 0.0
    )
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4),
        "recall":    round(recall, 4),
        "f1":        round(f1, 4),
    }


def _sentiment_accuracy(
    true_sentiment_lists:  list[dict[str, str]],
    pred_sentiment_dicts:  list[dict[str, str]],
) -> dict:
    correct = total = 0
    for true_d, pred_d in zip(true_sentiment_lists, pred_sentiment_dicts):
        for aspect, true_label in true_d.items():
            if aspect in pred_d:
                total += 1
                if pred_d[aspect] == true_label:
                    correct += 1
    accuracy = round(correct / total, 4) if total else 0.0
    return {"correct": correct, "total": total, "accuracy": accuracy}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Phase 2 aspect extraction and sentiment."
    )
    parser.add_argument(
        "--csv",
        default=str(ROOT / "data" / "eval" / "labeled_sample.csv"),
        help="Path to labeled CSV file.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("SENTIMENT_MODEL", "lexicon"),
        help="Sentiment model name or 'lexicon' (default: lexicon).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-row details.",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Load domain config for aspect patterns
    from backend.api.domain_config import _load_yaml, list_available_domains
    domains = list_available_domains()
    if not domains:
        print("ERROR: No domain configs found in config/domains/.", file=sys.stderr)
        sys.exit(1)
    domain_cfg    = _load_yaml(domains[0])
    aspect_config = domain_cfg.get("aspect_config", {})

    rows = _load_csv(csv_path)
    print(f"\nEvaluation on: {csv_path}")
    print(f"Rows loaded  : {len(rows)}")
    print(f"Domain       : {domains[0]}")
    print(f"Model        : {args.model}")
    print(
        "\n⚠️  IMPORTANT: These {n} examples are hand-written placeholders, NOT a "
        "statistically valid sample.  Do not cite these numbers as production "
        "model accuracy.\n".format(n=len(rows))
    )

    true_aspect_lists:     list[list[str]]       = []
    pred_aspect_lists:     list[list[str]]       = []
    true_sentiment_lists:  list[dict[str, str]]  = []
    pred_sentiment_dicts:  list[dict[str, str]]  = []

    for row in rows:
        text           = row.get("text", "").strip()
        true_aspects   = _parse_aspects(row.get("true_aspects", ""))
        true_sents_raw = _parse_aspects(row.get("true_sentiment_per_aspect", ""))
        true_sent_dict = {
            asp: snt
            for asp, snt in zip(true_aspects, true_sents_raw)
        }

        pred_aspects, pred_sent = _run_pipeline(text, aspect_config, args.model)

        true_aspect_lists.append(true_aspects)
        pred_aspect_lists.append(pred_aspects)
        true_sentiment_lists.append(true_sent_dict)
        pred_sentiment_dicts.append(pred_sent)

        if args.verbose:
            print(f"\n  ID   : {row.get('id', '?')}")
            print(f"  Text : {text[:80]}{'…' if len(text) > 80 else ''}")
            print(f"  True aspects : {true_aspects}")
            print(f"  Pred aspects : {pred_aspects}")
            missed = set(true_aspects) - set(pred_aspects)
            extra  = set(pred_aspects) - set(true_aspects)
            if missed:
                print(f"  ❌ Missed    : {sorted(missed)}")
            if extra:
                print(f"  ⚠️  Extra    : {sorted(extra)}")
            for asp in set(true_aspects) & set(pred_aspects):
                t = true_sent_dict.get(asp, "?")
                p = pred_sent.get(asp, "?")
                mark = "✓" if t == p else "✗"
                print(f"  {mark} {asp}: true={t} pred={p}")

    # ── Metrics ───────────────────────────────────────────────────────────────
    asp_m  = _aspect_metrics(true_aspect_lists, pred_aspect_lists)
    sent_m = _sentiment_accuracy(true_sentiment_lists, pred_sentiment_dicts)

    print("\n" + "=" * 56)
    print("ASPECT EXTRACTION")
    print(f"  Precision : {asp_m['precision']:.4f}")
    print(f"  Recall    : {asp_m['recall']:.4f}")
    print(f"  F1        : {asp_m['f1']:.4f}")
    print(f"  TP={asp_m['tp']}  FP={asp_m['fp']}  FN={asp_m['fn']}")
    print()
    print("ASPECT-LEVEL SENTIMENT ACCURACY")
    print(f"  Accuracy  : {sent_m['accuracy']:.4f}")
    print(f"  {sent_m['correct']} correct / {sent_m['total']} matched aspects")
    print("=" * 56)
    print()
    print(
        "Reminder: replace data/eval/labeled_sample.csv rows with real "
        "hand-labelled production comments before citing these numbers."
    )


if __name__ == "__main__":
    main()
