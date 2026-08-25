import argparse
import csv
import math
from pathlib import Path

import duckdb


UTF8_BOM = b"\xef\xbb\xbf"
DEFAULT_INPUT = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据\advisor_recall_weighted_pool_sample_2014_2026.csv"
)
DEFAULT_OUTPUT = DEFAULT_INPUT.with_name(
    "advisor_recall_weighted_pool_sample_2014_2026_5000.csv"
)
DEFAULT_SAMPLE_SIZE = 5000
DEFAULT_SEED = 20260612
POOL_COLUMN = "sample_pool"


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def largest_remainder(total: int, weights: dict[str, int]) -> dict[str, int]:
    if total < 0:
        raise ValueError("total must be non-negative")
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        raise ValueError("weights must sum to a positive value")

    raw = {key: total * weight / weight_sum for key, weight in weights.items()}
    quotas = {key: math.floor(value) for key, value in raw.items()}
    remainder = total - sum(quotas.values())

    order = sorted(weights, key=lambda key: (raw[key] - quotas[key], weights[key], key), reverse=True)
    for key in order[:remainder]:
        quotas[key] += 1
    return quotas


def allocate_with_caps(total: int, counts: dict[str, int]) -> dict[str, int]:
    if total > sum(counts.values()):
        raise ValueError(f"sample size {total} exceeds available rows {sum(counts.values())}")
    return largest_remainder(total, counts)


def ensure_utf8_sig(path: Path) -> None:
    content = path.read_bytes()
    if not content.startswith(UTF8_BOM):
        path.write_bytes(UTF8_BOM + content)


def create_source_table(con: duckdb.DuckDBPyConnection, input_path: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    input_sql = sql_literal(str(input_path))
    con.execute("DROP TABLE IF EXISTS source_rows")
    con.execute(
        f"""
        CREATE TEMP TABLE source_rows AS
        SELECT
            row_number() OVER () AS __row_id,
            *
        FROM read_csv_auto(
            {input_sql},
            header = true,
            all_varchar = true,
            ignore_errors = true,
            union_by_name = true,
            encoding = 'utf-8'
        )
        """
    )

    columns = {row[1] for row in con.execute("PRAGMA table_info('source_rows')").fetchall()}
    if POOL_COLUMN not in columns:
        raise ValueError(f"missing required column: {POOL_COLUMN}")


def fetch_pool_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    pool_col = sql_identifier(POOL_COLUMN)
    rows = con.execute(
        f"""
        SELECT lower(trim({pool_col})) AS pool, count(*) AS n
        FROM source_rows
        WHERE nullif(trim({pool_col}), '') IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()

    counts = {str(pool): int(n) for pool, n in rows}
    if not counts:
        raise ValueError(f"no non-empty {POOL_COLUMN} values found")
    return counts


def create_quota_table(con: duckdb.DuckDBPyConnection, quotas: dict[str, int]) -> None:
    con.execute("DROP TABLE IF EXISTS quota")
    con.execute("CREATE TEMP TABLE quota(pool VARCHAR, quota INTEGER)")
    con.executemany("INSERT INTO quota VALUES (?, ?)", sorted(quotas.items()))


def write_quota_csv(output_path: Path, counts: dict[str, int], quotas: dict[str, int]) -> Path:
    quota_path = output_path.with_name(output_path.stem + "_quota.csv")
    with quota_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_pool", "source_rows", "sample_quota"])
        for pool in sorted(counts):
            writer.writerow([pool, counts[pool], quotas.get(pool, 0)])
        writer.writerow(["TOTAL", sum(counts.values()), sum(quotas.values())])
    return quota_path


def export_sample(con: duckdb.DuckDBPyConnection, output_path: Path, seed: int) -> int:
    output_sql = sql_literal(str(output_path))
    pool_col = sql_identifier(POOL_COLUMN)
    con.execute(
        f"""
        COPY (
            WITH ranked AS (
                SELECT
                    s.*,
                    q.quota AS __quota,
                    row_number() OVER (
                        PARTITION BY lower(trim(s.{POOL_COLUMN}))
                        ORDER BY hash(cast({seed} AS VARCHAR) || '|' || cast(s.__row_id AS VARCHAR))
                    ) AS __rn
                FROM source_rows AS s
                INNER JOIN quota AS q
                    ON lower(trim(s.{pool_col})) = q.pool
            )
            SELECT * EXCLUDE (__row_id, __quota, __rn)
            FROM ranked
            WHERE __rn <= __quota
            ORDER BY lower(trim({pool_col})), __rn
        )
        TO {output_sql}
        WITH (HEADER true, DELIMITER ',')
        """
    )
    ensure_utf8_sig(output_path)
    return int(
        con.execute(
            "SELECT count(*) FROM read_csv_auto(?, header=true, all_varchar=true, ignore_errors=true)",
            [str(output_path)],
        ).fetchone()[0]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample rows from one CSV by preserving sample_pool proportions with DuckDB."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--write-quota", action="store_true")
    parser.add_argument("--validate-only", action="store_true", help="Print counts and quotas without writing output.")
    args = parser.parse_args()

    if args.sample_size <= 0:
        raise ValueError("--sample-size must be positive")

    con = duckdb.connect()
    create_source_table(con, args.input)
    counts = fetch_pool_counts(con)
    quotas = allocate_with_caps(args.sample_size, counts)

    print("source rows: " + str(sum(counts.values())))
    print("pool counts: " + ", ".join(f"{pool}={counts[pool]}" for pool in sorted(counts)))
    print("sample quotas: " + ", ".join(f"{pool}={quotas[pool]}" for pool in sorted(quotas)))

    if args.validate_only:
        return

    create_quota_table(con, quotas)
    sampled_rows = export_sample(con, args.output, args.seed)

    print(f"sampled rows: {sampled_rows}")
    print(f"output: {args.output}")
    if args.write_quota:
        quota_path = write_quota_csv(args.output, counts, quotas)
        print(f"quota: {quota_path}")

    if sampled_rows != args.sample_size:
        raise RuntimeError(f"sampled row count {sampled_rows} != target {args.sample_size}")


if __name__ == "__main__":
    main()
