import json
import argparse
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any

ALL_RESULTS = ["FE", "SE", "EN", "EF", "FA", "PM", "CM", "VC", "FR"]


def compute_percentages(counter: Counter, total: int) -> Dict[str, float]:
    if total == 0:
        return {r: 0.0 for r in ALL_RESULTS}
    return {r: round(counter.get(r, 0) / total * 100, 1) for r in ALL_RESULTS}


def load_json(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_single(input_path: Path, output_path: Path):
    data = load_json(input_path)
    counter = Counter(item.get("result") for item in data)
    total = len(data)
    percentages = compute_percentages(counter, total)
    percentages["_total"] = total

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(percentages, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {output_path}")
    print(f"Total: {total}")
    for r in ALL_RESULTS:
        print(f"  {r}: {percentages[r]}%")


def process_directory(input_dir: Path, output_path: Path):
    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in: {input_dir}")
        return

    per_file: Dict[str, Dict] = {}
    global_counter = Counter()
    global_total = 0

    for json_file in json_files:
        data = load_json(json_file)
        counter = Counter(item.get("result") for item in data)
        total = len(data)
        percentages = compute_percentages(counter, total)
        percentages["_total"] = total
        per_file[json_file.name] = percentages

        global_counter.update(counter)
        global_total += total

    global_percentages = compute_percentages(global_counter, global_total)
    global_percentages["_total"] = global_total

    result = {
        "per_file": per_file,
        "global": global_percentages,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {output_path}")
    print(f"\nFiles processed: {len(json_files)}")
    for name, stats in per_file.items():
        print(f"  {name}: total={stats['_total']}")
    print(f"\nGlobal (total={global_total}):")
    for r in ALL_RESULTS:
        print(f"  {r}: {global_percentages[r]}%")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compute result distribution statistics from eval JSON output(s)."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to a single JSON file or a directory containing JSON files.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="metrics.json",
        help="Path to save the result JSON.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    if input_path.is_file():
        process_single(input_path, output_path)
    else:
        process_directory(input_path, output_path)


if __name__ == "__main__":
    main()
