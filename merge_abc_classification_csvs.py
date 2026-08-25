from __future__ import annotations

import argparse
import csv
from pathlib import Path


INPUT_FILES = [
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part01_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part02_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part03_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part04_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part05_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part06_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part07_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part08_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part09_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part10_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part11_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part12_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part13_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part14_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part15_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part16_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part17_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part18_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part19_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part20_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part21_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part22_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part23_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part24_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part25_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part26_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part27_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part28_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part29_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part30_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part31_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part32_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part33_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part34_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part35_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part36_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part37_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part38_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part39_已标注.csv"),
    Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag0_人工复核文件_part40_已标注.csv"),
]

OUTPUT_FILE = Path(r"E:\浏览器下载\训练集扩展5000_保留2000review_flag=0.csv")
ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")


def open_csv(path: Path):
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            handle = path.open("r", encoding=encoding, newline="")
            sample = handle.read(4096)
            handle.seek(0)
            sample.encode(encoding)
            sample.decode(encoding) if isinstance(sample, bytes) else sample
            return handle, encoding
        except UnicodeDecodeError as exc:
            last_error = exc
        except Exception:
            raise
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"cannot decode {path}: {last_error}")


def read_header_and_count(path: Path) -> tuple[list[str], int, str]:
    with open_csv(path)[0] as handle:
        encoding = handle.encoding
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"missing header: {path}")
        count = sum(1 for _ in reader)
    return list(reader.fieldnames), count, encoding


def validate_inputs() -> tuple[list[str], list[tuple[Path, int, str]], list[tuple[Path, list[str]]]]:
    missing = [path for path in INPUT_FILES if not path.exists()]
    if missing:
        missing_text = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"missing input files:\n{missing_text}")

    union_header: list[str] = []
    missing_by_file: list[tuple[Path, list[str]]] = []
    stats: list[tuple[Path, int, str]] = []
    headers_by_file: list[tuple[Path, list[str]]] = []
    for path in INPUT_FILES:
        header, row_count, encoding = read_header_and_count(path)
        headers_by_file.append((path, header))
        for col in header:
            if col not in union_header:
                union_header.append(col)
        stats.append((path, row_count, encoding))

    if not union_header:
        raise ValueError("no input files")
    for path, header in headers_by_file:
        missing = [col for col in union_header if col not in header]
        if missing:
            missing_by_file.append((path, missing))
    return union_header, stats, missing_by_file


def merge_csvs() -> None:
    header, stats, missing_by_file = validate_inputs()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as output_handle:
        writer = csv.DictWriter(output_handle, fieldnames=header, extrasaction="raise")
        writer.writeheader()
        for path in INPUT_FILES:
            with open_csv(path)[0] as input_handle:
                reader = csv.DictReader(input_handle)
                for row in reader:
                    for col in header:
                        row.setdefault(col, "")
                    writer.writerow(row)

    _, output_count, output_encoding = read_header_and_count(OUTPUT_FILE)
    expected_count = sum(row_count for _, row_count, _ in stats)
    if output_count != expected_count:
        raise ValueError(f"output row count mismatch: expected {expected_count}, got {output_count}")

    print("MERGED")
    print(f"output={OUTPUT_FILE}")
    print(f"output_encoding={output_encoding}")
    print(f"rows={output_count}")
    print(f"columns={len(header)}")
    if missing_by_file:
        print("header_mode=union_missing_values_filled_blank")
    print("inputs:")
    for path, row_count, encoding in stats:
        print(f"{path.name}\trows={row_count}\tencoding={encoding}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    header, stats, missing_by_file = validate_inputs()
    print("VALID")
    print(f"columns={len(header)}")
    print(f"expected_rows={sum(row_count for _, row_count, _ in stats)}")
    if missing_by_file:
        print("header_mode=union_missing_values_filled_blank")
        print("missing_columns:")
        for path, missing in missing_by_file:
            print(f"{path.name}\tmissing={','.join(missing)}")
    print("inputs:")
    for path, row_count, encoding in stats:
        print(f"{path.name}\trows={row_count}\tencoding={encoding}")
    if not args.validate_only:
        merge_csvs()


if __name__ == "__main__":
    main()
