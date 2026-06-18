from __future__ import annotations

import argparse
import csv
from pathlib import Path


INPUT_FILES = [
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part01.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part02.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part03.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part04.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part05.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part06.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part07.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part08.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part09.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part10.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part11.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part12.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part13.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part14.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part15.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part16.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part17.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part18.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part19.csv"),
    Path(r"E:\浏览器下载\人工标注1000种子_full_text_part20.csv"),
]

OUTPUT_FILE = Path(r"E:\浏览器下载\人工标注1000种子_full_text_ABC分类_合并.csv")
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
