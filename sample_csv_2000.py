from __future__ import annotations

import csv
import random
from pathlib import Path


SOURCE = Path(r"E:\学习资料\研\我的论文\金融科技\第二章论文\投顾数据\投顾召回岗位_readable.csv")
OUTPUT = SOURCE.with_name("投顾召回岗位_抽样2000.csv")
SAMPLE_SIZE = 2000
RANDOM_SEED = 20260610


def main() -> None:
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)

    if len(rows) < SAMPLE_SIZE:
        raise SystemExit(f"not enough rows: {len(rows)} < {SAMPLE_SIZE}")

    sample = random.Random(RANDOM_SEED).sample(rows, SAMPLE_SIZE)

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(sample)

    with OUTPUT.open("r", encoding="utf-8-sig", newline="") as handle:
        written = list(csv.reader(handle))

    print(f"source_rows={len(rows)}")
    print(f"sample_rows={len(written) - 1}")
    print(f"columns={len(header)}")
    print(f"seed={RANDOM_SEED}")
    print(f"output={OUTPUT}")


if __name__ == "__main__":
    main()
