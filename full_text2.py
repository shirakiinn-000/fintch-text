import argparse
import csv
import re
from pathlib import Path


DEFAULT_INPUT = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\标注数据\训练集扩展5000 保留2000review_flag=0 人工复核文件.csv"
)
DEFAULT_OUTPUT = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\标注数据\训练集扩展5000 保留2000review_flag=0 人工复核文件_full_text.csv"
)
FULL_TEXT_COL = "full_text"
FULL_TEXT_FIELDS = [
    ("企业名称", "企业名称"),
    ("招聘岗位", "招聘岗位"),
    ("职位描述", "职位描述"),
]


def clean_value(value: str | None) -> str:
    """Clean text only for full_text; keep original CSV columns unchanged."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def build_full_text(row: dict[str, str]) -> str:
    return " ".join(f"{label}：{clean_value(row.get(column))}" for label, column in FULL_TEXT_FIELDS)


def output_fields(input_fields: list[str]) -> list[str]:
    fields = [field for field in input_fields if field != FULL_TEXT_COL]
    fields.append(FULL_TEXT_COL)
    return fields


def add_full_text(input_path: Path, output_path: Path) -> int:
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.stem + ".full_text_tmp" + output_path.suffix)
    row_count = 0

    try:
        with input_path.open("r", encoding="utf-8-sig", newline="") as src:
            reader = csv.DictReader(src)
            if reader.fieldnames is None:
                raise ValueError(f"Input CSV has no header: {input_path}")

            fieldnames = output_fields(reader.fieldnames)
            with temp_path.open("w", encoding="utf-8-sig", newline="") as dst:
                writer = csv.DictWriter(dst, fieldnames=fieldnames)
                writer.writeheader()
                for row in reader:
                    row[FULL_TEXT_COL] = build_full_text(row)
                    writer.writerow({field: row.get(field, "") for field in fieldnames})
                    row_count += 1

        temp_path.replace(output_path)
        return row_count
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append/rebuild full_text for ESG recall sample CSV.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input CSV path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output CSV path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = add_full_text(args.input, args.output)
    print(f"input: {args.input}")
    print(f"output: {args.output}")
    print(f"rows: {rows}")


if __name__ == "__main__":
    main()
