from __future__ import annotations

import argparse
import csv
from pathlib import Path

import duckdb

#字段精简

DEFAULT_SOURCE_PATH = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据\advisor_recall_weighted_pool_sample_2014_2026_拓展岗位召回命中_每标签100.csv"
)
DEFAULT_OUTPUT_PATH = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\标注数据\人工标注600种子.csv"
)
OUTPUT_COLUMNS = [
    "id",
    "企业名称",
    "上市公司行业",
    "招聘岗位",
    "职位描述",
    "sample_pool",
    "拓展召回标签",
    "拓展召回命中词",
    "抽样标签",
]


def sql_literal(path: Path) -> str:
    return str(path).replace("'", "''")


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def export_selected_columns(source_path: Path, output_path: Path) -> dict[str, object]:
    if not source_path.exists():
        raise FileNotFoundError(f"Source CSV not found: {source_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    source_sql = f"""
        read_csv_auto(
            '{sql_literal(source_path)}',
            header=true,
            all_varchar=true,
            ignore_errors=true,
            union_by_name=true,
            encoding='utf-8'
        )
    """
    columns = [row[0] for row in con.sql(f"describe select * from {source_sql}").fetchall()]
    missing = [column for column in OUTPUT_COLUMNS if column not in columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    select_list = ", ".join(quote_ident(column) for column in OUTPUT_COLUMNS)
    con.sql(
        f"""
        copy (
            select {select_list}
            from {source_sql}
        )
        to '{sql_literal(output_path)}'
        (header, delimiter ',', quote '"', escape '"')
        """
    )
    source_rows = con.sql(f"select count(*) from {source_sql}").fetchone()[0]
    con.close()

    ensure_utf8_bom(output_path)
    return validate_output(source_rows, output_path)


def ensure_utf8_bom(path: Path) -> None:
    data = path.read_bytes()
    if not data.startswith(b"\xef\xbb\xbf"):
        path.write_bytes(b"\xef\xbb\xbf" + data)


def validate_output(source_rows: int, output_path: Path) -> dict[str, object]:
    with output_path.open("rb") as handle:
        has_bom = handle.read(3) == b"\xef\xbb\xbf"

    output_rows = 0
    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        output_fields = reader.fieldnames or []
        fields_ok = output_fields == OUTPUT_COLUMNS
        for _ in reader:
            output_rows += 1

    return {
        "source_rows": int(source_rows),
        "output_rows": output_rows,
        "fields_ok": fields_ok,
        "output_has_bom": has_bom,
        "output_columns": output_fields,
        "output_path": str(output_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export selected annotation seed columns with DuckDB.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_PATH, help="Input CSV path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output CSV path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = export_selected_columns(args.source, args.output)
    for key, value in summary.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
