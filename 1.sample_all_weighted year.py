import argparse
import csv
import random
import re
from pathlib import Path


DEFAULT_SAMPLE_SIZE_PER_YEAR = 2000
DEFAULT_SEED = 20260610
START_YEAR = 2014
END_YEAR = 2026


def find_default_input_dir(script_dir: Path) -> Path:
    chapter_dir = script_dir.parent.parent
    marker = "\u62db\u8058\u6570\u636e"
    candidates = [p for p in chapter_dir.iterdir() if p.is_dir() and marker in p.name]
    if len(candidates) != 1:
        names = ", ".join(p.name for p in candidates) or "none"
        raise SystemExit(f"Expected one data folder under {chapter_dir}, found: {names}")
    return candidates[0]


def normalize_header(header: list[str]) -> list[str]:
    return [name for name in header if name != ""]


def extract_year(path: Path) -> int | None:
    match = re.search(r"(20\d{2})", path.stem)
    return int(match.group(1)) if match else None


def sample_file(path: Path, header: list[str] | None, sample_size: int, rng: random.Random):
    reservoir = []
    total = 0

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        current_header = normalize_header(next(reader))

        if header is not None and current_header != header:
            raise SystemExit(f"Header mismatch in {path.name}: {current_header!r}")

        width = len(current_header)
        for raw_row in reader:
            if not raw_row:
                continue
            row = raw_row[:width]
            if len(row) < width:
                row += [""] * (width - len(row))

            total += 1
            if len(reservoir) < sample_size:
                reservoir.append(row)
            else:
                index = rng.randrange(total)
                if index < sample_size:
                    reservoir[index] = row

    return current_header, total, reservoir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample up to 2000 rows from each yearly listed-company recruitment CSV."
    )
    parser.add_argument("--input-dir", type=Path, default=None, help="Folder containing yearly CSV files.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sample-2000.csv"),
        help="Output CSV path. Relative paths are written under the input data folder.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE_PER_YEAR,
        help="Rows to sample from each year.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed for reproducible samples.")
    args = parser.parse_args()

    if args.sample_size <= 0:
        raise SystemExit("--sample-size must be greater than 0")

    script_dir = Path(__file__).resolve().parent
    input_dir = args.input_dir or find_default_input_dir(script_dir)
    output = args.output if args.output.is_absolute() else input_dir / args.output

    prefix = "\u4e0a\u5e02\u516c\u53f8\u62db\u8058\u6570\u636e"
    files = []
    for path in sorted(input_dir.glob(prefix + "*.csv")):
        year = extract_year(path)
        if year is not None and START_YEAR <= year <= END_YEAR:
            files.append((year, path))

    if not files:
        raise SystemExit(f"No {START_YEAR}-{END_YEAR} input CSV files found under {input_dir}")

    rng = random.Random(args.seed)
    canonical_header = None
    sampled_by_file = []
    counts = []

    for year, path in files:
        canonical_header, total, rows = sample_file(path, canonical_header, args.sample_size, rng)
        sampled_by_file.append((year, path.name, rows))
        counts.append((year, path.name, total, len(rows)))

    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(canonical_header)
        for _, _, rows in sampled_by_file:
            writer.writerows(rows)

    print(f"OUTPUT\t{output}")
    print(f"HEADER_COLS\t{len(canonical_header)}")
    print(f"TOTAL_SAMPLED\t{sum(sampled for _, _, _, sampled in counts)}")
    print("YEAR\tFILE\tTOTAL_ROWS\tSAMPLED_ROWS")
    for item in counts:
        print("\t".join(map(str, item)))


if __name__ == "__main__":
    main()
