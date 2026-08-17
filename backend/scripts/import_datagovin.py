"""Catalogue datasets from data.gov.in through its official API.

    export DATA_GOV_IN_API_KEY=<your 32-character key>
    python -m backend.scripts.import_datagovin --resource 9ef84268-d588-465a-a308-a864a43d0070 --dry-run
    python -m backend.scripts.import_datagovin --resources ids.txt --out datagovin.csv

WHY THE API AND NOT THE WEBSITE. data.gov.in serves `robots.txt: Disallow: /`
to every agent, so crawling the portal is off the table. The API is the route
the platform itself publishes for automated access, which is why this exists as
a separate script from harvest_gov_sources.py -- that one reads HTML from sites
that permit it; this one calls a sanctioned API and never touches the portal.

WHAT IT WRITES. One catalogue entry per dataset, not the rows inside it. The
platform's Research Centre holds documents with citations, and a dataset's
citation is its resource page; there is no table here for arbitrary government
tables and inventing one to hold a few thousand crop-price rows would be a
schema built for a demo rather than for a reader. The entry records what the
dataset is, who publishes it, how many records it has and what its columns are,
which is what someone deciding whether to go and use it needs.

ABOUT THE KEY. `579b464db66ec23bdd000001...` is the sample key printed in
data.gov.in's own documentation and reproduced in every tutorial about it. It
works, but the quota is shared with everyone else who copied it, so it rate
limits and 502s under load. Generate your own: log in at data.gov.in, open My
Account, and use "Generate Your New API KEY". The script warns when it sees the
sample prefix.

THE UPSTREAM IS UNRELIABLE, which is a fact about the service rather than a
complaint: it answers, then returns 502 for minutes at a time. Every call is
retried with exponential backoff, and a resource that never answers is reported
rather than silently omitted -- a catalogue that quietly lost half its entries
to a transient gateway error is worse than one that says what it could not read.
"""

from dataclasses import dataclass, field as dataclass_field
from typing import Optional
import argparse
import asyncio
import csv
import os
import pathlib
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core import config, db as database  # noqa: E402

API_ROOT = "https://api.data.gov.in/resource"
PORTAL_RESOURCE = "https://www.data.gov.in/resource"

SAMPLE_KEY_PREFIX = "579b464db66ec23bdd000001"

CSV_COLUMNS = [
    "title", "kind", "authors", "publisher", "published_on",
    "source_url", "licence", "language", "tags", "summary",
]

MAX_ATTEMPTS = 5
BASE_DELAY = 3.0


@dataclass
class Outcome:
    rows: list[dict] = dataclass_field(default_factory=list)
    failed: list[str] = dataclass_field(default_factory=list)


def _client():
    import httpx

    return httpx.Client(
        timeout=90,
        follow_redirects=True,
        headers={"User-Agent": "RightToRecallResearchBot/1.0 (+https://righttorecall.in)"},
    )


def fetch_metadata(client, resource_id: str, api_key: str, verbose: bool = True) -> Optional[dict]:
    """One resource's metadata, or None if the API never answered.

    `limit=1` deliberately: this catalogues the dataset, so one record is enough
    to confirm it is live and to read the field list off the envelope. Pulling
    the whole table to write one summary row would be rude to a service that is
    already struggling.
    """
    url = f"{API_ROOT}/{resource_id}?api-key={api_key}&format=json&limit=1"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.get(url)
            if response.status_code == 200 and response.content.strip().startswith(b"{"):
                return response.json()
            if response.status_code in (401, 403):
                raise SystemExit(
                    f"The API rejected the key ({response.status_code}). Generate one at "
                    "data.gov.in -> My Account -> Generate Your New API KEY."
                )
            reason = f"HTTP {response.status_code}"
        except SystemExit:
            raise
        except Exception as error:  # network flake, malformed body
            reason = type(error).__name__

        if attempt < MAX_ATTEMPTS:
            delay = BASE_DELAY * (2 ** (attempt - 1))
            if verbose:
                print(f"    {resource_id[:8]}… {reason}, retrying in {delay:.0f}s "
                      f"({attempt}/{MAX_ATTEMPTS})")
            time.sleep(delay)
        elif verbose:
            print(f"    {resource_id[:8]}… gave up after {MAX_ATTEMPTS} attempts ({reason})")
    return None


