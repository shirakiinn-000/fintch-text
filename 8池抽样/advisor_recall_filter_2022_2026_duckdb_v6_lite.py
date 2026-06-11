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
DEFAULT_TITLE_COLS = ["招聘岗位"]
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
    "c_rule_version",
    "c_relax_type",
]

C_RULE_VERSION = "v6_lite_c_relax"

TITLE_TOUGU_PATTERNS = [
    "投顾",
    "特聘投顾",
    "证券投顾",
    "基金投顾",
    "投顾岗",
    "投顾助理",
    "投顾服务",
    "投顾业务",
    "投顾组合",
    "投顾签约",
]

TITLE_TOUGU_WEAK_CONTEXTS = [
    "投顾资格",
    "投顾资格者优先",
    "考取投顾资格",
    "投顾资源",
    "投顾培训",
    "投顾产品发行",
]

C_SOFT_CLIENT_TERMS = [
    "客户",
    "高净值客户",
    "中高端客户",
    "高端个人客户",
    "财富客户",
    "私行客户",
    "存量客户",
    "现有客户",
    "机构客户",
    "机构投资者",
    "机构财富类客户",
    "个人客户",
    "客户需求",
    "客户实际情况",
    "客户资产",
    "客户画像",
    "客户投资需求",
    "客户理财需求",
]

C_STRONG_ADVISORY_RIGHT_TERMS = [
    "投资咨询服务",
    "投资咨询",
    "投资建议",
    "资产配置方案",
    "资产配置计划",
    "资产配置建议",
    "个性化资产配置",
    "定制化理财方案",
    "专属资产配置方案",
    "投资理财方案",
    "理财方案",
    "理财规划",
    "财富规划",
    "投资规划方案",
    "金融解决方案",
    "定制金融解决方案",
    "综合金融服务方案",
    "产品组合",
    "投资组合方案",
    "基金组合策略",
    "适当性管理",
    "投资者教育服务",
    "定期调整建议",
    "持续投顾服务",
]

FINANCIAL_CONTEXT_TERMS = [
    "证券",
    "基金",
    "信托",
    "期货",
    "银行",
    "保险资管",
    "公募",
    "私募",
    "资管",
    "资产管理",
    "财富管理",
    "理财",
    "金融产品",
    "投研",
    "投资咨询",
    "投资者教育",
    "证券从业",
    "基金从业",
]

HARD_EXCLUSION_GROUPS = {
    "excluded_internal_portfolio": [
        "资产管理部",
        "权益投资经理",
        "公募权益投资经理",
        "固定收益组合投资岗",
        "股票投资岗",
        "基金经理",
        "投资经理",
        "首席投资官",
        "投研",
        "研究员",
        "信评",
        "风险控制",
        "风险管理",
        "业绩归因",
        "FOF研究",
        "交易管理",
    ],
    "excluded_financing_ib": [
        "融资经理",
        "募资",
        "LP群体",
        "投行项目",
        "项目承揽",
        "IPO",
        "新三板",
        "企业债",
        "债券承销",
        "并购重组",
        "股权投资项目",
    ],
    "excluded_sales_channel": [
        "产品销售",
        "基金销售",
        "销售任务",
        "销售目标",
        "渠道拓展",
        "渠道经理",
        "市场渠道",
        "商务合作",
        "客户开发",
        "客户维护",
        "营销活动",
        "募资渠道",
        "直销总监",
    ],
    "excluded_non_financial": [
        "IT",
        "运维",
        "测试",
        "售前",
        "解决方案经理",
        "房地产",
        "大健康",
        "细胞",
        "养老社区",
        "教育培训",
        "客服通知",
        "积分兑换",
    ],
}

WEAK_ONLY_C_TERMS = {"高净值客户", "投资组合", "收益目标", "投资目标"}

