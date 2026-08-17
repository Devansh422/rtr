"""Discover published documents on official sources, and emit an import-ready CSV.

    python -m backend.scripts.harvest_gov_sources --list
    python -m backend.scripts.harvest_gov_sources --source cic_annual_reports --out cic.csv
    python -m backend.scripts.import_research --file cic.csv --dry-run

WHAT THIS IS. A discovery step, not an importer. It reads an official index page,
finds the documents published on it, and writes the rows `import_research` takes.
Nothing reaches the database until a person has looked at the CSV and run the
importer, because the catalogue is a public claim about what a government
published and a parser that silently mis-reads a page should not be able to make
that claim unattended.

THREE RULES IT FOLLOWS, AND THE THIRD IS THE ONE THAT MATTERS.

1. **robots.txt is checked before every fetch**, with urllib's own parser, and a
   disallowed URL is skipped and reported. data.gov.in is `Disallow: /` for all
   agents -- so it is deliberately absent from the sources below, and its
   official API is the supported route to it instead (see --list).

2. **One request at a time, with a delay.** These are public bodies running
   modest infrastructure; a burst of parallel requests to a commission's website
   is a cost paid by everyone else trying to read it.

3. **It identifies itself honestly and never pretends to be a browser.** The
   User-Agent names the project and links to it. Some government sites refuse
   that and serve only a spoofed desktop browser string -- indiacode.nic.in is
   one, returning 403 to an honest agent and 302 to a fake Chrome. Those sites
   are NOT harvested. Setting a browser UA to get past a filter that exists to
   exclude automated clients is circumventing a stated preference, and a project
   whose whole argument is that institutions should be held to what they publish
   cannot also be the thing sneaking past their front door. Linking to such a
   document in a citation is fine; that is what a citation is.
"""

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse
import argparse
import csv
import html
import pathlib
import re
import sys
import time
import urllib.robotparser as robotparser

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

USER_AGENT = (
    "RightToRecallResearchBot/1.0 "
    "(+https://righttorecall.in; civic accountability research; contact via site)"
)

# Seconds between requests to the same host.
DELAY = 1.5

CSV_COLUMNS = [
    "title", "kind", "authors", "publisher", "published_on",
    "source_url", "licence", "language", "tags", "summary",
]


class Fetcher:
    """A polite, robots-respecting HTTP client."""

    def __init__(self, verbose: bool = True):
        import httpx

        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=40, follow_redirects=True
        )
        self.verbose = verbose
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._last_call: dict[str, float] = {}
        self.skipped: list[str] = []

    def allowed(self, url: str) -> bool:
        host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if host not in self._robots:
            parser = robotparser.RobotFileParser()
            try:
                response = self.client.get(f"{host}/robots.txt")
                parser.parse(response.text.splitlines() if response.status_code == 200 else [])
            except Exception:
                # No robots.txt served is not permission to hammer the site, but
                # it is not a prohibition either. Proceed at the same polite rate.
                parser.parse([])
            self._robots[host] = parser
        return self._robots[host].can_fetch(USER_AGENT, url)

    def get(self, url: str) -> Optional[str]:
        if not self.allowed(url):
            self.skipped.append(f"{url} (robots.txt disallows it)")
            if self.verbose:
                print(f"    SKIP (robots.txt): {url}")
            return None

        host = urlparse(url).netloc
        elapsed = time.monotonic() - self._last_call.get(host, 0)
        if elapsed < DELAY:
            time.sleep(DELAY - elapsed)
        self._last_call[host] = time.monotonic()

        response = self.client.get(url)
        if response.status_code == 403:
            # Rule 3. This is the site declining automated access, and the answer
            # is to stop rather than to disguise the client.
            self.skipped.append(
                f"{url} (403 to an honestly identified agent; not retried disguised)"
            )
            if self.verbose:
                print(f"    SKIP (403 to an honest agent): {url}")
            return None
        response.raise_for_status()
        return response.text

    def exists(self, url: str) -> bool:
        """HEAD check, so a dead link never reaches the catalogue."""
        if not self.allowed(url):
            return False
        try:
            return self.client.head(url).status_code == 200
        except Exception:
            return False


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    index_url: str
    harvest: Callable[[Fetcher], list[dict]]
    notes: str = ""


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()


