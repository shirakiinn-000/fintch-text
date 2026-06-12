import argparse
import csv
from pathlib import Path

#样本均等分成两份

DEFAULT_INPUT = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\标注数据\advisor_recall_weighted_pool_sample_2014_2026.csv"
)


def split_csv_equal_parts(input_path: Path, output1: Path | None = None, output2: Path | None = None) -> tuple[Path, Path, int, int]:
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    output1 = output1 or input_path.with_name(input_path.stem + "_part1.csv")
    output2 = output2 or input_path.with_name(input_path.stem + "_part2.csv")

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        total_rows = sum(1 for _ in reader)

    split_at = (total_rows + 1) // 2
    counts = [0, 0]

    with input_path.open("r", encoding="utf-8-sig", newline="") as f, \
            output1.open("w", encoding="utf-8-sig", newline="") as f1, \
            output2.open("w", encoding="utf-8-sig", newline="") as f2:
        reader = csv.reader(f)
        header = next(reader)
        writers = [csv.writer(f1), csv.writer(f2)]
        writers[0].writerow(header)
        writers[1].writerow(header)

        for idx, row in enumerate(reader):
            part = 0 if idx < split_at else 1
            writers[part].writerow(row)
            counts[part] += 1

    validate_output(output1, header, counts[0])
    validate_output(output2, header, counts[1])
    return output1, output2, counts[0], counts[1]


def validate_output(path: Path, expected_header: list[str], expected_rows: int) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = sum(1 for _ in reader)

    if header != expected_header:
        raise RuntimeError(f"Header mismatch: {path}")
    if rows != expected_rows:
        raise RuntimeError(f"Row mismatch: {path}: {rows} != {expected_rows}")
    if path.read_bytes()[:3] != bytes([239, 187, 191]):
        raise RuntimeError(f"Missing UTF-8 BOM: {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split a CSV into two equal row-count parts.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output1", type=Path, default=None)
    parser.add_argument("--output2", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output1, output2, rows1, rows2 = split_csv_equal_parts(args.input, args.output1, args.output2)
    print(f"INPUT={args.input}")
    print(f"PART1={output1}")
    print(f"PART1_ROWS={rows1}")
    print(f"PART2={output2}")
    print(f"PART2_ROWS={rows2}")
    print("VALIDATED=True")


if __name__ == "__main__":
    main()
