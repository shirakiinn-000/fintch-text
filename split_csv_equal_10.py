from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_SOURCE = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\标注数据\人工标注1000种子_full_text.csv")
DEFAULT_PARTS = 20


def detect_encoding(path: Path) -> tuple[str, bool]:
    has_bom = path.read_bytes()[:3] == b"\xef\xbb\xbf"
    return ("utf-8-sig" if has_bom else "utf-8"), has_bom


def split_counts(total_rows: int, parts: int) -> list[int]:
    base, remainder = divmod(total_rows, parts)
    return [base + (1 if index < remainder else 0) for index in range(parts)]


def output_path(source: Path, part_index: int) -> Path:
    return source.with_name(f"{source.stem}_part{part_index:02d}{source.suffix}")


def split_csv(source: Path, parts: int) -> None:
    if parts <= 0:
        raise ValueError("parts must be greater than zero")
    if not source.exists():
        raise FileNotFoundError(source)

    encoding, has_bom = detect_encoding(source)

    with source.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"empty CSV: {source}") from exc
        rows = list(reader)

    counts = split_counts(len(rows), parts)
    write_encoding = "utf-8-sig" if has_bom else "utf-8"

    offset = 0
    outputs: list[tuple[Path, int]] = []
    for part_index, count in enumerate(counts, start=1):
        part_path = output_path(source, part_index)
        part_rows = rows[offset : offset + count]
        offset += count
        with part_path.open("w", encoding=write_encoding, newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(part_rows)
        outputs.append((part_path, count))

    print(f"source={source}")
    print(f"data_rows={len(rows)}")
    print(f"parts={parts}")
    print(f"has_bom={has_bom}")
    for part_path, count in outputs:
        print(f"{part_path.name}\t{count}")
    validate_outputs(source, parts, expected_counts=counts)


def validate_outputs(source: Path, parts: int, expected_counts: list[int] | None = None) -> None:
    encoding, source_has_bom = detect_encoding(source)
    with source.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle)
        source_header = next(reader)
        source_rows = sum(1 for _ in reader)

    if expected_counts is None:
        expected_counts = split_counts(source_rows, parts)

    total_rows = 0
    failures: list[str] = []
    print("readback_validation:")
    for part_index, expected_count in enumerate(expected_counts, start=1):
        part_path = output_path(source, part_index)
        if not part_path.exists():
            failures.append(f"{part_path.name}: missing")
            continue
        part_encoding, part_has_bom = detect_encoding(part_path)
        with part_path.open("r", encoding=part_encoding, newline="") as handle:
            reader = csv.reader(handle)
            part_header = next(reader)
            part_rows = sum(1 for _ in reader)
        total_rows += part_rows
        print(f"{part_path.name}\trows={part_rows}\tbom={part_has_bom}")
        if part_rows != expected_count:
            failures.append(f"{part_path.name}: rows {part_rows} != {expected_count}")
        if part_header != source_header:
            failures.append(f"{part_path.name}: header mismatch")
        if source_has_bom and not part_has_bom:
            failures.append(f"{part_path.name}: missing BOM")

    if total_rows != source_rows:
        failures.append(f"total rows {total_rows} != {source_rows}")
    if failures:
        raise RuntimeError("; ".join(failures))
    print(f"validation=OK total_rows={total_rows}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Split a CSV into equal row-count parts.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--parts", type=int, default=DEFAULT_PARTS)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        validate_outputs(args.source, args.parts)
    else:
        split_csv(args.source, args.parts)


if __name__ == "__main__":
    main()