TERM_FILES = {
    "A": "A.txt",
    "B": "B.txt",
    "C_LEFT": "C_left.txt",
    "C_RIGHT": "C_right.txt",
    "D": "D.txt",
    "E": "E.txt",
    "ACTION_WORDS": "action_words.txt",
    "CONNECTOR_WORDS": "connector_words.txt",
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
    parser.add_argument(
        "--title-col",
        default=None,
        help="Job title column to concatenate before duty text. Defaults to 岗位名称, then 招聘岗位 if present.",
    )
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
    required_names = {"A", "B", "C_LEFT", "C_RIGHT", "D", "E", "ACTION_WORDS", "CONNECTOR_WORDS"}
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


def build_c_bound_pattern(
    left_terms: list[str],
    right_terms: list[str],
    action_words: list[str],
    connector_words: list[str],
) -> re.Pattern[str]:
    left_pattern = "|".join(re.escape(term) for term in sorted(left_terms, key=len, reverse=True) if term)
    right_pattern = "|".join(re.escape(term) for term in sorted(right_terms, key=len, reverse=True) if term)
    action_pattern = "|".join(re.escape(term) for term in sorted(action_words, key=len, reverse=True) if term)
    connector_pattern = "|".join(re.escape(term) for term in sorted(connector_words, key=len, reverse=True) if term)

    if not left_pattern or not right_pattern or not action_pattern:
        return re.compile(r"a^")

    lead_pattern = action_pattern
    if connector_pattern:
        lead_pattern = rf"(?:{action_pattern})|(?:{connector_pattern})"

    return re.compile(
        rf"({lead_pattern})[^。；;\n]{{0,50}}({left_pattern})[^。；;\n]{{0,80}}({right_pattern})",
        flags=re.IGNORECASE,
    )


def build_c_reverse_bound_pattern(
    left_terms: list[str],
    right_terms: list[str],
    action_words: list[str],
) -> re.Pattern[str]:
    left_pattern = "|".join(re.escape(term) for term in sorted(left_terms, key=len, reverse=True) if term)
    right_pattern = "|".join(re.escape(term) for term in sorted(right_terms, key=len, reverse=True) if term)
    action_pattern = "|".join(re.escape(term) for term in sorted(action_words, key=len, reverse=True) if term)

    if not left_pattern or not right_pattern or not action_pattern:
        return re.compile(r"a^")

    return re.compile(
        rf"({action_pattern})[^。；;\n]{{0,50}}({right_pattern})[^。；;\n]{{0,80}}({left_pattern})",
        flags=re.IGNORECASE,
    )


def find_terms(text: str, terms: list[str]) -> list[str]:
    folded_text = text.casefold()
    hits = [term for term in terms if term.casefold() in folded_text]
    return sorted(set(hits), key=lambda value: (value.casefold(), value))


def first_hard_exclusion_type(text: str) -> str:
    folded_text = text.casefold()
    for exclusion_type, terms in HARD_EXCLUSION_GROUPS.items():
        if any(term.casefold() in folded_text for term in terms):
            return exclusion_type
    return ""


def title_tougu_hits(title: str) -> list[str]:
    folded_title = title.casefold()
    if any(term.casefold() in folded_title for term in TITLE_TOUGU_WEAK_CONTEXTS):
        return []
    return find_terms(title, TITLE_TOUGU_PATTERNS)


def find_spans(text: str, terms: list[str]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for term in terms:
        if not term:
            continue
        pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
        spans.extend((match.start(), match.end(), term) for match in pattern.finditer(text))
    return spans


def shortest_joint_evidence(text: str, left_terms: list[str], right_terms: list[str]) -> str:
    left_spans = find_spans(text, left_terms)
    right_spans = find_spans(text, right_terms)
    if not left_spans or not right_spans:
        return ""

    best: tuple[int, int] | None = None
    for left_start, left_end, _ in left_spans:
        for right_start, right_end, _ in right_spans:
            start = min(left_start, right_start)
            end = max(left_end, right_end)
            if best is None or (end - start) < (best[1] - best[0]):
                best = (start, end)

    if best is None:
        return ""
    start = max(0, best[0] - 12)
    end = min(len(text), best[1] + 12)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def find_soft_client_strong_advisory(text: str) -> tuple[list[str], list[str], list[str], str]:
    financial_hits = find_terms(text, FINANCIAL_CONTEXT_TERMS)
    soft_hits = find_terms(text, C_SOFT_CLIENT_TERMS)
    strong_hits = find_terms(text, C_STRONG_ADVISORY_RIGHT_TERMS)

    if not financial_hits or not soft_hits or not strong_hits:
        return financial_hits, soft_hits, strong_hits, ""

    if set(soft_hits + strong_hits).issubset(WEAK_ONLY_C_TERMS):
        return financial_hits, soft_hits, strong_hits, ""

    evidence = shortest_joint_evidence(text, soft_hits, strong_hits)
    return financial_hits, soft_hits, strong_hits, evidence


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
    title: str,
    text: str,
    term_sets: dict[str, list[str]],
    c_forward_pattern: re.Pattern[str],
    c_reverse_pattern: re.Pattern[str],
) -> dict[str, str]:
    title_hits = title_tougu_hits(title)
    a_hits = sorted(
        set(find_terms(text, term_sets["A"]) + title_hits),
        key=lambda value: (value.casefold(), value),
    )
    b_hits = find_terms(text, term_sets["B"])
    c_left_hits, c_right_hits, c_snippets = find_c_bound(
        text,
        term_sets["C_LEFT"],
        term_sets["C_RIGHT"],
        c_forward_pattern,
        c_reverse_pattern,
    )
    _, soft_client_hits, strong_advisory_hits, soft_c_evidence = find_soft_client_strong_advisory(text)
    hard_exclusion_type = first_hard_exclusion_type(text)
    d_hits = find_terms(text, term_sets["D"])
    e_hits = find_terms(text, term_sets["E"])
    old_c_bound = bool(c_left_hits and c_right_hits)
    soft_c_bound = bool(soft_c_evidence)
    c_blocked_by_exclusion = bool(hard_exclusion_type and not soft_c_bound)
    c_bound = (old_c_bound or soft_c_bound) and not c_blocked_by_exclusion
    c_relax_type = ""
    c_bound_evidence = ""
    c_risk_override = False

    if title_hits:
        recall_level = "A_high"
        c_relax_type = "title_tougu_fix"
    elif a_hits:
        recall_level = "A_high"
    elif c_bound:
        recall_level = "C_bound"
        if soft_c_bound:
            c_left_hits = sorted(
                set(c_left_hits + soft_client_hits),
                key=lambda value: (value.casefold(), value),
            )
            c_right_hits = sorted(
                set(c_right_hits + strong_advisory_hits),
                key=lambda value: (value.casefold(), value),
            )
            c_bound_evidence = soft_c_evidence
            c_relax_type = "soft_client_strong_advisory"
        else:
            c_bound_evidence = " || ".join(c_snippets[:5])
            c_relax_type = "old_c"
        if hard_exclusion_type:
            c_relax_type = hard_exclusion_type
            c_risk_override = True
    elif b_hits:
        recall_level = "B_broad"
    else:
        pool, sample_stratum, review_priority = UNRECALLED_RISK if e_hits else UNRECALLED_CLEAN
        if c_blocked_by_exclusion:
            c_relax_type = hard_exclusion_type
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
            "c_rule_version": C_RULE_VERSION,
            "c_relax_type": c_relax_type,
        }

    pool, sample_stratum, review_priority = POOL_RULES[(recall_level, bool(d_hits) or c_risk_override)]

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
        "c_bound_evidence": c_bound_evidence,
        "c_rule_version": C_RULE_VERSION,
        "c_relax_type": c_relax_type,
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


