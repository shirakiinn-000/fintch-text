from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path

import duckdb

#从上市公司岗位中按 dict中的 投顾召回词.txt 直接召回约5w岗位

ROOT = Path(__file__).resolve().parent
DICT_PATH = ROOT / "dict" / "投顾召回词.txt"
DATA_DIR = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\上市公司招聘数据")
OUTPUT_CSV = DATA_DIR / "投顾召回岗位.csv"

JOB_COLUMN = "招聘岗位"
DESCRIPTION_COLUMN = "职位描述"
EXTRA_COLUMNS = ["来源文件", "命中字段", "命中词"]
YEARS = range(2014, 2027)
INPUT_TEMPLATE = "上市公司招聘数据{year}.csv"
READ_CSV = (
    "read_csv_auto(?, header=true, all_varchar=true, ignore_errors=true, "
    "union_by_name=true, encoding='utf-8')"
)


@dataclass
class FileStats:
    source_file: str
    rows_scanned: int
    matched_rows: int


def normalize_for_match(value: object) -> str:
    return "" if value is None else str(value).lower()


def read_keywords(path: Path) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            keyword = line.strip()
            if keyword and keyword not in seen:
                keywords.append(keyword)
                seen.add(keyword)
    if not keywords:
        raise ValueError(f"No keywords found: {path}")
    return keywords


def keyword_params(keywords: list[str]) -> list[str]:
    params: list[str] = []
    for keyword in keywords:
        normalized = keyword.lower()
        params.extend([normalized, normalized])
    return params


