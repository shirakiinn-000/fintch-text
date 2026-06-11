import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import duckdb

# 从8个池按目标比例抽样，池内按年份加权平均分配

UTF8_BOM = b"\xef\xbb\xbf"
DEFAULT_INPUT_DIR = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据")
DEFAULT_OUTPUT = DEFAULT_INPUT_DIR / "advisor_recall_weighted_pool_sample_2014_2026.csv"
YEARS = list(range(2014, 2027))
POOLS = [f"p{i}" for i in range(1, 9)]
DEFAULT_SAMPLE_SIZE = 10000

POOL_SAMPLE_SHARES = {
    "p1": 24,
    "p2": 14,
    "p3": 15,
    "p4": 8,
    "p5": 16,
    "p6": 8,
    "p7": 10,
    "p8": 5,
}


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def make_file_list(input_dir: Path) -> list[Path]:
    paths = [input_dir / f"advisor_recall_labeled_{year}.csv" for year in YEARS]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing input CSV(s): " + "; ".join(missing))
    return paths


def duckdb_file_array(paths: list[Path]) -> str:
    return "[" + ", ".join(sql_literal(str(path)) for path in paths) + "]"


def largest_remainder(total: int, weights: dict[str, float]) -> dict[str, int]:
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


def allocate_with_caps(total: int, weights: dict[str, int], caps: dict[str, int]) -> dict[str, int]:
    remaining_total = total
    remaining_weights = {key: weight for key, weight in weights.items() if caps.get(key, 0) > 0}
    allocation = {key: 0 for key in weights}

    while remaining_total > 0 and remaining_weights:
        proposed = largest_remainder(remaining_total, remaining_weights)
        overflow = 0
        next_weights = {}

        for key, value in proposed.items():
            available = caps.get(key, 0) - allocation[key]
            take = min(value, available)
            allocation[key] += take
            overflow += value - take
            if allocation[key] < caps.get(key, 0):
                next_weights[key] = remaining_weights[key]

        if overflow == remaining_total:
            break
        remaining_total = overflow
        remaining_weights = next_weights

    return allocation


def create_source_table(con: duckdb.DuckDBPyConnection, paths: list[Path]) -> None:
    con.execute("DROP TABLE IF EXISTS source_rows")
    con.execute(
        f"""
        CREATE TEMP TABLE source_rows AS
        WITH raw AS (
            SELECT *
            FROM read_csv_auto(
                {duckdb_file_array(paths)},
                header = true,
                all_varchar = true,
                ignore_errors = true,
                union_by_name = true,
                filename = true,
                encoding = 'utf-8'
            )
        )
        SELECT
            row_number() OVER (PARTITION BY filename ORDER BY filename) AS _source_row_number,
            regexp_extract(filename, '([0-9]{{4}})\\.csv$', 1) AS _source_year,
            filename AS _source_file,
            *
        FROM raw
        """
    )


def fetch_counts(con: duckdb.DuckDBPyConnection) -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    rows = con.execute(
        """
        SELECT _source_year, lower(trim(sample_pool)) AS pool, count(*) AS n
        FROM source_rows
        GROUP BY 1, 2
        """
    ).fetchall()

    year_totals: dict[str, int] = defaultdict(int)
    pool_year_counts: dict[tuple[str, str], int] = {}
    for year, pool, n in rows:
        year = str(year)
        pool = str(pool)
        n = int(n)
        year_totals[year] += n
        pool_year_counts[(pool, year)] = n

    return dict(year_totals), pool_year_counts


def build_quotas(
    year_totals: dict[str, int],
    pool_year_counts: dict[tuple[str, str], int],
    sample_size: int,
) -> tuple[int, dict[tuple[str, str], int], dict[str, int]]:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")

    final_total = sample_size
    pool_targets = largest_remainder(final_total, POOL_SAMPLE_SHARES)

    year_weights = {str(year): year_totals[str(year)] for year in YEARS}
    quotas: dict[tuple[str, str], int] = {}

    for pool in POOLS:
        caps = {str(year): pool_year_counts.get((pool, str(year)), 0) for year in YEARS}
        year_allocation = allocate_with_caps(pool_targets[pool], year_weights, caps)
        for year in YEARS:
            year_key = str(year)
            quotas[(pool, year_key)] = year_allocation.get(year_key, 0)

    return final_total, quotas, pool_targets


