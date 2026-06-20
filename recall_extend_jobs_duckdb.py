from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

import duckdb

#召回额外岗位

DEFAULT_RULE_PATH = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\codex\fintech 文本提取\dict\拓展岗位召回\拓展岗位召回.txt"
)
DEFAULT_SOURCE_PATH = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据\advisor_recall_weighted_pool_sample_2014_2026.csv"
)
DEFAULT_OUTPUT_PATH = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\召回岗位数据\advisor_recall_weighted_pool_sample_2014_2026_拓展岗位召回命中.csv"
)
DEFAULT_EXCLUDE_SAMPLE_PATH = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\标注数据\人工标注1600种子_剔除重复id.csv"
)

ID_COL = "id"
DESCRIPTION_COL = "职位描述"
TITLE_COL = "招聘岗位"
COMPLIANCE_LABEL = "合规"
COMPLIANCE_TITLE_TERM = "合规"
ADDED_FIELDS = [
    "拓展召回标签",
    "拓展召回命中词",
    "拓展召回标签数",
    "拓展召回词表文件",
]
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")


def contains_term(term: str, text: str) -> bool:
    if ASCII_LETTER_RE.search(term):
        return re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", text) is not None
    return term in text


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def parse_rules(path: Path) -> list[tuple[str, list[str]]]:
    lines = [line.strip() for line in read_text_with_fallback(path).splitlines() if line.strip()]
    if len(lines) % 2 != 0:
        raise ValueError(f"Rule file should contain label/term pairs, got {len(lines)} non-empty lines: {path}")

    rules: list[tuple[str, list[str]]] = []
    for index in range(0, len(lines), 2):
        label = re.sub(r"[:：]$", "", lines[index])
        label = re.sub(r"召回$", "", label)
        terms_line = lines[index + 1]
        if terms_line.startswith("(") and terms_line.endswith(")"):
            terms_line = terms_line[1:-1]
        terms = [term.strip() for term in terms_line.split("|") if term.strip()]
        if not label or not terms:
            raise ValueError(f"Invalid rule block near line {index + 1}: {path}")
        rules.append((label, terms))
    return rules


