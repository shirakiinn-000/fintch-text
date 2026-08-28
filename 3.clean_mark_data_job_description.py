from __future__ import annotations

import argparse
import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path

#任何文件，清除马克数据网水印和html标签

DEFAULT_INPUT = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\上市公司招聘数据\上市公司招聘数据2022_2026_随机抽样100_readable.csv")
DESC_COL = "职位描述"

MARK_NAME = r"马\s*[-－—]?\s*克\s*[-－—]?\s*数\s*[-－—]?\s*据\s*[-－—]?\s*网?"
MARK_NAME1 = r"马-克-数据"
MARK_TEAM = r"马\s*[-－—]?\s*克\s*[-－—]?\s*团\s*[-－—]?\s*队"
MARK_DOMAIN = r"(?:https?://)?(?:www\.)?macrodatas\.cn"

MARK_ALL = rf"(?:{MARK_NAME}|{MARK_TEAM}|{MARK_DOMAIN}|{MARK_NAME1})"

MARK_PATTERNS = [
    rf"[（(]\s*来\s*自?\s*源?\s*{MARK_ALL}\s*[）)]",
    rf"更多\s*数据\s*来自\s*{MARK_ALL}",
    rf"更多\s*数据\s*来源\s*{MARK_ALL}",
    rf"百度\s*搜索\s*[:：]?\s*{MARK_ALL}",
    rf"百度\s*[:：]?\s*{MARK_ALL}",
    rf"更多\s*数据\s*[:：]?\s*{MARK_ALL}",
    rf"更多\s*数据\s*[:：]?\s*搜\s*索\s*[:：]?\s*{MARK_ALL}\s*来源\s*[:：]?\s*{MARK_ALL}",
    rf"更多\s*数据\s*[:：]?\s*搜\s*索\s*[:：]?\s*{MARK_ALL}",
    rf"(?:关注)?\s*(?:微信)?\s*公众号\s*[:：]?\s*{MARK_ALL}",
    rf"\s*来\s*自?\s*源?\s*[:：]?\s*(?:百度\s*)?\s*[:：]?\s*{MARK_ALL}",
    rf"\s*来\s*自?\s*源?\s*[:：]?\s*{MARK_ALL}",
    rf"数据由\s*{MARK_ALL}\s*整理",
    rf"该数据由<\s*{MARK_ALL}\s*>整理",
    rf"（更多数据，详见\s*[:：]?\s*{MARK_ALL}）",
    rf"关注\s*(?:微信\s*)?公众号\s*[:：]?",
    rf"该数据由<\s*{MARK_ALL}\s*>整理",
    rf"(?:微信\s*)?分享{MARK_ALL}",
    rf";&nbsp",
    rf"&middot",
    rf"（该信息由用户发自手机）",
    rf"分享\s*微信邮件",
    rf"分享\s*微信邮件。",
    rf"搜索",
    rf"。来源：",
    rf"来源：",
    rf"微信分享",
    MARK_ALL,
]

MARK_REGEXES = [re.compile(pattern, flags=re.IGNORECASE) for pattern in MARK_PATTERNS]
HTML_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[^<>]*)?/?>")
HTML = re.compile(r'^https?://[\w%:@&\-\.?~#=/]+(?:\?[\w%:@&\-\.?=~/]*)?$')
HTML_ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);")
LEFTOVER_SPACE_RE = re.compile(r"\s+")
SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([，。；：、,.!?！？;:])")
EMPTY_BRACKETS_RE = re.compile(r"[（(]\s*[）)]")
CLEAN_SYMBOL_RE = re.compile(r"[●◆■□▪▫•·◦○◎★☆▶▷➤➢*]")


@dataclass
class CleanStats:
    rows: int = 0
    changed_rows: int = 0
    markers_before: int = 0
    markers_after: int = 0
    html_before: int = 0
    html_after: int = 0


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_清洗职位描述{input_path.suffix}")


def has_mark_data_marker(text: str) -> bool:
    return any(regex.search(text) for regex in MARK_REGEXES)


def has_html_artifact(text: str) -> bool:
    return bool(HTML_TAG_RE.search(text) or HTML_ENTITY_RE.search(text))


def has_clean_symbol(text: str) -> bool:
    return bool(CLEAN_SYMBOL_RE.search(text))


def unescape_html_entities(text: str) -> str:
    for _ in range(20):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    return text


def clean_description_text(value: str | None) -> str:
    if value is None:
        return ""

    text = str(value)
    if not has_mark_data_marker(text) and not has_html_artifact(text) and not has_clean_symbol(text):
        return text

    text = unescape_html_entities(text)
    text = HTML_TAG_RE.sub(" ", text)

    for regex in MARK_REGEXES:
        text = regex.sub(" ", text)

    text = CLEAN_SYMBOL_RE.sub("", text)
    text = EMPTY_BRACKETS_RE.sub(" ", text)
    text = SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = LEFTOVER_SPACE_RE.sub(" ", text).strip()
    return text


def open_csv_reader(path: Path):
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            handle = path.open("r", encoding=encoding, newline="")
            sample = handle.read(4096)
            handle.seek(0)
            sample.encode("utf-8")
            return handle, encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", b"", 0, 1, f"Cannot decode {path}")


def clean_csv(input_path: Path, output_path: Path, *, dry_run: bool = False) -> CleanStats:
    stats = CleanStats()

    reader_handle, input_encoding = open_csv_reader(input_path)
    with reader_handle:
        reader = csv.DictReader(reader_handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {input_path}")
        if DESC_COL not in reader.fieldnames:
            raise ValueError(f"Missing required column: {DESC_COL}")

        writer_handle = None
        writer = None
        if not dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            writer_handle = output_path.open("w", encoding="utf-8-sig", newline="")
            writer = csv.DictWriter(writer_handle, fieldnames=reader.fieldnames)
            writer.writeheader()

        try:
            for row in reader:
                stats.rows += 1
                before = row.get(DESC_COL) or ""
                if has_mark_data_marker(before):
                    stats.markers_before += 1
                if has_html_artifact(before):
                    stats.html_before += 1

                after = clean_description_text(before)
                if after != before:
                    stats.changed_rows += 1
                if has_mark_data_marker(after):
                    stats.markers_after += 1
                if has_html_artifact(after):
                    stats.html_after += 1

                row[DESC_COL] = after
                if writer is not None:
                    writer.writerow(row)
        finally:
            if writer_handle is not None:
                writer_handle.close()

    print(f"input={input_path}")
    print(f"input_encoding={input_encoding}")
    print(f"output={output_path if not dry_run else '(dry-run, not written)'}")
    print(f"rows={stats.rows}")
    print(f"changed_rows={stats.changed_rows}")
    print(f"marker_rows_before={stats.markers_before}")
    print(f"marker_rows_after={stats.markers_after}")
    print(f"html_rows_before={stats.html_before}")
    print(f"html_rows_after={stats.html_after}")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean Mark Data Network watermark and HTML tags from the 职位描述 column in a CSV."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input CSV path.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path. Defaults to '<input stem>_清洗职位描述.csv'.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print cleaning statistics.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input
    output_path = args.output or default_output_path(input_path)
    clean_csv(input_path, output_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