def resolve_title_col(header: list[str], title_col: str | None) -> str:
    if title_col:
        if title_col not in header:
            raise ValueError(f"Source CSV missing title column: {title_col}")
        return title_col

    for candidate in DEFAULT_TITLE_COLS:
        if candidate in header:
            return candidate
    raise ValueError(f"Source CSV missing title column. Tried: {DEFAULT_TITLE_COLS}")


def build_recall_text(row: dict[str, str], title_col: str, duty_col: str) -> str:
    parts = [
        row.get(title_col, "").strip(),
        row.get(duty_col, "").strip(),
    ]
    return "\n".join(part for part in parts if part)


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
    valid_relax_types = {
        "",
        "old_c",
        "soft_client_strong_advisory",
        "title_tougu_fix",
        *HARD_EXCLUSION_GROUPS.keys(),
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
            c_rule_version = row.get("c_rule_version", "")
            c_relax_type = row.get("c_relax_type", "")
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
            if c_rule_version != C_RULE_VERSION:
                raise ValueError(f"{output_path} contains unexpected c_rule_version: {c_rule_version}")
            if c_relax_type not in valid_relax_types:
                raise ValueError(f"{output_path} contains unexpected c_relax_type: {c_relax_type}")
            if c_relax_type == "soft_client_strong_advisory" and not row.get("c_bound_evidence", "").strip():
                raise ValueError(f"{output_path} contains soft C row without c_bound_evidence.")
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
    title_col = resolve_title_col(header, args.title_col)
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
                row.get(title_col, "").strip(),
                build_recall_text(row, title_col, args.duty_col),
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
    c_forward_pattern = build_c_bound_pattern(
        term_sets["C_LEFT"],
        term_sets["C_RIGHT"],
        term_sets["ACTION_WORDS"],
        term_sets["CONNECTOR_WORDS"],
    )
    c_reverse_pattern = build_c_reverse_bound_pattern(
        term_sets["C_LEFT"],
        term_sets["C_RIGHT"],
        term_sets["ACTION_WORDS"],
    )

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
