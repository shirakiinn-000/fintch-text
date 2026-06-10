import argparse
import csv
import re
from collections import Counter
from pathlib import Path

import duckdb

# 按8个池召回投顾服务职能岗位

DEFAULT_INPUT_DIR = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\上市公司招聘数据")
DEFAULT_OUTPUT_DIR = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据")
DEFAULT_TERM_DIR = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\codex\fintech 文本提取\dict\召回词")
DEFAULT_YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
DEFAULT_DUTY_COL = "职位描述"
FETCH_SIZE = 50_000
TERM_SPLIT_PATTERN = re.compile(r"[、,，;；]+")

APPENDED_COLUMNS = [
    "advisor_recall_flag",
    "advisor_recall_level",
    "sample_pool",
    "sample_stratum",
    "review_priority",
    "match_a_terms",
    "match_b_terms",
    "match_c_left_terms",
    "match_c_right_terms",
    "match_d_terms",
    "match_e_terms",
    "c_bound_evidence",
]

TERM_FILES = {
    "A": "A.txt",
    "B": "B.txt",
    "C_LEFT": "C_left.txt",
    "C_RIGHT": "C_right.txt",
    "D": "D.txt",
    "E": "E.txt",
}

POOL_RULES = {
    ("A_high", False): ("p1", "s1_a_clean", "high"),
    ("A_high", True): ("p2", "s2_a_risk", "high"),
    ("B_broad", False): ("p3", "s3_b_clean", "medium"),
    ("B_broad", True): ("p4", "s4_b_risk", "low"),
    ("C_bound", False): ("p5", "s5_c_clean", "medium"),
    ("C_bound", True): ("p6", "s6_c_risk", "low"),
}

UNRECALLED_CLEAN = ("p7", "s7_unrecalled_random", "medium")
UNRECALLED_RISK = ("p8", "s8_unrecalled_risk", "medium")

ACTION_WORDS = [
    "负责",
    "主导",
    "参与",
    "推进",
    "推动",
    "协助",
    "支持",
    "配合",
    "组织",
    "开展",
    "实施",
    "执行",
    "完成",
    "落地",
    "了解",
    "识别",
    "收集",
    "挖掘",
    "分析",
    "评估",
    "测评",
    "判断",
    "诊断",
    "提供",
    "出具",
    "制定",
    "设计",
    "构建",
    "生成",
    "配置",
    "匹配",
    "推荐",
    "筛选",
    "遴选",
    "规划",
    "调整",
    "优化",
    "跟踪",
    "监控",
    "解释",
    "说明",
    "揭示",
    "沟通",
    "回访",
    "陪伴",
    "维护",
    "处理",
    "审核",
    "复核",
    "校验",
    "检查",
    "质检",
    "留痕",
    "披露",
    "管理",
    "监督",
    "调仓",
    "再平衡",
    "申购",
    "赎回",
    "转换",
    "办理",
    "核验",
    "建设",
    "建立",
    "搭建",
    "开发",
    "运营",
    "训练",
    "校准",
    "培训",
    "督导",
    "考核",
]

# C_left.txt 和 C_right.txt 应保存投顾任务链的原子词，建议一行一个词；
# read_terms() 也兼容同一行用 、 , ， ; ； 分隔多个词。

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Label yearly listed-company hiring CSVs with advisor recall pools."
    )
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--term-dir", type=Path, default=DEFAULT_TERM_DIR)
    parser.add_argument("--duty-col", default=DEFAULT_DUTY_COL)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row cap for focused validation runs. Omit for full output.",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def path_sql_literal(path: Path) -> str:
    return sql_literal(str(path).replace("\\", "/"))


def read_terms(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)

    terms: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(("：", ":")):
            continue
        for term in TERM_SPLIT_PATTERN.split(line):
            term = term.strip()
            if not term:
                continue
            key = term.casefold()
            if key in seen:
                continue
            seen.add(key)
            terms.append(term)

    if not terms:
        raise ValueError(f"No terms found in {path}")
    return terms


def load_term_sets(term_dir: Path) -> dict[str, list[str]]:
    return {name: read_terms(term_dir / file_name) for name, file_name in TERM_FILES.items()}


