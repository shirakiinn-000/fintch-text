#!/usr/bin/env python3
"""使用 DuckDB 删除 CSV 中所有字段均为空或仅含空白字符的记录。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import uuid4

import duckdb


DEFAULT_INPUT_PATH = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\上市公司招聘数据"
    r"\上市公司招聘数据2014_2026_readable_清洗职位描述.csv"
)
UTF8_BOM = b"\xef\xbb\xbf"


def sql_string(value: str) -> str:
    """将普通字符串安全地转换成 DuckDB SQL 字符串字面量。"""
    return "'" + value.replace("'", "''") + "'"


def csv_scan_sql(path: Path) -> str:
    return (
        "read_csv("
        f"{sql_string(str(path))}, "
        "header = true, "
        "all_varchar = true, "
        "encoding = 'utf-8', "
        "strict_mode = true, "
        "ignore_errors = false, "
        "max_line_size = 104857600"
        ")"
    )


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def prepend_utf8_bom_in_place(path: Path, chunk_size: int = 8 * 1024 * 1024) -> None:
    """用固定大小缓冲区原地添加 BOM，避免为超大 CSV 再复制一份临时文件。"""
    with path.open("r+b") as file:
        if file.read(3) == UTF8_BOM:
            return

        file.seek(0, 2)
        original_size = file.tell()
        file.truncate(original_size + len(UTF8_BOM))

        read_end = original_size
        while read_end > 0:
            read_start = max(0, read_end - chunk_size)
            file.seek(read_start)
            block = file.read(read_end - read_start)
            file.seek(read_start + len(UTF8_BOM))
            file.write(block)
            read_end = read_start

        file.seek(0)
        file.write(UTF8_BOM)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="用 DuckDB 删除 CSV 中所有字段均为空或仅含空白字符的记录。"
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"输入 CSV；默认：{DEFAULT_INPUT_PATH}",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="输出 CSV；默认在输入文件同目录生成“原文件名_删除空行.csv”",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计记录数和空记录数，不生成文件",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许覆盖已存在的输出文件（不会覆盖输入文件）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else input_path.with_name(f"{input_path.stem}_删除空行{input_path.suffix}")
    )

    if not input_path.is_file():
        raise FileNotFoundError(f"找不到输入文件：{input_path}")
    if input_path.suffix.lower() != ".csv":
        raise ValueError(f"输入文件不是 CSV：{input_path}")
    if output_path == input_path:
        raise ValueError("输出路径不能与输入路径相同；脚本不会覆盖源文件。")
    if output_path.exists() and not args.force:
        raise FileExistsError(f"输出文件已存在：{output_path}\n如需覆盖，请添加 --force。")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scan = csv_scan_sql(input_path)

    with duckdb.connect(database=":memory:") as connection:
        connection.execute("SET preserve_insertion_order = true")
        description = connection.execute(f"SELECT * FROM {scan} LIMIT 0").description
        column_names = [item[0] for item in description]
        if not column_names:
            raise ValueError("CSV 中没有可读取的列。")

        empty_terms = [
            f"COALESCE(TRIM(CAST({quote_identifier(name)} AS VARCHAR)), '') = ''"
            for name in column_names
        ]
        empty_condition = " AND ".join(empty_terms)

        source_rows, empty_rows = connection.execute(
            f"SELECT COUNT(*), COUNT(*) FILTER (WHERE {empty_condition}) FROM {scan}"
        ).fetchone()

        print(f"输入文件：{input_path}")
        print(f"列数：{len(column_names):,}")
        print(f"DuckDB 读取到的记录数：{source_rows:,}")
        print(f"待删除的全空记录数：{empty_rows:,}")

        if args.dry_run:
            print("dry-run 完成：未生成输出文件。")
            return 0

        temporary_output = output_path.with_name(
            f".{output_path.name}.{uuid4().hex}.duckdb_tmp"
        )
        try:
            copy_sql = (
                f"COPY (SELECT * FROM {scan} WHERE NOT ({empty_condition})) "
                f"TO {sql_string(str(temporary_output))} "
                "(FORMAT CSV, HEADER true, DELIMITER ',', QUOTE '\"', ESCAPE '\"')"
            )
            connection.execute(copy_sql)
            prepend_utf8_bom_in_place(temporary_output)

            if output_path.exists():
                output_path.unlink()
            temporary_output.replace(output_path)
        finally:
            if temporary_output.exists():
                temporary_output.unlink()

        output_scan = csv_scan_sql(output_path)
        output_description = connection.execute(
            f"SELECT * FROM {output_scan} LIMIT 0"
        ).description
        output_columns = [item[0] for item in output_description]
        output_rows, remaining_empty_rows = connection.execute(
            f"SELECT COUNT(*), COUNT(*) FILTER (WHERE {empty_condition}) FROM {output_scan}"
        ).fetchone()

    expected_rows = source_rows - empty_rows
    has_bom = output_path.open("rb").read(3) == UTF8_BOM
    if output_columns != column_names:
        raise RuntimeError("核验失败：输出文件的列名或列顺序发生变化。")
    if output_rows != expected_rows:
        raise RuntimeError(
            f"核验失败：输出记录数应为 {expected_rows:,}，实际为 {output_rows:,}。"
        )
    if remaining_empty_rows != 0:
        raise RuntimeError(f"核验失败：输出中仍有 {remaining_empty_rows:,} 条全空记录。")
    if not has_bom:
        raise RuntimeError("核验失败：输出文件没有 UTF-8 BOM。")

    print(f"输出文件：{output_path}")
    print(f"输出记录数：{output_rows:,}")
    print(f"实际删除记录数：{source_rows - output_rows:,}")
    print("核验通过：列结构未变、无剩余全空记录、UTF-8 BOM 已保留。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(1)
