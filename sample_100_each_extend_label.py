from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

#额外岗位抽样600

DEFAULT_SOURCE_PATH = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据\advisor_recall_weighted_pool_sample_2014_2026_拓展岗位召回命中.csv"
)
DEFAULT_OUTPUT_PATH = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据\advisor_recall_weighted_pool_sample_2014_2026_拓展岗位召回命中_每标签100.csv"
)
LABEL_COL = "拓展召回标签"
SAMPLE_LABEL_COL = "抽样标签"
SAMPLE_RANK_COL = "抽样标签内序号"
DEFAULT_SAMPLE_SIZE = 100
SEED = "extend_label_sample_20260618"


def stable_key(label: str, row: dict[str, str], index: int) -> str:
    raw = "|".join(
        [
            SEED,
            label,
            row.get("id", ""),
            row.get("_source_row_number", ""),
            row.get("招聘岗位", ""),
            str(index),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sample_each_label(source_path: Path, output_path: Path, sample_size: int) -> dict[str, object]:
    rows_by_label: dict[str, list[tuple[str, int, dict[str, str]]]] = {}
    source_rows = 0

    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Source CSV has no header: {source_path}")
        if LABEL_COL not in reader.fieldnames:
            raise ValueError(f"Missing required column {LABEL_COL!r}: {source_path}")
        source_fields = list(reader.fieldnames)

        for index, row in enumerate(reader, start=1):
            source_rows += 1
            labels = [label.strip() for label in (row.get(LABEL_COL) or "").split(";") if label.strip()]
            for label in labels:
                rows_by_label.setdefault(label, []).append((stable_key(label, row, index), index, dict(row)))

    available_label_counts = {label: len(items) for label, items in sorted(rows_by_label.items())}
    shortage = {label: count for label, count in available_label_counts.items() if count < sample_size}
    if shortage:
        raise ValueError(f"Not enough rows for requested sample size {sample_size}: {shortage}")

    output_fields = source_fields + [SAMPLE_LABEL_COL, SAMPLE_RANK_COL]
    sampled_rows: list[dict[str, str]] = []
    for label in sorted(rows_by_label):
        selected = sorted(rows_by_label[label], key=lambda item: (item[0], item[1]))[:sample_size]
        for rank, (_, _, row) in enumerate(selected, start=1):
            out_row = dict(row)
            out_row[SAMPLE_LABEL_COL] = label
            out_row[SAMPLE_RANK_COL] = str(rank)
            sampled_rows.append(out_row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sampled_rows)

    return validate_output(output_path, output_fields, source_rows, available_label_counts)


def validate_output(
    output_path: Path,
    expected_fields: list[str],
    source_rows: int,
    available_label_counts: dict[str, int],
) -> dict[str, object]:
    with output_path.open("rb") as handle:
        has_bom = handle.read(3) == b"\xef\xbb\xbf"

    readback_counts: Counter[str] = Counter()
    output_rows = 0
    empty_sample_label_rows = 0
    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields_ok = (reader.fieldnames or []) == expected_fields
        for row in reader:
            output_rows += 1
            sample_label = row.get(SAMPLE_LABEL_COL) or ""
            if not sample_label:
                empty_sample_label_rows += 1
            readback_counts[sample_label] += 1

    return {
        "source_rows": source_rows,
        "available_label_counts": available_label_counts,
        "output_rows": output_rows,
        "readback_counts": dict(sorted(readback_counts.items())),
        "has_bom": has_bom,
        "fields_ok": fields_ok,
        "empty_sample_label_rows": empty_sample_label_rows,
        "output_path": str(output_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample N rows for each 拓展召回标签 from the hit CSV.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_PATH, help="Input 拓展岗位召回命中 CSV")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output sampled CSV")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE, help="Rows to sample per label")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = sample_each_label(args.source, args.output, args.sample_size)
    for key, value in summary.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
