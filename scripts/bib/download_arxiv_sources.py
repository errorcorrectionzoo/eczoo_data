#!/usr/bin/env python3
"""Download missing arXiv source packages cited by this repository.

The script discovers ``arxiv:`` citations in repository YAML files, queries the
arXiv API in small batches, and fetches only missing source trees.  It is
deliberately serial and defaults to at least three seconds between every arXiv
request, in accordance with arXiv's API etiquette.  If an API batch exhausts
its retries, only that batch falls back to direct source retrieval from the
arXiv website.  A failed ID stays absent, so a later run will retry it without
re-downloading completed sources.
"""

from __future__ import annotations

import argparse
import gzip
import http.client
import io
import json
import re
import shutil
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = REPOSITORY_ROOT.parent / "eczoo_resources" / "arxiv_source"
ARXIV_PATTERN = re.compile(r"arxiv:([^,}\s]+)", re.IGNORECASE)
MODERN_ID_PATTERN = re.compile(r"^\d{4}\.\d{4,5}$")
LEGACY_ID_PATTERN = re.compile(r"^[a-z-]+/\d{7}$", re.IGNORECASE)
VERSION_SUFFIX = re.compile(r"v\d+$", re.IGNORECASE)
ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--delay", type=float, default=3.0,
                        help="minimum seconds between arXiv requests (default: 3)")
    parser.add_argument("--batch-size", type=int, default=20,
                        help="IDs per arXiv API request (default: 20)")
    parser.add_argument("--retries", type=int, default=3,
                        help="attempts for each request (default: 3)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--limit", type=int, default=None,
                        help="maximum number of source packages to download this run")
    parser.add_argument(
        "--retry-source-unavailable",
        action="store_true",
        help="retry packages previously rejected by arXiv's source endpoint",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def normalize_id(value: str) -> str:
    return VERSION_SUFFIX.sub("", value.strip())


def directory_name(arxiv_id: str) -> str:
    return arxiv_id.replace("/", "_")


def valid_id(arxiv_id: str) -> bool:
    return bool(MODERN_ID_PATTERN.fullmatch(arxiv_id) or LEGACY_ID_PATTERN.fullmatch(arxiv_id))


def cited_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".yml", ".yaml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in ARXIV_PATTERN.findall(text):
            arxiv_id = normalize_id(match)
            if valid_id(arxiv_id):
                ids.add(arxiv_id)
    return ids


def existing_ids(source_dir: Path) -> set[str]:
    if not source_dir.exists():
        return set()
    return {
        child.name.replace("_", "/", 1)
        if "_" in child.name and not child.name[:1].isdigit()
        else child.name
        for child in source_dir.iterdir()
        if child.is_dir() and any(child.iterdir())
    }


def state_path(source_dir: Path) -> Path:
    return source_dir / ".arxiv_source_update_state.json"


def load_state(source_dir: Path, cited: set[str]) -> dict[str, list[str]]:
    path = state_path(source_dir)
    if not path.exists():
        return {
            "cited_ids": sorted(cited), "available_ids": [], "unavailable_ids": [],
            "direct_source_ids": [], "unavailable_source_ids": [], "failed_ids": [],
        }
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "cited_ids": sorted(cited), "available_ids": [], "unavailable_ids": [],
            "direct_source_ids": [], "unavailable_source_ids": [], "failed_ids": [],
        }
    if state.get("cited_ids") != sorted(cited):
        return {
            "cited_ids": sorted(cited), "available_ids": [], "unavailable_ids": [],
            "direct_source_ids": [], "unavailable_source_ids": [], "failed_ids": [],
        }
    return state


def save_state(source_dir: Path, state: dict[str, list[str]]) -> None:
    path = state_path(source_dir)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class ArxivClient:
    def __init__(self, delay: float, retries: int, timeout: float) -> None:
        self.delay = delay
        self.retries = retries
        self.timeout = timeout
        self.last_request = 0.0
        self.opener = urllib.request.build_opener()

    def get(self, url: str) -> bytes:
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self.last_request)
            if wait > 0:
                time.sleep(wait)
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": "eczoo-data source updater (contact: EC Zoo)"}
                )
                self.last_request = time.monotonic()
                with self.opener.open(request, timeout=self.timeout) as response:
                    return response.read()
            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                TimeoutError,
                OSError,
                http.client.HTTPException,
            ) as exc:
                if attempt == self.retries:
                    raise RuntimeError(f"{url}: {exc}") from exc
                time.sleep(self.delay * attempt)
        raise AssertionError("unreachable")

    def api_existing_ids(self, ids: list[str]) -> set[str]:
        query = urllib.parse.urlencode({"id_list": ",".join(ids), "max_results": len(ids)})
        response = self.get(f"https://export.arxiv.org/api/query?{query}")
        try:
            feed = ET.fromstring(response)
        except ET.ParseError as exc:
            raise RuntimeError("arXiv API returned malformed XML") from exc
        found: set[str] = set()
        for entry in feed.findall("atom:entry", ATOM_NAMESPACE):
            identifier = entry.findtext("atom:id", default="", namespaces=ATOM_NAMESPACE)
            if "/abs/" in identifier:
                found.add(normalize_id(identifier.rsplit("/abs/", 1)[1]))
        return found


