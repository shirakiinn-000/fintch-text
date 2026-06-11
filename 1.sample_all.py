import argparse
import csv
import random
import re
from pathlib import Path

#从所有上市公司岗位抽样 每年固定样本

DEFAULT_TOTAL_SAMPLE_SIZE = 200
DEFAULT_SEED = 20260610


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


def count_file(path: Path, header: list[str] | None):
    total = 0

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        current_header = normalize_header(next(reader))

        if header is not None and current_header != header:
            raise SystemExit(f"Header mismatch in {path.name}: {current_header!r}")

        for raw_row in reader:
            if raw_row:
                total += 1

    return current_header, total


def allocate_samples(year_counts: list[tuple[str, str, int]], total_sample_size: int, min_per_year: int):
    if total_sample_size <= 0:
        raise SystemExit("--sample-size must be greater than 0")

    eligible = [item for item in year_counts if item[2] > 0]
    if not eligible:
        raise SystemExit("No data rows found in input CSV files")

    min_per_year = max(0, min_per_year)
    if total_sample_size < len(eligible) * min_per_year:
        raise SystemExit(
            f"--sample-size={total_sample_size} is too small for "
            f"--min-per-year={min_per_year} across {len(eligible)} years"
        )

    allocations = {name: min(min_per_year, total) for _, name, total in eligible}
    remaining = total_sample_size - sum(allocations.values())
    remaining_capacity = {name: total - allocations[name] for _, name, total in eligible}

    while remaining > 0:
        available = [(year, name, total) for year, name, total in eligible if remaining_capacity[name] > 0]
        if not available:
            break

        available_total = sum(total for _, _, total in available)
        quotas = []
        assigned = 0
        for year, name, total in available:
            raw_quota = remaining * total / available_total
            add = min(int(raw_quota), remaining_capacity[name])
            quotas.append((raw_quota - int(raw_quota), year, name))
            allocations[name] += add
            remaining_capacity[name] -= add
            assigned += add

        remaining -= assigned
        if remaining <= 0:
            break

        quotas.sort(reverse=True)
        changed = False
        for _, _, name in quotas:
            if remaining <= 0:
                break
            if remaining_capacity[name] <= 0:
                continue
            allocations[name] += 1
            remaining_capacity[name] -= 1
            remaining -= 1
            changed = True

        if not changed:
            break

    return allocations


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
        description="Weighted sample listed-company recruitment CSV rows by yearly job counts."
    )
    parser.add_argument("--input-dir", type=Path, default=None, help="Folder containing yearly CSV files.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sample.csv"),
        help="Output CSV path. Relative paths are written under the input data folder.",
    )
    parser.add_argument("--sample-size", type=int, default=DEFAULT_TOTAL_SAMPLE_SIZE, help="Total rows to sample.")
    parser.add_argument(
        "--min-per-year",
        type=int,
        default=1,
        help="Minimum rows to keep for each non-empty year before weighted allocation.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed for reproducible samples.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    input_dir = args.input_dir or find_default_input_dir(script_dir)
    output = args.output if args.output.is_absolute() else input_dir / args.output

    prefix = "\u4e0a\u5e02\u516c\u53f8\u62db\u8058\u6570\u636e"
    files = sorted(input_dir.glob(prefix + "*.csv"))
    if not files:
        raise SystemExit(f"No input CSV files found under {input_dir}")

    rng = random.Random(args.seed)
    canonical_header = None
    year_counts = []
    sampled_by_file = []
    counts = []

    for path in files:
        canonical_header, total = count_file(path, canonical_header)
        match = re.search(r"(20\d{2})", path.stem)
        year = match.group(1) if match else path.stem
        year_counts.append((year, path.name, total))

    allocations = allocate_samples(year_counts, args.sample_size, args.min_per_year)

    for path in files:
        match = re.search(r"(20\d{2})", path.stem)
        year = match.group(1) if match else path.stem
        target = allocations.get(path.name, 0)
        canonical_header, total, rows = sample_file(path, canonical_header, target, rng)
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
    print("YEAR\tFILE\tTOTAL_ROWS\tWEIGHT\tSAMPLED_ROWS")
    for item in counts:
        year, name, total, sampled = item
        weight = total / sum(row_total for _, _, row_total, _ in counts)
        print("\t".join(map(str, (year, name, total, f"{weight:.8f}", sampled))))


if __name__ == "__main__":
    main()
