#!/usr/bin/env python3

# Pick a random sample of code_id keys for YAML files under codes/ that received
# a substantive edit within the N months preceding a given reference date.
#
# Bulk commits that only stamp a new _meta changelog entry (e.g. e9237537c
# touched 1104 of 1142 files) would otherwise mark nearly every code as
# recently edited, so changes consisting solely of changelog entries do not
# count as edits here.

from __future__ import annotations

import argparse
import calendar
import datetime
import random
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CHANGELOG_LINE = re.compile(r"^[+-]\s*(-\s*)?(user_id|date)\s*:", re.IGNORECASE)


def months_before(date: datetime.date, months: int) -> datetime.date:
    month_index = date.month - 1 - months
    year = date.year + month_index // 12
    month = month_index % 12 + 1
    return datetime.date(year, month, min(date.day, calendar.monthrange(year, month)[1]))


def build_rename_map(start_date: datetime.date, end_date: datetime.date) -> dict[str, str]:
    # Codes get reshuffled through the taxonomy, so an edit often lands under a
    # path that no longer exists. Chain renames oldest-first so a historical
    # path can be walked forward to where the entry lives now.
    result = subprocess.run(
        [
            "git", "log", "--reverse",
            f"--since={start_date.isoformat()}",
            f"--until={end_date.isoformat()} 23:59:59",
            "--name-status", "--find-renames", "--no-color", "--pretty=format:",
            "--", "codes",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    renames: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.startswith("R"):
            continue
        fields = line.split("\t")
        if len(fields) == 3:
            renames[fields[1]] = fields[2]
    return renames


def resolve_current_path(path: str, renames: dict[str, str]) -> str:
    seen: set[str] = set()
    while path in renames and path not in seen:
        seen.add(path)
        path = renames[path]
    return path


def find_substantively_edited_paths(start_date: datetime.date, end_date: datetime.date) -> set[Path]:
    process = subprocess.Popen(
        [
            "git", "log",
            f"--since={start_date.isoformat()}",
            f"--until={end_date.isoformat()} 23:59:59",
            "-p", "--unified=0", "--no-color", "--pretty=format:",
            "--", "codes",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        text=True,
    )

    edited: set[str] = set()
    current: str | None = None
    in_hunk = False

    # Track hunk state explicitly: only inside a hunk does a leading +/- mean a
    # changed line. Otherwise the "--- a/path" header, or a blank line between
    # commits, gets misread as content.
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip("\n")
        if line.startswith("diff --git "):
            current, in_hunk = None, False
        elif line.startswith("+++ "):
            target = line[4:].strip()
            # "+++ /dev/null" marks a deletion and must not inherit the previous file.
            current = target[2:] if target.startswith("b/") and target.endswith(".yml") else None
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and current is not None and line[:1] in ("+", "-"):
            if line.strip() in {"+", "-"} or CHANGELOG_LINE.match(line):
                continue
            edited.add(current)
            current = None  # one substantive line settles this file

    if process.wait() != 0:
        raise subprocess.CalledProcessError(process.returncode, "git log")

    renames = build_rename_map(start_date, end_date)
    resolved = {REPO_ROOT / resolve_current_path(path, renames) for path in edited}
    return {path for path in resolved if path.is_file()}


def extract_code_id(path: Path) -> str | None:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.split("#", 1)[0].strip()
            if stripped.startswith("code_id:"):
                return stripped[len("code_id:"):].strip().strip("'\"")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Randomly sample code_id keys for code YAML files edited in the months before a given date."
    )
    parser.add_argument(
        "date",
        nargs="?",
        type=datetime.date.fromisoformat,
        default=datetime.date.today(),
        help="Reference date, YYYY-MM-DD (default: today).",
    )
    parser.add_argument("--months", type=int, default=3, help="Lookback window in months (default: 3).")
    parser.add_argument("--count", type=int, default=5, help="Number of code_id keys to print (default: 5).")
    parser.add_argument("--seed", type=int, default=None, help="Random seed, for reproducible sampling.")
    args = parser.parse_args()

    reference_date = args.date
    start_date = months_before(reference_date, args.months)

    candidates = sorted(
        code_id
        for code_id in (
            extract_code_id(path)
            for path in find_substantively_edited_paths(start_date, reference_date)
        )
        if code_id is not None
    )

    rng = random.Random(args.seed)
    for code_id in rng.sample(candidates, min(args.count, len(candidates))):
        print(code_id)


if __name__ == "__main__":
    main()
