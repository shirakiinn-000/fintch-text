import argparse
from pathlib import Path

import duckdb

# 召回所有除 p7 以外的样本，合并输出为一个 CSV。

DEFAULT_INPUT_DIR = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据")
DEFAULT_OUTPUT = DEFAULT_INPUT_DIR / "advisor_recall_labeled_2014_2026_non_p7.csv"
YEARS = list(range(2014, 2027))
POOL_COLUMN = "sample_pool"
UTF8_BOM = b"\xef\xbb\xbf"


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def make_file_list(input_dir: Path, years: list[int]) -> list[Path]:
    paths = [input_dir / f"advisor_recall_labeled_{year}.csv" for year in years]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing input CSV(s): " + "; ".join(missing))
    return paths


def duckdb_file_array(paths: list[Path]) -> str:
    return "[" + ", ".join(sql_literal(str(path).replace("\\", "/")) for path in paths) + "]"


def path_sql(path: Path) -> str:
    return sql_literal(str(path).replace("\\", "/"))


def source_sql(paths: list[Path]) -> str:
    return f"""
        read_csv_auto(
            {duckdb_file_array(paths)},
            header = true,
            all_varchar = true,
            ignore_errors = true,
            union_by_name = true,
            filename = true,
            encoding = 'utf-8'
        )
    """


def create_source_view(con: duckdb.DuckDBPyConnection, paths: list[Path]) -> None:
    con.execute("DROP VIEW IF EXISTS source_rows")
    con.execute(
        f"""
        CREATE TEMP VIEW source_rows AS
        SELECT
            regexp_extract(filename, '([0-9]{{4}})\\.csv$', 1) AS source_year,
            filename AS source_file,
            *
        FROM {source_sql(paths)}
        """
    )


def validate_header(con: duckdb.DuckDBPyConnection) -> None:
    columns = [row[1] for row in con.execute("PRAGMA table_info('source_rows')").fetchall()]
    if POOL_COLUMN not in columns:
        raise ValueError(f"Missing required column: {POOL_COLUMN}")


def export_non_p7(con: duckdb.DuckDBPyConnection, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    output_sql = path_sql(output)
    con.execute(
        f"""
        COPY (
            SELECT *
            FROM source_rows
            WHERE coalesce(lower(trim({POOL_COLUMN})), '') <> 'p7'
            ORDER BY source_year, lower(trim({POOL_COLUMN}))
        )
        TO {output_sql}
        WITH (HEADER true, DELIMITER ',')
        """
    )
    ensure_utf8_sig(output)
    return int(
        con.execute(
            f"""
            SELECT count(*)
            FROM read_csv_auto(
                {output_sql},
                header = true,
                all_varchar = true,
                ignore_errors = true,
                encoding = 'utf-8'
            )
            """
        ).fetchone()[0]
    )


def ensure_utf8_sig(path: Path) -> None:
    content = path.read_bytes()
    if not content.startswith(UTF8_BOM):
        path.write_bytes(UTF8_BOM + content)


def print_counts(con: duckdb.DuckDBPyConnection, output_rows: int) -> None:
    source_counts = con.execute(
        f"""
        SELECT coalesce(lower(trim({POOL_COLUMN})), '') AS pool, count(*) AS n
        FROM source_rows
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()
    non_p7_counts = con.execute(
        f"""
        SELECT coalesce(lower(trim({POOL_COLUMN})), '') AS pool, count(*) AS n
        FROM source_rows
        WHERE coalesce(lower(trim({POOL_COLUMN})), '') <> 'p7'
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()

    print("SOURCE_POOL_COUNTS=" + ", ".join(f"{pool or '<blank>'}:{n}" for pool, n in source_counts))
    print("NON_P7_POOL_COUNTS=" + ", ".join(f"{pool or '<blank>'}:{n}" for pool, n in non_p7_counts))
    print(f"ROWS_OUT={output_rows}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export all advisor recall labeled samples except sample_pool p7."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--years", nargs="+", type=int, default=YEARS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = make_file_list(args.input_dir, args.years)

    con = duckdb.connect()
    create_source_view(con, paths)
    validate_header(con)
    output_rows = export_non_p7(con, args.output)

    print(f"INPUT_DIR={args.input_dir}")
    print(f"OUTPUT={args.output}")
    print(f"YEARS={','.join(str(year) for year in args.years)}")
    print_counts(con, output_rows)


if __name__ == "__main__":
    main()
