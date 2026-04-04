#!/usr/bin/env python3
"""Download arXiv PDFs listed in a text file with a resumable queue."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IDS_PATH = ROOT / "scripts" / "arxiv_ids.txt"
DEFAULT_OUTPUT_DIR = Path("/home/valbert/books/arxiv_papers")
QUEUE_FILENAME = "arxiv_ids_remaining.txt"
SOURCE_SNAPSHOT_FILENAME = "arxiv_ids_source.txt"
DEFAULT_GSUTIL = "gsutil"

VERSION_PATTERN = re.compile(r"v(\d+)\.pdf$")
LEGACY_ID_PATTERN = re.compile(r"^(?P<archive>[a-z-]+)/(?P<number>\d{7})$", re.IGNORECASE)
MODERN_ID_PATTERN = re.compile(r"^(?P<number>\d{4}\.\d{4,5})$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download arXiv PDFs from the arxiv-dataset GCS bucket and maintain "
            "a queue file containing only IDs that have not yet been downloaded."
        )
    )
    parser.add_argument(
        "--ids-file",
        type=Path,
        default=DEFAULT_IDS_PATH,
        help=f"Source file containing one arXiv ID per line. Default: {DEFAULT_IDS_PATH}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory where PDFs and queue files will be stored. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--queue-file",
        type=Path,
        default=None,
        help=(
            "Path to the resumable queue file. Defaults to "
            "<output-dir>/arxiv_ids_remaining.txt."
        ),
    )
    parser.add_argument(
        "--gsutil",
        default=DEFAULT_GSUTIL,
        help=f"Path to the gsutil executable. Default: {DEFAULT_GSUTIL}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of IDs to process in this run.",
    )
    parser.add_argument(
        "--skip-existing",
        dest="skip_existing",
        action="store_true",
        default=True,
        help=(
            "Treat an already-downloaded PDF as complete and remove its ID from the "
            "queue. Enabled by default."
        ),
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Do not treat already-present PDFs as complete.",
    )
    return parser.parse_args()


def read_ids(ids_path: Path) -> list[str]:
    ids: list[str] = []
    for raw_line in ids_path.read_text(encoding="utf-8").splitlines():
        paper_id = raw_line.strip()
        if paper_id and not paper_id.startswith("#"):
            ids.append(paper_id)
    return ids


def write_ids(ids_path: Path, ids: list[str]) -> None:
    content = "\n".join(ids)
    if content:
        content += "\n"
    tmp_path = ids_path.with_name(f"{ids_path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(ids_path)


def ensure_queue_file(source_ids_path: Path, queue_path: Path, snapshot_path: Path) -> list[str]:
    if queue_path.exists():
        return read_ids(queue_path)

    if not source_ids_path.exists():
        raise FileNotFoundError(f"Source IDs file does not exist: {source_ids_path}")

    shutil.copy2(source_ids_path, snapshot_path)
    shutil.copy2(source_ids_path, queue_path)
    return read_ids(queue_path)


def modern_month_prefix(arxiv_id: str) -> str:
    match = MODERN_ID_PATTERN.fullmatch(arxiv_id)
    if match is None:
        raise ValueError(f"Unsupported modern arXiv ID format: {arxiv_id}")
    return match.group("number").split(".", 1)[0]


def legacy_parts(arxiv_id: str) -> tuple[str, str, str]:
    match = LEGACY_ID_PATTERN.fullmatch(arxiv_id)
    if match is None:
        raise ValueError(f"Unsupported legacy arXiv ID format: {arxiv_id}")
    archive = match.group("archive").lower()
    number = match.group("number")
    month = number[:4]
    return archive, month, number


def pdf_uri_pattern(arxiv_id: str) -> str:
    if "/" in arxiv_id:
        archive, month, number = legacy_parts(arxiv_id)
        return f"gs://arxiv-dataset/arxiv/{archive}/pdf/{month}/{number}v*.pdf"

    month = modern_month_prefix(arxiv_id)
    return f"gs://arxiv-dataset/arxiv/arxiv/pdf/{month}/{arxiv_id}v*.pdf"


def latest_pdf_uri(gsutil: str, arxiv_id: str) -> str | None:
    uri_pattern = pdf_uri_pattern(arxiv_id)
    result = subprocess.run(
        [gsutil, "ls", uri_pattern],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    candidates = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not candidates:
        return None

    def version_key(uri: str) -> int:
        match = VERSION_PATTERN.search(uri)
        return int(match.group(1)) if match else -1

    return max(candidates, key=version_key)


def versioned_filename(arxiv_id: str, remote_uri: str) -> str:
    remote_name = Path(remote_uri).name
    if "/" not in arxiv_id:
        return remote_name

    match = VERSION_PATTERN.search(remote_name)
    if match is None:
        raise ValueError(f"Could not determine version from {remote_uri}")

    safe_id = arxiv_id.replace("/", "_")
    version = match.group(1)
    return f"{safe_id}v{version}.pdf"


def local_pdf_path(output_dir: Path, arxiv_id: str, remote_uri: str) -> Path:
    return output_dir / versioned_filename(arxiv_id, remote_uri)


def download_pdf(gsutil: str, remote_uri: str, destination: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [gsutil, "cp", remote_uri, str(destination)],
        check=False,
        capture_output=True,
        text=True,
    )


def print_progress(message: str) -> None:
    print(message, flush=True)


def main() -> int:
    args = parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    queue_path = (
        args.queue_file.expanduser().resolve()
        if args.queue_file is not None
        else output_dir / QUEUE_FILENAME
    )
    snapshot_path = output_dir / SOURCE_SNAPSHOT_FILENAME
    source_ids_path = args.ids_file.expanduser().resolve()

    try:
        remaining_ids = ensure_queue_file(source_ids_path, queue_path, snapshot_path)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not remaining_ids:
        print_progress(f"No IDs left to process in {queue_path}")
        return 0

    total_before = len(remaining_ids)
    attempted = 0
    downloaded = 0
    skipped_existing = 0
    missing = 0
    failed = 0

    index = 0
    while index < len(remaining_ids):
        if args.limit is not None and attempted >= args.limit:
            break

        arxiv_id = remaining_ids[index]
        attempted += 1
        print_progress(f"[{attempted}/{total_before}] Processing {arxiv_id}")

        try:
            remote_uri = latest_pdf_uri(args.gsutil, arxiv_id)
        except ValueError as exc:
            failed += 1
            print(exc, file=sys.stderr)
            index += 1
            continue

        if remote_uri is None:
            missing += 1
            print_progress(f"  Missing from bucket, leaving in queue: {arxiv_id}")
            index += 1
            continue

        destination = local_pdf_path(output_dir, arxiv_id, remote_uri)
        if args.skip_existing:
            if destination.exists():
                skipped_existing += 1
                print_progress(f"  Already present, removing from queue: {destination.name}")
                remaining_ids.pop(index)
                write_ids(queue_path, remaining_ids)
                continue

        result = download_pdf(args.gsutil, remote_uri, destination)
        if result.returncode == 0:
            downloaded += 1
            print_progress(f"  Downloaded {destination.name}")
            remaining_ids.pop(index)
            write_ids(queue_path, remaining_ids)
            continue

        failed += 1
        stderr = result.stderr.strip()
        if stderr:
            print(stderr, file=sys.stderr)
        print_progress(f"  Download failed, leaving in queue: {arxiv_id}")
        index += 1

    print_progress(
        "Finished run: "
        f"downloaded={downloaded}, skipped_existing={skipped_existing}, "
        f"missing={missing}, failed={failed}, remaining={len(remaining_ids)}"
    )
    print_progress(f"Queue file: {queue_path}")
    print_progress(f"Download directory: {output_dir}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