# ==========================================================================
# Central Information Commission - annual reports
# ==========================================================================
def harvest_cic_annual_reports(fetcher: Fetcher) -> list[dict]:
    """The CIC's statutory annual reports under section 25 of the RTI Act.

    These are the closest thing India has to a national RTI dataset: each report
    carries, in its annexures, the applications received, disposed and rejected
    by every registered central public authority -- upwards of two thousand of
    them. It is the source most of the published "RTI rejection rate" figures
    are ultimately drawn from.

    Both language editions are catalogued. The Hindi edition is not a courtesy
    copy: it is the version most applicants in the Hindi belt will actually read.
    """
    index_url = "https://cic.gov.in/reports/annual-reports"
    page = fetcher.get(index_url)
    if page is None:
        return []

    rows = []
    for node, label in re.findall(
        r'<a href="(/node/\d+)" rel="bookmark"><span>([^<]+)</span>', page
    ):
        label = _text(label)
        years = re.search(r"(\d{4})-(\d{2,4})", label)
        if not years:
            continue
        start_year = int(years.group(1))

        detail = fetcher.get(urljoin(index_url, node))
        if detail is None:
            continue

        for href in re.findall(r'href="([^"]*/Reports/[^"]*\.pdf[^"]*)"', detail, re.I):
            url = urljoin(index_url, href)
            hindi = href.rstrip("/").upper().endswith("H.PDF")
            if not fetcher.exists(url):
                continue
            rows.append(
                {
                    "title": (
                        f"Central Information Commission Annual Report "
                        f"{years.group(0)}" + (" (Hindi)" if hindi else "")
                    ),
                    "kind": "committee_report",
                    "authors": "Central Information Commission",
                    "publisher": "Central Information Commission",
                    # The report covers a financial year and is published after
                    # it closes; dating it to 1 April of the closing year is
                    # honest without inventing a publication day.
                    "published_on": date(start_year + 1, 4, 1).isoformat(),
                    "source_url": url,
                    # Government work published for public use.
                    "licence": "gov_open",
                    "language": "hi" if hindi else "en",
                    "tags": "rti;statistics;annual report;public authorities;all india",
                    "summary": (
                        "Statutory annual report of the Central Information Commission under "
                        "section 25 of the Right to Information Act 2005. The annexures give "
                        "applications received, disposed, transferred and rejected by each "
                        "registered central public authority, which is the underlying source "
                        "for most published RTI rejection figures."
                    ),
                }
            )
    return rows


# ==========================================================================
# Satark Nagrik Sangathan - report cards on the Information Commissions
# ==========================================================================
def harvest_sns_report_cards(fetcher: Fetcher) -> list[dict]:
    """Annual assessments of every Information Commission, central and state.

    Not a government source, and catalogued as `linked_only` for that reason:
    these are SNS's own copyrighted reports, so the platform links to their PDF
    and hosts nothing. They are here because they are the only recurring
    published measure that covers ALL the state commissions on the same terms.
    """
    index_url = "https://www.snsindia.org/rti-assessments/"
    page = fetcher.get(index_url)
    if page is None:
        return []

    rows, seen = [], set()
    for href, label in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', page, re.S | re.I):
        url = urljoin(index_url, href)
        title = _text(label)
        if not title or url in seen or len(title) < 8:
            continue
        seen.add(url)
        year = re.search(r"(20\d{2})", title) or re.search(r"(20\d{2})", href)
        rows.append(
            {
                "title": title[:280],
                "kind": "report",
                "authors": "Satark Nagrik Sangathan",
                "publisher": "Satark Nagrik Sangathan",
                "published_on": f"{year.group(1)}-10-01" if year else "",
                "source_url": url,
                "licence": "linked_only",
                "language": "en",
                "tags": "rti;information commissions;all states;assessment",
                "summary": (
                    "Annual assessment of the central and state Information Commissions: "
                    "appeals and complaints registered and disposed, pending backlog, time "
                    "taken to dispose, and penalties imposed."
                ),
            }
        )
    return rows


