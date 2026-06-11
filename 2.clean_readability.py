import csv
import re
from pathlib import Path

#任何文件，去除职位描述中的空格，把文件变可读

INPUT_PATH = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据\advisor_recall_weighted_pool_sample_2014_2026.csv")
OUTPUT_PATH = INPUT_PATH.with_name(INPUT_PATH.stem + "_readable.csv")
DESCRIPTION_COL = "职位描述"


def normalize_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def main() -> None:
    rows = 0
    changed = 0
    before_newline = 0
    before_multi_space = 0

    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="", errors="replace") as src:
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            raise RuntimeError("CSV header is empty")
        if DESCRIPTION_COL not in reader.fieldnames:
            raise RuntimeError(f"Missing target column: {DESCRIPTION_COL}")

        with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=reader.fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in reader:
                rows += 1
                original = row.get(DESCRIPTION_COL, "") or ""
                if "\n" in original or "\r" in original:
                    before_newline += 1
                if re.search(r"\s{2,}", original):
                    before_multi_space += 1
                cleaned = normalize_cell(original)
                if cleaned != original:
                    changed += 1
                    row[DESCRIPTION_COL] = cleaned
                writer.writerow(row)

    after_rows = 0
    after_newline = 0
    after_multi_space = 0
    after_columns = None
    with OUTPUT_PATH.open("r", encoding="utf-8-sig", newline="", errors="replace") as check:
        reader = csv.DictReader(check)
        after_columns = len(reader.fieldnames or [])
        for row in reader:
            after_rows += 1
            value = row.get(DESCRIPTION_COL, "") or ""
            if "\n" in value or "\r" in value:
                after_newline += 1
            if re.search(r"\s{2,}", value):
                after_multi_space += 1

    print(f"INPUT={INPUT_PATH}")
    print(f"OUTPUT={OUTPUT_PATH}")
    print(f"ROWS_IN={rows}")
    print(f"ROWS_OUT={after_rows}")
    print(f"COLUMNS_OUT={after_columns}")
    print(f"CHANGED_DESCRIPTION_CELLS={changed}")
    print(f"BEFORE_NEWLINE_CELLS={before_newline}")
    print(f"BEFORE_MULTI_SPACE_CELLS={before_multi_space}")
    print(f"AFTER_NEWLINE_CELLS={after_newline}")
    print(f"AFTER_MULTI_SPACE_CELLS={after_multi_space}")


if __name__ == "__main__":
    main()
