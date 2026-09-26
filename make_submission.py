"""Generate submission.jsonl for the 30 canonical challenge test pairs.

First expand the challenge seeds:
  python3 dataset/generate_dataset.py --seed-dir dataset --out /tmp/magicpin-expanded
Then:
  python3 make_submission.py --dataset /tmp/magicpin-expanded
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from bot import compose


def load_dir(path: Path, key: str):
    result = {}
    for file in path.glob("*.json"):
        value = json.loads(file.read_text(encoding="utf-8"))
        result[value.get(key, file.stem)] = value
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/expanded", help="Expanded dataset directory")
    parser.add_argument("--output", default="submission.jsonl", help="Output JSONL path")
    args = parser.parse_args()
    root = Path(args.dataset)
    categories = load_dir(root / "categories", "slug")
    merchants = load_dir(root / "merchants", "merchant_id")
    customers = load_dir(root / "customers", "customer_id")
    triggers = load_dir(root / "triggers", "id")
    pairs_path = root / "test_pairs.json"
    if not pairs_path.exists():
        raise SystemExit(f"Missing {pairs_path}; run dataset/generate_dataset.py first")
    pairs = json.loads(pairs_path.read_text(encoding="utf-8")).get("pairs", [])
    if len(pairs) != 30:
        raise SystemExit(f"Expected 30 canonical pairs, found {len(pairs)}")

    lines = []
    for pair in pairs:
        trigger = triggers[pair["trigger_id"]]
        merchant = merchants[pair["merchant_id"]]
        category = categories[merchant["category_slug"]]
        customer = customers.get(pair.get("customer_id")) if pair.get("customer_id") else None
        message = compose(category, merchant, trigger, customer)
        if not message["body"].strip():
            message["body"] = ""
        lines.append(json.dumps({"test_id": pair["test_id"], **message}, ensure_ascii=False))

    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} submissions to {args.output}")


if __name__ == "__main__":
    main()