def validate_term_sets(term_sets: dict[str, list[str]]) -> None:
    required_names = {"A", "B", "C_LEFT", "C_RIGHT", "D", "E"}
    missing = sorted(name for name in required_names if not term_sets.get(name))
    if missing:
        raise ValueError(f"Missing or empty advisor term sets: {missing}")

    for name, terms in term_sets.items():
        for term in terms:
            if "+" in term or "/" in term:
                print(f"[warning] {name} term may be a chain expression, not an atomic term: {term}")
            if term.endswith(("：", ":")):
                print(f"[warning] {name} term looks like a heading: {term}")
            if name in {"B", "D", "E"} and TERM_SPLIT_PATTERN.search(term):
                print(f"[warning] {name} term still contains a delimiter after splitting: {term}")


def make_literal_pattern(terms: list[str]) -> re.Pattern[str]:
    escaped = [re.escape(term) for term in sorted(terms, key=len, reverse=True) if term]
    if not escaped:
        return re.compile(r"a^")
    return re.compile("|".join(escaped), flags=re.IGNORECASE)


def build_c_bound_pattern(left_terms: list[str], right_terms: list[str]) -> re.Pattern[str]:
    left_pattern = "|".join(re.escape(term) for term in sorted(left_terms, key=len, reverse=True) if term)
    right_pattern = "|".join(re.escape(term) for term in sorted(right_terms, key=len, reverse=True) if term)
    action_pattern = "|".join(re.escape(term) for term in ACTION_WORDS)

    if not left_pattern or not right_pattern:
        return re.compile(r"a^")

    return re.compile(
        rf"({action_pattern})[^。；;\n]{{0,50}}({left_pattern})[^。；;\n]{{0,80}}({right_pattern})",
        flags=re.IGNORECASE,
    )


def build_c_reverse_bound_pattern(left_terms: list[str], right_terms: list[str]) -> re.Pattern[str]:
    left_pattern = "|".join(re.escape(term) for term in sorted(left_terms, key=len, reverse=True) if term)
    right_pattern = "|".join(re.escape(term) for term in sorted(right_terms, key=len, reverse=True) if term)
    action_pattern = "|".join(re.escape(term) for term in ACTION_WORDS)

    if not left_pattern or not right_pattern:
        return re.compile(r"a^")

    return re.compile(
        rf"({action_pattern})[^。；;\n]{{0,50}}({right_pattern})[^。；;\n]{{0,80}}({left_pattern})",
        flags=re.IGNORECASE,
    )


def find_terms(text: str, terms: list[str]) -> list[str]:
    folded_text = text.casefold()
    hits = [term for term in terms if term.casefold() in folded_text]
    return sorted(set(hits), key=lambda value: (value.casefold(), value))


def find_c_bound(
    text: str,
    left_terms: list[str],
    right_terms: list[str],
    forward_pattern: re.Pattern[str],
    reverse_pattern: re.Pattern[str],
) -> tuple[list[str], list[str], list[str]]:
    snippets: list[str] = []
    left_hits: list[str] = []
    right_hits: list[str] = []

    for pattern in (forward_pattern, reverse_pattern):
        for match in pattern.finditer(text):
            snippet = match.group(0).strip()
            if snippet:
                snippets.append(snippet)
            matched_text = match.group(0)
            left_hits.extend(find_terms(matched_text, left_terms))
            right_hits.extend(find_terms(matched_text, right_terms))

    return (
        sorted(set(left_hits), key=lambda value: (value.casefold(), value)),
        sorted(set(right_hits), key=lambda value: (value.casefold(), value)),
        sorted(set(snippets)),
    )


