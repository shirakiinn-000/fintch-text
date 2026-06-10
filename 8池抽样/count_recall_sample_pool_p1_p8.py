import argparse
import csv
from collections import Counter
from pathlib import Path


DEFAULT_INPUT_DIR = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据")
DEFAULT_OUTPUT = Path("advisor_recall_sample_pool_p1_p8_counts.csv")
YEARS = range(2014, 2027)
POOLS = [f"p{i}" for i in range(1, 9)]


def count_file(path: Path, pool_column: str) -> tuple[int, Counter]:
    counts: Counter[str] = Counter()
    total = 0

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header row")
        if pool_column not in reader.fieldnames:
            raise ValueError(f"{path} missing required column: {pool_column}")

        for row in reader:
            total += 1
            value = (row.get(pool_column) or "").strip().lower()
            if value in POOLS:
                counts[value] += 1
            elif value:
                counts[f"other:{value}"] += 1
            else:
                counts["blank"] += 1

    return total, counts


def write_summary(rows: list[dict[str, object]], output: Path) -> None:
    fieldnames = [
        "year",
        "source_file",
        "total_rows",
        *[f"{pool}_count" for pool in POOLS],
        *[f"{pool}_share" for pool in POOLS],
        "blank_count",
        "other_count",
    ]

    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_rows(input_dir: Path, pool_column: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    grand_total = 0
    grand_counts: Counter[str] = Counter()

    for year in YEARS:
        path = input_dir / f"advisor_recall_labeled_{year}.csv"
        if not path.exists():
            raise FileNotFoundError(path)

        total, counts = count_file(path, pool_column)
        grand_total += total
        grand_counts.update(counts)
        rows.append(format_row(str(year), path.name, total, counts))

    rows.append(format_row("TOTAL", "all_files", grand_total, grand_counts))
    return rows


def format_row(year: str, source_file: str, total: int, counts: Counter) -> dict[str, object]:
    row: dict[str, object] = {
        "year": year,
        "source_file": source_file,
        "total_rows": total,
        "blank_count": counts.get("blank", 0),
        "other_count": sum(v for k, v in counts.items() if k.startswith("other:")),
    }

    for pool in POOLS:
        row[f"{pool}_count"] = counts.get(pool, 0)
    for pool in POOLS:
        row[f"{pool}_share"] = f"{(counts.get(pool, 0) / total):.6%}" if total else "0.000000%"

    return row


def print_summary(rows: list[dict[str, object]]) -> None:
    columns = ["year", "total_rows", *[f"{pool}_count" for pool in POOLS]]
    print(",".join(columns))
    for row in rows:
        print(",".join(str(row[column]) for column in columns))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count sample_pool p1-p8 distribution for ESG recall labeled CSV files."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pool-column", default="sample_pool")
    args = parser.parse_args()

    rows = build_rows(args.input_dir, args.pool_column)
    write_summary(rows, args.output)
    print_summary(rows)
    print(f"\nWrote: {args.output.resolve()}")


if __name__ == "__main__":
    main()