def detect_csv_encoding(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                handle.readline()
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8-sig"


def duckdb_source_summary(path: Path) -> tuple[int, list[str]]:
    con = duckdb.connect()
    escaped = str(path).replace("'", "''")
    rel = con.sql(
        f"""
        select *
        from read_csv_auto(
            '{escaped}',
            header=true,
            all_varchar=true,
            ignore_errors=true,
            union_by_name=true,
            encoding='utf-8'
        )
        """
    )
    row_count = rel.count("*").fetchone()[0]
    columns = [column[0] for column in rel.description]
    con.close()
    return int(row_count), columns


def load_excluded_ids(path: Path, id_col: str = ID_COL) -> tuple[set[str], dict[str, int]]:
    if not path.exists():
        raise FileNotFoundError(f"Exclude sample CSV not found: {path}")

    encoding = detect_csv_encoding(path)
    excluded_ids: set[str] = set()
    total_rows = 0
    empty_id_rows = 0
    duplicate_id_rows = 0

    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Exclude sample CSV has no header: {path}")
        if id_col not in reader.fieldnames:
            raise ValueError(f"Missing required column {id_col!r} in exclude sample CSV: {path}")

        for row in reader:
            total_rows += 1
            row_id = (row.get(id_col) or "").strip()
            if not row_id:
                empty_id_rows += 1
                continue
            if row_id in excluded_ids:
                duplicate_id_rows += 1
            excluded_ids.add(row_id)

    return excluded_ids, {
        "exclude_sample_rows": total_rows,
        "exclude_sample_unique_ids": len(excluded_ids),
        "exclude_sample_empty_id_rows": empty_id_rows,
        "exclude_sample_duplicate_id_rows": duplicate_id_rows,
    }


def matched_labels(desc: str, title: str, rules: list[tuple[str, list[str]]]) -> tuple[list[str], list[str]]:
    labels: list[str] = []
    hit_parts: list[str] = []
    for label, terms in rules:
        hits = []
        for term in terms:
            if contains_term(term, desc):
                hits.append(term)
        if hits:
            labels.append(label)
            hit_parts.append(f"{label}={'|'.join(hits)}")
    if COMPLIANCE_TITLE_TERM in title and COMPLIANCE_LABEL not in labels:
        labels.append(COMPLIANCE_LABEL)
        hit_parts.append(f"{COMPLIANCE_LABEL}={TITLE_COL}:{COMPLIANCE_TITLE_TERM}")
    return labels, hit_parts


def write_hits(
    rule_path: Path,
    source_path: Path,
    output_path: Path,
    exclude_sample_path: Path | None = DEFAULT_EXCLUDE_SAMPLE_PATH,
    id_col: str = ID_COL,
) -> dict[str, object]:
    if not rule_path.exists():
        raise FileNotFoundError(f"Rule file not found: {rule_path}")
    if not source_path.exists():
        raise FileNotFoundError(f"Source CSV not found: {source_path}")

    source_rows_duckdb, source_columns_duckdb = duckdb_source_summary(source_path)
    if DESCRIPTION_COL not in source_columns_duckdb:
        raise ValueError(f"Missing required column {DESCRIPTION_COL!r} in source CSV: {source_path}")
    if exclude_sample_path is not None and id_col not in source_columns_duckdb:
        raise ValueError(f"Missing required column {id_col!r} in source CSV: {source_path}")

    rules = parse_rules(rule_path)
    excluded_ids: set[str] = set()
    exclude_summary: dict[str, int] = {
        "exclude_sample_rows": 0,
        "exclude_sample_unique_ids": 0,
        "exclude_sample_empty_id_rows": 0,
        "exclude_sample_duplicate_id_rows": 0,
    }
    if exclude_sample_path is not None:
        excluded_ids, exclude_summary = load_excluded_ids(exclude_sample_path, id_col)

    encoding = detect_csv_encoding(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    multi_label_rows = 0
    excluded_source_rows = 0
    excluded_matched_rows = 0
    label_counts: Counter[str] = Counter()

    with source_path.open("r", encoding=encoding, newline="") as input_handle:
        reader = csv.DictReader(input_handle)
        if reader.fieldnames is None:
            raise ValueError(f"Source CSV has no header: {source_path}")
        if DESCRIPTION_COL not in reader.fieldnames:
            raise ValueError(f"Missing required column {DESCRIPTION_COL!r} in source CSV: {source_path}")

        fieldnames = list(reader.fieldnames) + ADDED_FIELDS
        with output_path.open("w", encoding="utf-8-sig", newline="") as output_handle:
            writer = csv.DictWriter(output_handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in reader:
                row_id = (row.get(id_col) or "").strip()
                is_excluded = row_id in excluded_ids
                labels, hit_parts = matched_labels(
                    row.get(DESCRIPTION_COL) or "",
                    row.get(TITLE_COL) or "",
                    rules,
                )
                if is_excluded:
                    excluded_source_rows += 1
                    if labels:
                        excluded_matched_rows += 1
                    continue
                if not labels:
                    continue
                row["拓展召回标签"] = ";".join(labels)
                row["拓展召回命中词"] = ";".join(hit_parts)
                row["拓展召回标签数"] = str(len(labels))
                row["拓展召回词表文件"] = rule_path.name
                writer.writerow(row)

                rows_written += 1
                if len(labels) > 1:
                    multi_label_rows += 1
                label_counts.update(labels)

    readback = validate_output(source_path, output_path, source_columns_duckdb, excluded_ids, id_col)
    return {
        "source_rows_duckdb": source_rows_duckdb,
        "source_columns": len(source_columns_duckdb),
        "exclude_sample_path": str(exclude_sample_path) if exclude_sample_path is not None else "",
        **exclude_summary,
        "excluded_source_rows": excluded_source_rows,
        "excluded_matched_rows": excluded_matched_rows,
        "rule_count": len(rules),
        "term_count": sum(len(terms) for _, terms in rules),
        "rows_written": rows_written,
        "multi_label_rows": multi_label_rows,
        "label_counts": dict(sorted(label_counts.items())),
        **readback,
    }


def validate_output(
    source_path: Path,
    output_path: Path,
    source_columns: list[str],
    excluded_ids: set[str] | None = None,
    id_col: str = ID_COL,
) -> dict[str, object]:
    with output_path.open("rb") as handle:
        has_bom = handle.read(3) == b"\xef\xbb\xbf"

    output_rows = 0
    empty_label_rows = 0
    excluded_id_rows_in_output = 0
    readback_label_counts: Counter[str] = Counter()
    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        output_fields = reader.fieldnames or []
        original_prefix_ok = output_fields[: len(source_columns)] == source_columns
        added_fields_ok = output_fields[len(source_columns) :] == ADDED_FIELDS
        for row in reader:
            output_rows += 1
            labels = [label for label in (row.get("拓展召回标签") or "").split(";") if label]
            if not labels:
                empty_label_rows += 1
            if excluded_ids and (row.get(id_col) or "").strip() in excluded_ids:
                excluded_id_rows_in_output += 1
            readback_label_counts.update(labels)

    return {
        "output_rows_readback": output_rows,
        "output_has_bom": has_bom,
        "original_prefix_ok": original_prefix_ok,
        "added_fields_ok": added_fields_ok,
        "empty_label_rows": empty_label_rows,
        "excluded_id_rows_in_output": excluded_id_rows_in_output,
        "readback_label_counts": dict(sorted(readback_label_counts.items())),
        "output_path": str(output_path),
        "source_path": str(source_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recall extended job categories from 职位描述 using a TXT rule file.")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULE_PATH, help="Path to 拓展岗位召回.txt")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_PATH, help="Source sample CSV")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output hit CSV")
    parser.add_argument(
        "--exclude-sample",
        type=Path,
        default=DEFAULT_EXCLUDE_SAMPLE_PATH,
        help="CSV whose id values should be excluded from recall output",
    )
    parser.add_argument("--id-col", default=ID_COL, help="ID column used for exclusion")
    parser.add_argument(
        "--no-exclude-sample",
        action="store_true",
        help="Disable exclusion of ids from the 1000-sample CSV",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exclude_sample = None if args.no_exclude_sample else args.exclude_sample
    summary = write_hits(args.rules, args.source, args.output, exclude_sample, args.id_col)
    for key, value in summary.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