def classify_text(
    text: str,
    term_sets: dict[str, list[str]],
    c_forward_pattern: re.Pattern[str],
    c_reverse_pattern: re.Pattern[str],
) -> dict[str, str]:
    a_hits = find_terms(text, term_sets["A"])
    b_hits = find_terms(text, term_sets["B"])
    c_left_hits, c_right_hits, c_snippets = find_c_bound(
        text,
        term_sets["C_LEFT"],
        term_sets["C_RIGHT"],
        c_forward_pattern,
        c_reverse_pattern,
    )
    d_hits = find_terms(text, term_sets["D"])
    e_hits = find_terms(text, term_sets["E"])

    if a_hits:
        recall_level = "A_high"
    elif b_hits:
        recall_level = "B_broad"
    elif c_left_hits and c_right_hits:
        recall_level = "C_bound"
    else:
        pool, sample_stratum, review_priority = UNRECALLED_RISK if e_hits else UNRECALLED_CLEAN
        return {
            "advisor_recall_flag": "0",
            "advisor_recall_level": "unrecalled",
            "sample_pool": pool,
            "sample_stratum": sample_stratum,
            "review_priority": review_priority,
            "match_a_terms": "",
            "match_b_terms": "",
            "match_c_left_terms": "",
            "match_c_right_terms": "",
            "match_d_terms": "",
            "match_e_terms": "；".join(e_hits),
            "c_bound_evidence": "",
        }

    pool, sample_stratum, review_priority = POOL_RULES[(recall_level, bool(d_hits))]

    return {
        "advisor_recall_flag": "1",
        "advisor_recall_level": recall_level,
        "sample_pool": pool,
        "sample_stratum": sample_stratum,
        "review_priority": review_priority,
        "match_a_terms": "；".join(a_hits),
        "match_b_terms": "；".join(b_hits),
        "match_c_left_terms": "；".join(c_left_hits),
        "match_c_right_terms": "；".join(c_right_hits),
        "match_d_terms": "；".join(d_hits),
        "match_e_terms": "",
        "c_bound_evidence": " || ".join(c_snippets[:5]),
    }


def source_sql(csv_path: Path) -> str:
    return f"""
        read_csv_auto(
            {path_sql_literal(csv_path)},
            header = true,
            all_varchar = true,
            ignore_errors = true,
            encoding = 'utf-8'
        )
    """


def get_header(con: duckdb.DuckDBPyConnection, csv_path: Path) -> list[str]:
    result = con.execute(f"SELECT * FROM {source_sql(csv_path)} LIMIT 0")
    return [column[0] for column in result.description]


def iter_source_rows(
    con: duckdb.DuckDBPyConnection,
    csv_path: Path,
    header: list[str],
    max_rows: int | None = None,
):
    source = source_sql(csv_path)
    total_rows = con.execute(f"SELECT count(*) FROM {source}").fetchone()[0]
    limit_clause = "" if max_rows is None else f" LIMIT {int(max_rows)}"

    cursor = con.execute(
        f"""
        SELECT *
        FROM {source}
        {limit_clause}
        """
    )

    while True:
        batch = cursor.fetchmany(FETCH_SIZE)
        if not batch:
            break
        for values in batch:
            row = {header[i]: ("" if value is None else str(value)) for i, value in enumerate(values)}
            yield total_rows, row


def output_path_for_year(output_dir: Path, year: int) -> Path:
    return output_dir / f"advisor_recall_labeled_{year}.csv"


def input_path_for_year(input_dir: Path, year: int) -> Path:
    return input_dir / f"上市公司招聘数据{year}.csv"


def validate_inputs(args: argparse.Namespace) -> None:
    if not args.input_dir.exists():
        raise FileNotFoundError(args.input_dir)
    if not args.term_dir.exists():
        raise FileNotFoundError(args.term_dir)
    if not args.output_dir.exists():
        raise FileNotFoundError(args.output_dir)

    for year in args.years:
        csv_path = input_path_for_year(args.input_dir, year)
        if not csv_path.exists():
            raise FileNotFoundError(csv_path)
        out_path = output_path_for_year(args.output_dir, year)
        if out_path.exists() and not args.overwrite:
            raise FileExistsError(f"{out_path} already exists. Use --overwrite to replace it.")