def to_row(resource_id: str, payload: dict) -> dict:
    """Turn the API envelope into a catalogue entry."""
    title = (payload.get("title") or "").strip() or f"data.gov.in resource {resource_id}"
    org = payload.get("org")
    if isinstance(org, list):
        org = ", ".join(str(o) for o in org if o)
    org = (org or "").strip()

    sector = payload.get("sector")
    if isinstance(sector, list):
        sector = ";".join(str(s) for s in sector if s)

    fields = [f.get("name") for f in (payload.get("field") or []) if isinstance(f, dict)]
    total = payload.get("total")
    updated = (payload.get("updated_date") or "")[:10]

    description = (payload.get("desc") or "").strip()
    summary_parts = []
    if description:
        summary_parts.append(description)
    if total is not None:
        summary_parts.append(f"{total} records.")
    if fields:
        summary_parts.append("Columns: " + ", ".join(fields[:12]) + ("…" if len(fields) > 12 else "") + ".")
    summary_parts.append("Catalogued from the data.gov.in API; the rows stay at the source.")

    return {
        "title": title[:280],
        "kind": "dataset",
        "authors": org,
        # Government open data, published for reuse.
        "publisher": org or "Open Government Data Platform India",
        "published_on": updated,
        # The human-readable resource page, not the API call: the API URL carries
        # a key, and a citation that leaks a credential is not a citation.
        "source_url": f"{PORTAL_RESOURCE}/{resource_id}",
        "licence": "gov_open",
        "language": "en",
        "tags": ";".join(filter(None, ["open data", "data.gov.in", sector or ""]))[:240],
        "summary": " ".join(summary_parts)[:1400],
    }


def collect(resource_ids: list[str], api_key: str) -> Outcome:
    outcome = Outcome()
    with _client() as client:
        for resource_id in resource_ids:
            print(f"  fetching {resource_id}")
            payload = fetch_metadata(client, resource_id, api_key)
            if payload is None:
                outcome.failed.append(resource_id)
                continue
            row = to_row(resource_id, payload)
            outcome.rows.append(row)
            print(f"    -> {row['title'][:70]}")
    return outcome


async def _import(rows: list[dict], publish: bool, dry_run: bool) -> None:
    from backend.scripts.import_research import import_documents

    async with database.transaction() as session:
        result = await import_documents(session, rows, publish=publish)
        if dry_run:
            await session.rollback()
    for key, value in result.as_dict().items():
        print(f"  {key:34} {value}")
    for line in result.rejected[:10]:
        print(f"    rejected: {line}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Catalogue data.gov.in datasets through the official API.",
        epilog="Needs DATA_GOV_IN_API_KEY, or --api-key.",
    )
    parser.add_argument("--resource", action="append", default=[], help="resource id (repeatable)")
    parser.add_argument("--resources", help="file with one resource id per line")
    parser.add_argument("--api-key", help="overrides DATA_GOV_IN_API_KEY")
    parser.add_argument("--out", help="write the catalogue to CSV instead of importing")
    parser.add_argument("--publish", action="store_true", help="publish what is imported")
    parser.add_argument("--dry-run", action="store_true", help="report what would change")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("DATA_GOV_IN_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "No API key. Set DATA_GOV_IN_API_KEY or pass --api-key.\n"
            "Get one: data.gov.in -> log in -> My Account -> Generate Your New API KEY."
        )
    if api_key.startswith(SAMPLE_KEY_PREFIX):
        print(
            "NOTE: this is the sample key from data.gov.in's own documentation. It works,\n"
            "      but its quota is shared with every tutorial that copied it, so expect\n"
            "      rate limiting and 502s. Generate your own from My Account.\n"
        )

    resource_ids = list(args.resource)
    if args.resources:
        resource_ids += [
            line.strip()
            for line in pathlib.Path(args.resources).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    if not resource_ids:
        raise SystemExit("Give at least one --resource or a --resources file.")

    outcome = collect(resource_ids, api_key)

    print(f"\n  catalogued: {len(outcome.rows)} / {len(resource_ids)}")
    if outcome.failed:
        print(f"  the API never answered for {len(outcome.failed)}: {', '.join(outcome.failed)}")
        print("  (data.gov.in returns 502 for minutes at a time; re-run to pick them up)")

    if not outcome.rows:
        raise SystemExit("\nNothing to import.")

    if args.out:
        out = pathlib.Path(args.out)
        with out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(outcome.rows)
        print(f"\n  written to {out}")
        return

    if not config.postgres_enabled():
        raise SystemExit("DATABASE_URL is not set; there is nothing to import into.")

    print()
    asyncio.run(_import(outcome.rows, args.publish, args.dry_run))
    asyncio.run(database.dispose())


if __name__ == "__main__":
    main()
