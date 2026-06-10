from __future__ import annotations

import csv
import re
from pathlib import Path


INPUT_CSV = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\上市公司招聘数据\sample_readable_清洗职位描述.csv")
OUTPUT_TXT = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\上市公司招聘数据\"投顾岗位职位描述.txt")

JOB_COLUMN = "招聘岗位"
DESCRIPTION_COLUMN = "职位描述"
KEYWORDS = ("投顾", "投资顾问")
PAREN_CONTENT_RE = re.compile(r"（[^）]*）|\([^)]*\)")


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_investment_advisor_job(title: str) -> bool:
    role_text = PAREN_CONTENT_RE.sub("", title)
    return any(keyword in role_text for keyword in KEYWORDS)


def main() -> None:
    matches: list[dict[str, str]] = []

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row.")

        missing = [col for col in (JOB_COLUMN, DESCRIPTION_COLUMN) if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        total_rows = 0
        for row in reader:
            total_rows += 1
            job_title = normalize(row.get(JOB_COLUMN))
            if is_investment_advisor_job(job_title):
                matches.append({key: normalize(value) for key, value in row.items()})

    with OUTPUT_TXT.open("w", encoding="utf-8") as f:
        f.write(f"来源文件：{INPUT_CSV}\n")
        f.write(f"识别规则：去除招聘岗位括号内容后，岗位名包含 {'、'.join(KEYWORDS)}\n")
        f.write(f"总行数：{total_rows}\n")
        f.write(f"投顾岗位数量：{len(matches)}\n")
        f.write("=" * 80 + "\n\n")

        for index, row in enumerate(matches, start=1):
            f.write(f"{index}. {row.get(JOB_COLUMN, '')}\n")
            f.write(f"企业名称：{row.get('企业名称', '')}\n")
            f.write(f"股票简称：{row.get('股票简称', '')}\n")
            f.write(f"关联股票代码：{row.get('关联股票代码', '')}\n")
            f.write(f"招聘发布年份：{row.get('招聘发布年份', '')}\n")
            f.write(f"工作城市：{row.get('工作城市', '')}\n")
            f.write("职位描述：\n")
            f.write(row.get(DESCRIPTION_COLUMN, ""))
            f.write("\n\n" + "-" * 80 + "\n\n")

    print(f"total_rows={total_rows}")
    print(f"matched_rows={len(matches)}")
    print(f"output={OUTPUT_TXT}")


if __name__ == "__main__":
    main()