def write_quota_table(path: Path, quotas: dict[tuple[str, str], int], pool_targets: dict[str, int]) -> None:
    quota_path = path.with_name(path.stem + "_quota.csv")
    with quota_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["year", *POOLS, "year_total_quota"])
        for year in YEARS:
            values = [quotas.get((pool, str(year)), 0) for pool in POOLS]
            writer.writerow([year, *values, sum(values)])
        writer.writerow(["TOTAL", *[pool_targets[pool] for pool in POOLS], sum(pool_targets.values())])


def create_quota_table(con: duckdb.DuckDBPyConnection, quotas: dict[tuple[str, str], int]) -> None:
    con.execute("DROP TABLE IF EXISTS quota")
    con.execute("CREATE TEMP TABLE quota(pool VARCHAR, source_year VARCHAR, quota INTEGER)")
    rows = [(pool, year, quota) for (pool, year), quota in quotas.items() if quota > 0]
    con.executemany("INSERT INTO quota VALUES (?, ?, ?)", rows)


def ensure_utf8_sig(path: Path) -> None:
    content = path.read_bytes()
    if not content.startswith(UTF8_BOM):
        path.write_bytes(UTF8_BOM + content)


def export_sample(con: duckdb.DuckDBPyConnection, output: Path, seed: int) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    output_sql = sql_literal(str(output))

    con.execute(
        f"""
        COPY (
            WITH ranked AS (
                SELECT
                    s.*,
                    q.quota,
                    row_number() OVER (
                        PARTITION BY lower(trim(s.sample_pool)), s._source_year
                        ORDER BY hash(
                            cast({seed} AS VARCHAR) || '|' ||
                            s._source_file || '|' ||
                            cast(s._source_row_number AS VARCHAR)
                        )
                    ) AS rn
                FROM source_rows AS s
                INNER JOIN quota AS q
                    ON lower(trim(s.sample_pool)) = q.pool
                   AND s._source_year = q.source_year
            )
            SELECT *
            FROM ranked
            WHERE rn <= quota
            ORDER BY _source_year, lower(trim(sample_pool)), rn
        )
        TO {output_sql}
        WITH (HEADER true, DELIMITER ',')
        """
    )
    ensure_utf8_sig(output)

    return int(con.execute(f"SELECT count(*) FROM read_csv_auto({output_sql}, header=true, all_varchar=true)").fetchone()[0])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample Advisor recall rows from p1-p8 pools with DuckDB and year-weighted quotas."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE, help="Total sample size.")
    parser.add_argument("--seed", type=int, default=20260524)
    parser.add_argument("--write-quota", action="store_true", help="Also write a quota CSV next to the sample output.")
    args = parser.parse_args()

    paths = make_file_list(args.input_dir)
    con = duckdb.connect()
    create_source_table(con, paths)
    year_totals, pool_year_counts = fetch_counts(con)
    final_total, quotas, pool_targets = build_quotas(year_totals, pool_year_counts, args.sample_size)
    create_quota_table(con, quotas)
    sampled_rows = export_sample(con, args.output, args.seed)

    if args.write_quota:
        write_quota_table(args.output, quotas, pool_targets)

    print(f"target total sample size: {final_total}")
    print(f"sampled rows: {sampled_rows}")
    print("pool targets: " + ", ".join(f"{pool}={pool_targets[pool]}" for pool in POOLS))
    print(f"output: {args.output}")
    if sampled_rows != final_total:
        raise RuntimeError(f"Sampled row count {sampled_rows} != target {final_total}")


if __name__ == "__main__":
    main()