def validate_output(
    output_path: Path,
    expected_original_header: list[str],
) -> tuple[int, Counter, Counter, Counter]:
    if not output_path.exists():
        raise FileNotFoundError(output_path)

    level_counts: Counter = Counter()
    pool_counts: Counter = Counter()
    priority_counts: Counter = Counter()
    row_count = 0
    valid_pools = {f"p{i}" for i in range(1, 9)}
    valid_strata = {
        "p1": ("s1_a_clean", "high"),
        "p2": ("s2_a_risk", "high"),
        "p3": ("s3_b_clean", "medium"),
        "p4": ("s4_b_risk", "low"),
        "p5": ("s5_c_clean", "medium"),
        "p6": ("s6_c_risk", "low"),
        "p7": ("s7_unrecalled_random", "medium"),
        "p8": ("s8_unrecalled_risk", "medium"),
    }
    with output_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{output_path} has no header.")
        expected_header = expected_original_header + APPENDED_COLUMNS
        missing = [col for col in expected_header if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"{output_path} missing columns: {missing}")
        if reader.fieldnames != expected_header:
            raise ValueError(f"{output_path} header order does not match expected original columns plus appended columns.")

        for row in reader:
            row_count += 1
            recall_flag = row.get("advisor_recall_flag", "")
            level = row.get("advisor_recall_level", "")
            sample_pool = row.get("sample_pool", "")
            sample_stratum = row.get("sample_stratum", "")
            review_priority = row.get("review_priority", "")
            if recall_flag not in {"0", "1"}:
                raise ValueError(f"{output_path} contains unexpected advisor_recall_flag: {recall_flag}")
            if level not in {"A_high", "B_broad", "C_bound", "unrecalled"}:
                raise ValueError(f"{output_path} contains unexpected advisor_recall_level: {level}")
            if sample_pool not in valid_pools:
                raise ValueError(f"{output_path} contains unexpected sample_pool: {sample_pool}")
            expected_stratum, expected_priority = valid_strata[sample_pool]
            if sample_stratum != expected_stratum or review_priority != expected_priority:
                raise ValueError(
                    f"{output_path} contains inconsistent pool mapping: "
                    f"{sample_pool}, {sample_stratum}, {review_priority}"
                )
            if recall_flag == "0" and sample_pool not in {"p7", "p8"}:
                raise ValueError(f"{output_path} contains unrecalled row outside p7/p8.")
            if recall_flag == "1" and sample_pool in {"p7", "p8"}:
                raise ValueError(f"{output_path} contains recalled row inside p7/p8.")
            level_counts[level] += 1
            pool_counts[sample_pool] += 1
            priority_counts[review_priority] += 1

    return row_count, level_counts, pool_counts, priority_counts


def process_year(
    con: duckdb.DuckDBPyConnection,
    year: int,
    args: argparse.Namespace,
    term_sets: dict[str, list[str]],
    c_forward_pattern: re.Pattern[str],
    c_reverse_pattern: re.Pattern[str],
) -> None:
    csv_path = input_path_for_year(args.input_dir, year)
    out_path = output_path_for_year(args.output_dir, year)
    header = get_header(con, csv_path)
    if args.duty_col not in header:
        raise ValueError(f"{csv_path} missing duty column: {args.duty_col}")

    fieldnames = header + APPENDED_COLUMNS
    total_rows = 0
    written_rows = 0

    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        rows = iter_source_rows(con, csv_path, header, args.max_rows)
        for source_total, row in rows:
            total_rows = source_total
            classification = classify_text(
                row.get(args.duty_col, ""),
                term_sets,
                c_forward_pattern,
                c_reverse_pattern,
            )
            output_row = dict(row)
            output_row.update(classification)
            writer.writerow(output_row)
            written_rows += 1

    validated_rows, level_counts, pool_counts, priority_counts = validate_output(out_path, header)
    if validated_rows != written_rows:
        raise ValueError(f"{out_path} validation mismatch: wrote {written_rows}, read {validated_rows}")
    if args.max_rows is None and validated_rows != total_rows:
        raise ValueError(f"{out_path} row count mismatch: source {total_rows}, output {validated_rows}")

    print(f"[{year}] 输入总行数: {total_rows}")
    if args.max_rows is not None:
        print(f"[{year}] 验证模式行数上限: {args.max_rows}")
    print(f"[{year}] 输出行数: {validated_rows}")
    print(f"[{year}] advisor_recall_level分布: {dict(level_counts)}")
    print(f"[{year}] sample_pool分布: {dict(pool_counts)}")
    print(f"[{year}] review_priority分布: {dict(priority_counts)}")
    print(f"[{year}] 输出文件: {out_path}")


def main() -> None:
    args = parse_args()
    validate_inputs(args)
    term_sets = load_term_sets(args.term_dir)
    validate_term_sets(term_sets)
    c_forward_pattern = build_c_bound_pattern(term_sets["C_LEFT"], term_sets["C_RIGHT"])
    c_reverse_pattern = build_c_reverse_bound_pattern(term_sets["C_LEFT"], term_sets["C_RIGHT"])

    con = duckdb.connect()
    for year in args.years:
        process_year(
            con,
            year,
            args,
            term_sets,
            c_forward_pattern,
            c_reverse_pattern,
        )


if __name__ == "__main__":
    main()
