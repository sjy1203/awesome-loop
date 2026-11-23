#!/usr/bin/env python3
"""Count arXiv papers per quarter whose title or abstract contains a loop phrase; write data/trend.json.

The phrases are the ones scripts/discover.py searches for. The script pages through every arXiv API match (newest
first), keeps papers whose title or abstract really contains a phrase, and bins them by the quarter of their first
version. It is a keyword proxy for activity in the field, not a curated count. The current quarter is marked partial.
https_proxy / http_proxy are honored.
Usage: python3 scripts/trend.py [--start-year 2018]
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from discover import PHRASES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "trend.json")
QUARTER_START = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
NS = {"a": "http://www.w3.org/2005/Atom", "os": "http://a9.com/-/spec/opensearch/1.1/"}


def quarter_bounds(year, q):
    start = datetime.date(year, *QUARTER_START[q])
    nxt = datetime.date(year + (q == 4), *QUARTER_START[q % 4 + 1])
    return start, nxt - datetime.timedelta(days=1)


def fetch_dates(page=1000, tries=5):
    """First-version dates of all phrase matches, via the same query as scripts/discover.py."""
    terms = " OR ".join(f'{field}:"{p}"' for p in PHRASES for field in ("ti", "abs"))
    dates, offset, total = {}, 0, None
    while total is None or offset < total:
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": terms, "sortBy": "submittedDate", "sortOrder": "descending", "start": offset,
             "max_results": page})
        for i in range(tries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "awesome-loop-trend"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    root = ET.fromstring(r.read())
                break
            except (OSError, ET.ParseError) as e:
                print(f"warn: offset {offset}: {e}", file=sys.stderr)
                time.sleep(10 * (i + 1))
        else:
            raise RuntimeError(f"arXiv API failed at offset {offset}")
        total = int(root.findtext("os:totalResults", "0", NS))
        entries = root.findall("a:entry", NS)
        if not entries:
            break
        for e in entries:
            aid = re.sub(r"v\d+$", "", e.findtext("a:id", "", NS).rsplit("/abs/", 1)[-1])
            text = (e.findtext("a:title", "", NS) + " " + e.findtext("a:summary", "", NS)).lower()
            if any(p in " ".join(text.split()) for p in PHRASES):
                dates[aid] = e.findtext("a:published", "", NS)[:10]
        offset += len(entries)
        time.sleep(4)  # arXiv API etiquette
    return dates


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start-year", type=int, default=2018)
    args = ap.parse_args()
    today = datetime.datetime.now(datetime.timezone.utc).date()
    dates = list(fetch_dates().values())
    bins = []
    for year in range(args.start_year, today.year + 1):
        for q in range(1, 5):
            start, end = quarter_bounds(year, q)
            if start > today:
                break
            n = sum(start.isoformat() <= d <= end.isoformat() for d in dates)
            bins.append({"period": f"{year}Q{q}", "start": start.isoformat(), "end": end.isoformat(), "count": n,
                         "partial": end >= today})
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": "arXiv API, phrase search in titles and abstracts", "phrases": PHRASES,
                   "generated": today.isoformat(), "bins": bins}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{len(bins)} quarters -> data/trend.json; last: {bins[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