def unpack_source(payload: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
            members = archive.getmembers()
            destination_root = destination.resolve()
            for member in members:
                target = (destination / member.name).resolve()
                if not target.is_relative_to(destination_root):
                    raise RuntimeError(f"unsafe archive member: {member.name}")
            archive.extractall(destination, members=members, filter="data")
            return
    except tarfile.ReadError:
        pass
    try:
        payload = gzip.decompress(payload)
    except gzip.BadGzipFile:
        pass
    (destination / "source.tex").write_bytes(payload)


def chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def main() -> int:
    args = parse_args()
    if args.delay < 3:
        raise SystemExit("--delay must be at least 3 seconds to respect arXiv API etiquette")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")

    source_dir = args.source_dir.expanduser().resolve()
    cited = cited_ids(REPOSITORY_ROOT)
    missing = sorted(cited - existing_ids(source_dir))
    print(f"Cited IDs: {len(cited)}; already present: {len(cited) - len(missing)}; missing: {len(missing)}")
    if args.dry_run:
        print("\n".join(missing))
        return 0
    source_dir.mkdir(parents=True, exist_ok=True)
    client = ArxivClient(args.delay, args.retries, args.timeout)
    state = load_state(source_dir, cited)
    available = set(state.get("available_ids", []))
    unavailable = set(state.get("unavailable_ids", []))
    direct_source_ids = set(state.get("direct_source_ids", []))
    unavailable_sources = set(state.get("unavailable_source_ids", []))
    if args.retry_source_unavailable:
        unavailable_sources.clear()
    metadata_missing = sorted(set(missing) - available - unavailable - direct_source_ids)
    for index, batch in enumerate(chunks(metadata_missing, args.batch_size), start=1):
        print(f"API batch {index}: checking {len(batch)} IDs", flush=True)
        try:
            returned = client.api_existing_ids(batch)
            available.update(returned)
            unavailable.update(set(batch) - returned)
            state["available_ids"] = sorted(available)
            state["unavailable_ids"] = sorted(unavailable)
            save_state(source_dir, state)
        except RuntimeError as exc:
            print(f"API batch {index} failed: {exc}", file=sys.stderr)
            print("  Falling back to direct arXiv source retrieval for this batch.", file=sys.stderr)
            direct_source_ids.update(batch)
            state["direct_source_ids"] = sorted(direct_source_ids)
            save_state(source_dir, state)

    downloaded = 0
    failed = set(state.get("failed_ids", []))
    failed.difference_update(unavailable_sources)
    pending = sorted(
        set(missing) & (available | direct_source_ids) - existing_ids(source_dir) - unavailable_sources,
        key=lambda item: (item in failed, item),
    )
    if args.limit is not None:
        pending = pending[: args.limit]
    for index, arxiv_id in enumerate(pending, start=1):
        destination = source_dir / directory_name(arxiv_id)
        if destination.exists() and any(destination.iterdir()):
            continue
        print(f"[{index}/{len(pending)}] Downloading {arxiv_id}", flush=True)
        try:
            payload = client.get("https://arxiv.org/src/" + urllib.parse.quote(arxiv_id, safe="/"))
            temporary = source_dir / f".{directory_name(arxiv_id)}.partial"
            shutil.rmtree(temporary, ignore_errors=True)
            unpack_source(payload, temporary)
            temporary.replace(destination)
            downloaded += 1
            failed.discard(arxiv_id)
        except (RuntimeError, OSError) as exc:
            shutil.rmtree(source_dir / f".{directory_name(arxiv_id)}.partial", ignore_errors=True)
            print(f"  failed: {exc}", file=sys.stderr)
            if "HTTP Error 403" in str(exc) or "HTTP Error 404" in str(exc):
                unavailable_sources.add(arxiv_id)
                failed.discard(arxiv_id)
            else:
                failed.add(arxiv_id)
        state["failed_ids"] = sorted(failed)
        state["unavailable_source_ids"] = sorted(unavailable_sources)
        save_state(source_dir, state)

    state["failed_ids"] = sorted(failed)
    state["direct_source_ids"] = sorted(direct_source_ids)
    state["unavailable_source_ids"] = sorted(unavailable_sources)
    save_state(source_dir, state)

    if unavailable:
        print("Not returned by the arXiv API: " + ", ".join(sorted(unavailable)), file=sys.stderr)
    if failed:
        print("Source downloads to retry: " + ", ".join(sorted(failed)), file=sys.stderr)
    if unavailable_sources:
        print("Source packages unavailable from arXiv: " + ", ".join(sorted(unavailable_sources)), file=sys.stderr)
    print(
        f"Downloaded: {downloaded}; API-unavailable: {len(unavailable)}; "
        f"direct-source fallback: {len(direct_source_ids)}; "
        f"source-unavailable: {len(unavailable_sources)}; failed: {len(failed)}"
    )
    return 0 if not unavailable and not unavailable_sources and not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
