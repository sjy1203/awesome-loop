#!/usr/bin/env python3
"""Find new arXiv papers on looped / recurrent-depth models and queue them in data/candidates.json for triage.

Sources: the arXiv API (phrase search in titles and abstracts) and Semantic Scholar papers that cite the seed
papers (best effort; this API is often rate-limited without a key). Papers already in papers/ or listed in
data/rejected.txt are skipped; candidates already queued are kept until they are triaged.
Optional env: S2_API_KEY; https_proxy / http_proxy are honored.
Usage: python3 scripts/discover.py [--days 14] [--max 300] [--no-citations]
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
import validate as V  # noqa: E402
from fetch_metrics import get_json  # noqa: E402

PHRASES = ["looped transformer", "looped transformers", "looped language model", "looped language models",
           "looped model", "looped models", "recurrent depth", "recurrent-depth", "depth recurrence",
           "depth-recurrent", "recursive transformer", "recursive transformers", "universal transformer",
           "universal transformers", "layer looping", "weight-tied layers", "latent recurrence"]
SEEDS = {"1807.03819": "Universal Transformers", "2502.05171": "Huginn", "2507.10524": "MoR",
         "2510.25741": "Ouro"}
ATOM = {"a": "http://www.w3.org/2005/Atom"}
CANDIDATES = os.path.join(V.ROOT, "data", "candidates.json")
REJECTED = os.path.join(V.ROOT, "data", "rejected.txt")


def arxiv_search(max_results):
    query = " OR ".join(f'{field}:"{p}"' for p in PHRASES for field in ("ti", "abs"))
    url = ("https://export.arxiv.org/api/query?" +
           urllib.parse.urlencode({"search_query": query, "sortBy": "submittedDate", "sortOrder": "descending",
                                   "max_results": max_results}))
    req = urllib.request.Request(url, headers={"User-Agent": "awesome-loop-discover"})
    with urllib.request.urlopen(req, timeout=120) as r:
        root = ET.fromstring(r.read())
    out = []
    for e in root.findall("a:entry", ATOM):
        aid = re.sub(r"v\d+$", "", e.findtext("a:id", "", ATOM).rsplit("/abs/", 1)[-1])
        title = " ".join(e.findtext("a:title", "", ATOM).split())
        abstract = " ".join(e.findtext("a:summary", "", ATOM).split())
        text = f"{title} {abstract}".lower()
        out.append({"id": aid, "title": title, "date": e.findtext("a:published", "", ATOM)[:10],
                    "authors": [a.findtext("a:name", "", ATOM) for a in e.findall("a:author", ATOM)][:6],
                    "url": f"https://arxiv.org/abs/{aid}", "terms": [p for p in PHRASES if p in text],
                    "abstract": abstract[:500]})
    return out


def citing_seeds(since):
    """{arxiv id: {"title", "date", "seeds": [...]}} for papers citing any seed paper, published on/after since."""
    headers = {"x-api-key": os.environ["S2_API_KEY"]} if os.environ.get("S2_API_KEY") else {}
    hits = {}
    for seed, name in SEEDS.items():
        url = (f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{seed}/citations"
               "?fields=externalIds,title,publicationDate&limit=1000")
        res = get_json(url, headers=headers, tries=3) or {}
        for item in res.get("data", []):
            p = item.get("citingPaper") or {}
            aid = (p.get("externalIds") or {}).get("ArXiv")
            date = p.get("publicationDate") or ""
            if aid and date >= since:
                hit = hits.setdefault(aid, {"title": p.get("title", ""), "date": date, "seeds": []})
                hit["seeds"].append(name)
        time.sleep(1)
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=14, help="only papers first published in the last N days")
    ap.add_argument("--max", type=int, default=300, help="arXiv results to scan (newest first)")
    ap.add_argument("--no-citations", action="store_true", help="skip the Semantic Scholar citation search")
    args = ap.parse_args()
    today = datetime.datetime.now(datetime.timezone.utc).date()
    since = (today - datetime.timedelta(days=args.days)).isoformat()
    known = {e["id"] for _, e in V.load_all()["paper"]}
    rejected = set()
    if os.path.exists(REJECTED):
        for ln in open(REJECTED, encoding="utf-8"):
            ln = ln.split("#", 1)[0].strip()
            if ln:
                rejected.add(ln)
    queue, old = {}, None
    if os.path.exists(CANDIDATES):
        old = json.load(open(CANDIDATES, encoding="utf-8"))["candidates"]
        queue = {c["id"]: c for c in old}
    found = [c for c in arxiv_search(args.max) if c["date"] >= since and c["terms"]]
    cites = {} if args.no_citations else citing_seeds(since)
    for c in found:
        c["cites_seeds"] = cites.pop(c["id"], {}).get("seeds", [])
        queue.setdefault(c["id"], c)
    for aid, hit in cites.items():  # cite a seed paper but matched no phrase
        queue.setdefault(aid, {"id": aid, "title": hit["title"], "date": hit["date"], "authors": [],
                               "url": f"https://arxiv.org/abs/{aid}", "terms": [], "abstract": "",
                               "cites_seeds": hit["seeds"]})
    pending = sorted((c for c in queue.values() if c["id"] not in known | rejected),
                     key=lambda c: (c["date"], c["id"]), reverse=True)
    if pending != old:  # keep the file (and its date) untouched when nothing changed
        os.makedirs(os.path.dirname(CANDIDATES), exist_ok=True)
        with open(CANDIDATES, "w", encoding="utf-8") as f:
            f.write(json.dumps({"updated": today.isoformat(), "candidates": pending}, ensure_ascii=False,
                               indent=1) + "\n")
    print(f"{len(found)} arXiv matches and {len(cites)} citation-only hits since {since}; "
          f"{len(pending)} candidates pending -> data/candidates.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