SOURCES: dict[str, Source] = {
    s.key: s
    for s in (
        Source(
            key="cic_annual_reports",
            label="Central Information Commission - statutory annual reports",
            index_url="https://cic.gov.in/reports/annual-reports",
            harvest=harvest_cic_annual_reports,
            notes="Authority-wise RTI statistics for every central public authority. "
            "Official source, robots-permitted, serves an honest agent.",
        ),
        Source(
            key="sns_report_cards",
            label="Satark Nagrik Sangathan - Information Commission report cards",
            index_url="https://www.snsindia.org/rti-assessments/",
            harvest=harvest_sns_report_cards,
            notes="All state commissions on comparable measures. Catalogued as "
            "linked_only - their copyright, so link and host nothing.",
        ),
    )
}

# Official sources that are deliberately NOT harvested, and why. Kept in code so
# the next person does not spend an afternoon rediscovering it.
NOT_HARVESTED = {
    "data.gov.in": (
        "robots.txt is 'Disallow: /' for every agent. Use the official API at "
        "api.data.gov.in instead -- register on data.gov.in, generate a 32-character "
        "key from My Account, and pull the resource as JSON. That is the sanctioned "
        "route and it does not involve crawling."
    ),
    "indiacode.nic.in": (
        "Returns 403 to an honestly identified agent and 200 only to a spoofed "
        "browser string. That is the site declining automated access. Cite and link "
        "to it; do not harvest it."
    ),
    "eci.gov.in": (
        "Serves a plain client but 403s anything with a browser User-Agent, and "
        "blocks robots.txt itself, so its intent cannot be established. Results are "
        "published as downloadable files -- use those with import_representatives."
    ),
    "rtionline.gov.in / dsscic.nic.in": (
        "Filing portals behind authentication. They hold applications belonging to "
        "the citizens who filed them, not an open dataset."
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Harvest document catalogues from official sources into an import-ready CSV.",
        epilog="Writes a CSV for backend.scripts.import_research. Never writes to the database.",
    )
    parser.add_argument("--source", choices=sorted(SOURCES), help="which catalogue to harvest")
    parser.add_argument("--out", help="path to write the CSV to")
    parser.add_argument("--list", action="store_true", help="list sources, and what is excluded")
    args = parser.parse_args()

    if args.list or not args.source:
        print("Harvestable:\n")
        for source in SOURCES.values():
            print(f"  {source.key}\n    {source.label}\n    {source.index_url}\n    {source.notes}\n")
        print("Deliberately not harvested:\n")
        for host, reason in NOT_HARVESTED.items():
            print(f"  {host}\n    {reason}\n")
        return

    if not args.out:
        raise SystemExit("--out is required")

    source = SOURCES[args.source]
    print(f"Harvesting {source.label}\n  {source.index_url}\n")
    fetcher = Fetcher()
    rows = source.harvest(fetcher)

    if not rows:
        raise SystemExit("Nothing found. The page structure may have changed.")

    out = pathlib.Path(args.out)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n  {len(rows)} document(s) written to {out}")
    if fetcher.skipped:
        print(f"\n  skipped ({len(fetcher.skipped)}):")
        for line in fetcher.skipped[:10]:
            print(f"    - {line}")
    print(
        "\nNothing has been written to the database. Read the CSV, then:\n"
        f"  python -m backend.scripts.import_research --file {out} --dry-run"
    )


if __name__ == "__main__":
    main()
