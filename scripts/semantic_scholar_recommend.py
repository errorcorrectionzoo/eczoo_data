#!/usr/bin/env python3
"""Fetch paper recommendations from Semantic Scholar for a given arXiv paper.

Uses the Semantic Scholar Recommendations API v1 with a single seed paper.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


RECOMMENDATIONS_BASE = "https://api.semanticscholar.org/recommendations/v1"
GRAPH_BASE = "https://api.semanticscholar.org/graph/v1"
DEFAULT_FIELDS = "title,authors,year,externalIds,citationCount,openAccessPdf,url"
DEFAULT_LIMIT = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Semantic Scholar paper recommendations for a given arXiv paper ID."
        )
    )
    parser.add_argument(
        "arxiv_id",
        help="arXiv paper ID (e.g. '2103.06474' or 'quant-ph/0605094').",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of recommendations to return (default: {DEFAULT_LIMIT}, max: 500).",
    )
    parser.add_argument(
        "--fields",
        default=DEFAULT_FIELDS,
        help=f"Comma-separated fields to return (default: {DEFAULT_FIELDS}).",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output raw JSON instead of formatted text.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Semantic Scholar API key (optional, increases rate limits).",
    )
    return parser.parse_args()


def make_request(
    url: str,
    *,
    api_key: str | None,
    data: bytes | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    req = urllib.request.Request(url, data=data)
    if api_key:
        req.add_header("x-api-key", api_key)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} error: {body}", file=sys.stderr)
        raise


def resolve_paper_id(arxiv_id: str, *, api_key: str | None) -> str:
    """Return the Semantic Scholar internal paper ID for an arXiv ID."""
    params = urllib.parse.urlencode({"fields": "paperId"})
    url = f"{GRAPH_BASE}/paper/ArXiv:{urllib.parse.quote(arxiv_id)}?{params}"
    data = make_request(url, api_key=api_key)
    return data["paperId"]


def fetch_recommendations(
    arxiv_id: str,
    *,
    limit: int,
    fields: str,
    api_key: str | None,
) -> dict[str, Any]:
    # POST endpoint accepts external IDs like "ArXiv:<id>" directly.
    params = urllib.parse.urlencode({"fields": fields, "limit": limit})
    url = f"{RECOMMENDATIONS_BASE}/papers/?{params}"
    body = json.dumps(
        {"positivePaperIds": [f"ArXiv:{arxiv_id}"], "negativePaperIds": []}
    ).encode("utf-8")
    return make_request(url, api_key=api_key, data=body, content_type="application/json")


def format_paper(paper: dict[str, Any], index: int) -> str:
    title = paper.get("title") or "(no title)"
    year = paper.get("year") or "?"
    citation_count = paper.get("citationCount")
    url = paper.get("url") or ""

    authors = paper.get("authors") or []
    author_str = ", ".join(a.get("name", "") for a in authors[:3])
    if len(authors) > 3:
        author_str += f" et al. ({len(authors)} total)"

    external_ids = paper.get("externalIds") or {}
    arxiv = external_ids.get("ArXiv")
    doi = external_ids.get("DOI")
    id_parts = []
    if arxiv:
        id_parts.append(f"arXiv:{arxiv}")
    if doi:
        id_parts.append(f"DOI:{doi}")
    id_str = "  |  ".join(id_parts) if id_parts else url

    pdf = paper.get("openAccessPdf")
    pdf_str = f"  [PDF: {pdf['url']}]" if pdf and pdf.get("url") else ""

    cite_str = f"  [cited {citation_count}x]" if citation_count is not None else ""

    lines = [
        f"{index}. {title} ({year}){cite_str}",
        f"   {author_str}",
        f"   {id_str}{pdf_str}",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    data = fetch_recommendations(
        args.arxiv_id,
        limit=args.limit,
        fields=args.fields,
        api_key=args.api_key,
    )

    if args.output_json:
        print(json.dumps(data, indent=2))
        return 0

    papers = data.get("recommendedPapers") or []
    if not papers:
        print("No recommendations returned.")
        return 0

    print(f"Recommendations for arXiv:{args.arxiv_id}  ({len(papers)} results)\n")
    for i, paper in enumerate(papers, start=1):
        print(format_paper(paper, i))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