def build_match_where(keywords: list[str]) -> str:
    clauses = []
    for _ in keywords:
        clauses.append(
            f"contains(lower(coalesce({quote_ident(JOB_COLUMN)}, '')), ?) "
            f"or contains(lower(coalesce({quote_ident(DESCRIPTION_COLUMN)}, '')), ?)"
        )
    return " or ".join(f"({clause})" for clause in clauses)


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def get_header(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                header = next(csv.reader(f))
            return [name for name in header if name]
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", b"", 0, 1, f"Cannot decode header: {path}")


def validate_header(path: Path, columns: list[str]) -> None:
    missing = [col for col in (JOB_COLUMN, DESCRIPTION_COLUMN) if col not in columns]
    if missing:
        raise ValueError(f"{path.name} missing required columns: {missing}")


def official_input_files(data_dir: Path, start_year: int, end_year: int) -> list[Path]:
    if start_year < min(YEARS) or end_year > max(YEARS) or start_year > end_year:
        raise ValueError(f"Year range must be within {min(YEARS)}-{max(YEARS)}.")
    files = [data_dir / INPUT_TEMPLATE.format(year=year) for year in range(start_year, end_year + 1)]
    missing = [str(path) for path in files if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing yearly CSV files: " + "; ".join(missing))
    return files


def row_match_metadata(row: dict[str, str], keywords: list[str]) -> tuple[str, str]:
    job_text = normalize_for_match(row.get(JOB_COLUMN))
    desc_text = normalize_for_match(row.get(DESCRIPTION_COLUMN))
    hit_fields: list[str] = []
    hit_terms: list[str] = []

    for keyword in keywords:
        normalized = keyword.lower()
        in_job = normalized in job_text
        in_desc = normalized in desc_text
        if in_job or in_desc:
            hit_terms.append(keyword)
        if in_job and JOB_COLUMN not in hit_fields:
            hit_fields.append(JOB_COLUMN)
        if in_desc and DESCRIPTION_COLUMN not in hit_fields:
            hit_fields.append(DESCRIPTION_COLUMN)

    return ";".join(hit_fields), ";".join(hit_terms)

def scan_file(
    con: duckdb.DuckDBPyConnection,
    input_path: Path,
    fieldnames: list[str],
    keywords: list[str],
    writer: csv.DictWriter,
    batch_size: int,
) -> FileStats:
    validate_header(input_path, fieldnames)
    path_arg = str(input_path)
    selected_columns = ", ".join(quote_ident(col) for col in fieldnames)
    where_sql = build_match_where(keywords)
    params = keyword_params(keywords)

    rows_scanned = con.execute(f"select count(*) from {READ_CSV}", [path_arg]).fetchone()[0]
    query = f"select {selected_columns} from {READ_CSV} where {where_sql}"
    cursor = con.execute(query, [path_arg, *params])

    matched_rows = 0
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        for values in rows:
            row = {field: "" if value is None else str(value) for field, value in zip(fieldnames, values)}
            hit_fields, hit_terms = row_match_metadata(row, keywords)
            if not hit_terms:
                raise ValueError(f"Internal match error: {input_path.name} row has empty hit terms")
            row["来源文件"] = input_path.name
            row["命中字段"] = hit_fields
            row["命中词"] = hit_terms
            writer.writerow(row)
            matched_rows += 1

    return FileStats(input_path.name, int(rows_scanned), matched_rows)


def recall_jobs(
    dict_path: Path,
    data_dir: Path,
    output_path: Path,
    batch_size: int = 10000,
    start_year: int = min(YEARS),
    end_year: int = max(YEARS),
) -> list[FileStats]:
    keywords = read_keywords(dict_path)
    input_files = official_input_files(data_dir, start_year, end_year)
    fieldnames = get_header(input_files[0])
    validate_header(input_files[0], fieldnames)
    output_fields = fieldnames + EXTRA_COLUMNS

    output_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=":memory:")
    con.execute("set preserve_insertion_order=false")

    stats: list[FileStats] = []
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        for input_path in input_files:
            current_header = get_header(input_path)
            validate_header(input_path, current_header)
            missing_from_base = [col for col in fieldnames if col not in current_header]
            if missing_from_base:
                raise ValueError(f"{input_path.name} missing base columns: {missing_from_base}")
            file_stats = scan_file(con, input_path, fieldnames, keywords, writer, batch_size)
            stats.append(file_stats)
            print(
                f"{file_stats.source_file}: "
                f"rows_scanned={file_stats.rows_scanned}, matched_rows={file_stats.matched_rows}"
            )

    total_rows = sum(item.rows_scanned for item in stats)
    total_matches = sum(item.matched_rows for item in stats)
    print(f"keywords={len(keywords)}")
    print(f"total_rows_scanned={total_rows}")
    print(f"total_matched_rows={total_matches}")
    print(f"output={output_path}")
    return stats


def validate_output(output_path: Path, dict_path: Path, sample_size: int = 20) -> None:
    keywords = read_keywords(dict_path)
    keyword_set = set(keywords)
    rows_seen = 0
    bad_hit_terms = 0
    sampled: list[dict[str, str]] = []
    rng = random.Random(20260610)

    with output_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Output CSV has no header: {output_path}")
        empty_columns = [col for col in reader.fieldnames if not col]
        if empty_columns:
            raise ValueError(f"Output CSV contains empty column names: {empty_columns}")
        for col in [JOB_COLUMN, DESCRIPTION_COLUMN, *EXTRA_COLUMNS]:
            if col not in reader.fieldnames:
                raise ValueError(f"Output CSV missing required column: {col}")

        for row in reader:
            rows_seen += 1
            hit_terms = [term for term in (row.get("命中词") or "").split(";") if term]
            if not hit_terms or any(term not in keyword_set for term in hit_terms):
                bad_hit_terms += 1
            if len(sampled) < sample_size:
                sampled.append(row)
            else:
                replacement = rng.randint(1, rows_seen)
                if replacement <= sample_size:
                    sampled[replacement - 1] = row

    if rows_seen <= 0:
        raise ValueError("Output CSV has zero data rows.")
    if bad_hit_terms:
        raise ValueError(f"Rows with invalid or empty hit terms: {bad_hit_terms}")

    bad_samples = 0
    for row in sampled:
        combined = normalize_for_match(row.get(JOB_COLUMN)) + "\n" + normalize_for_match(row.get(DESCRIPTION_COLUMN))
        hit_terms = [term for term in (row.get("命中词") or "").split(";") if term]
        if not any(term.lower() in combined for term in hit_terms):
            bad_samples += 1
    if bad_samples:
        raise ValueError(f"Sample validation failed rows: {bad_samples}")

    print(f"validated_output={output_path}")
    print(f"validated_rows={rows_seen}")
    print(f"sample_checked={len(sampled)}")
    print("validation=PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recall investment advisor jobs from yearly hiring CSV files with DuckDB."
    )
    parser.add_argument("--dict", type=Path, default=DICT_PATH, help="Keyword dictionary path.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Directory containing yearly CSV files.")
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV, help="Output CSV path.")
    parser.add_argument("--batch-size", type=int, default=10000, help="DuckDB fetch batch size.")
    parser.add_argument("--start-year", type=int, default=min(YEARS), help="First yearly CSV to process.")
    parser.add_argument("--end-year", type=int, default=max(YEARS), help="Last yearly CSV to process.")
    parser.add_argument("--validate-only", action="store_true", help="Only validate an existing output CSV.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.validate_only:
        validate_output(args.output, args.dict)
    else:
        recall_jobs(
            args.dict,
            args.data_dir,
            args.output,
            batch_size=args.batch_size,
            start_year=args.start_year,
            end_year=args.end_year,
        )


if __name__ == "__main__":
    main()
