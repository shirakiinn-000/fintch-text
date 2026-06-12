import argparse
from pathlib import Path

import duckdb

# 从 non_p7 合并文件中按 sample_pool 每池抽 100 条。

DEFAULT_INPUT = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据\advisor_recall_labeled_2014_2026_non_p7.csv"
)
DEFAULT_OUTPUT = DEFAULT_INPUT.with_name(DEFAULT_INPUT.stem + "_each_pool_100.csv")
POOL_COLUMN = "sample_pool"
DEFAULT_SAMPLE_PER_POOL = 100
DEFAULT_SEED = 20260611
UTF8_BOM = b"\xef\xbb\xbf"


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def path_sql(path: Path) -> str:
    return sql_literal(str(path).replace("\\", "/"))


def ensure_utf8_sig(path: Path) -> None:
    content = path.read_bytes()
    if not content.startswith(UTF8_BOM):
        path.write_bytes(UTF8_BOM + content)


def create_source_view(con: duckdb.DuckDBPyConnection, input_path: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    con.execute("DROP VIEW IF EXISTS source_rows")
    con.execute(
        f"""
        CREATE TEMP VIEW source_rows AS
        SELECT *
        FROM read_csv_auto(
            {path_sql(input_path)},
            header = true,
            all_varchar = true,
            ignore_errors = true,
            encoding = 'utf-8'
        )
        """
    )


def validate_pool_counts(con: duckdb.DuckDBPyConnection, sample_per_pool: int) -> list[str]:
    columns = [row[1] for row in con.execute("PRAGMA table_info('source_rows')").fetchall()]
    if POOL_COLUMN not in columns:
        raise ValueError(f"Missing required column: {POOL_COLUMN}")

    counts = con.execute(
        f"""
        SELECT lower(trim({POOL_COLUMN})) AS pool, count(*) AS n
        FROM source_rows
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()
    short_pools = [(pool, n) for pool, n in counts if pool and int(n) < sample_per_pool]
    if short_pools:
        detail = ", ".join(f"{pool}:{n}" for pool, n in short_pools)
        raise ValueError(f"Some pools have fewer than {sample_per_pool} rows: {detail}")

    return [str(pool) for pool, n in counts if pool]


def export_sample(con: duckdb.DuckDBPyConnection, output: Path, sample_per_pool: int, seed: int) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    output_sql = path_sql(output)
    con.execute(
        f"""
        COPY (
            WITH ranked AS (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY lower(trim({POOL_COLUMN}))
                        ORDER BY hash(
                            cast({int(seed)} AS VARCHAR) || '|' ||
                            coalesce(source_year, '') || '|' ||
                            coalesce(source_file, '') || '|' ||
                            coalesce(企业名称, '') || '|' ||
                            coalesce(招聘岗位, '') || '|' ||
                            coalesce(职位描述, '')
                        )
                    ) AS _pool_sample_rank
                FROM source_rows
                WHERE coalesce(lower(trim({POOL_COLUMN})), '') <> ''
            )
            SELECT *
            FROM ranked
            WHERE _pool_sample_rank <= {int(sample_per_pool)}
            ORDER BY lower(trim({POOL_COLUMN})), _pool_sample_rank
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


def print_output_counts(con: duckdb.DuckDBPyConnection, output: Path) -> None:
    rows = con.execute(
        f"""
        SELECT lower(trim({POOL_COLUMN})) AS pool, count(*) AS n
        FROM read_csv_auto(
            {path_sql(output)},
            header = true,
            all_varchar = true,
            ignore_errors = true,
            encoding = 'utf-8'
        )
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()
    print("OUTPUT_POOL_COUNTS=" + ", ".join(f"{pool}:{n}" for pool, n in rows))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample 100 rows from each sample_pool in the non_p7 CSV.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-per-pool", type=int, default=DEFAULT_SAMPLE_PER_POOL)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    con = duckdb.connect()
    create_source_view(con, args.input)
    pools = validate_pool_counts(con, args.sample_per_pool)
    output_rows = export_sample(con, args.output, args.sample_per_pool, args.seed)
    expected_rows = len(pools) * args.sample_per_pool

    print(f"INPUT={args.input}")
    print(f"OUTPUT={args.output}")
    print(f"POOLS={','.join(pools)}")
    print(f"SAMPLE_PER_POOL={args.sample_per_pool}")
    print(f"ROWS_OUT={output_rows}")
    print_output_counts(con, args.output)
    if output_rows != expected_rows:
        raise RuntimeError(f"Output rows {output_rows} != expected rows {expected_rows}")


if __name__ == "__main__":
    main()
