#!/usr/bin/env python3
"""Fetch citation, star, upvote and download counts into data/metrics/latest.json and history/<date>.json.

Sources (public endpoints, no login): Semantic Scholar (citations, influential citations), OpenAlex (citation
fallback, institutions), Hugging Face papers (upvotes), GitHub (stars of linked code repos), Hugging Face models
(downloads in the last 30 days, likes). A value that fails to fetch keeps its previous value.
Optional env: S2_API_KEY, GITHUB_TOKEN, OPENALEX_MAILTO (raise rate limits); https_proxy / http_proxy are honored.
Usage: python3 scripts/fetch_metrics.py [--date YYYY-MM-DD]
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate as V  # noqa: E402
from build import gh_repo  # noqa: E402

UA = "awesome-loop-metrics (+https://github.com/sjy1203/awesome-loop)"
S2_BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch?fields=citationCount,influentialCitationCount"
METRICS = os.path.join(V.ROOT, "data", "metrics")


def get_json(url, data=None, headers=None, tries=4):
    """GET, or POST JSON when data is given. Retries 429/5xx and network errors with backoff; None on failure."""
    hdrs = {"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    body = None
    if data is not None:
        body, hdrs["Content-Type"] = json.dumps(data).encode(), "application/json"
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=hdrs), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404 or e.code not in (429, 500, 502, 503, 504) or i == tries - 1:
                if e.code != 404:
                    print(f"warn: {url}: HTTP {e.code}", file=sys.stderr)
                return None
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            if i == tries - 1:
                print(f"warn: {url}: {e}", file=sys.stderr)
                return None
        time.sleep(3 * 2 ** i)
    return None


def hf_model_repo(url):
    """owner/name for a huggingface.co model URL (not datasets, spaces or collections), else None."""
    prefix = "https://huggingface.co/"
    if not url.startswith(prefix):
        return None
    parts = url[len(prefix):].strip("/").split("/")
    if len(parts) < 2 or parts[0] in ("datasets", "spaces", "collections", "papers"):
        return None
    return f"{parts[0]}/{parts[1]}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", default=datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    args = ap.parse_args()
    data = V.load_all()
    papers = [e for _, e in data["paper"]]
    arxiv = sorted(p["id"] for p in papers if p["id"][:1].isdigit())
    repos = sorted({r for r in (gh_repo(p["links"].get("code")) for p in papers) if r})
    hf_repos = {r for _, m in data["model"] for r in m["hf"]}
    hf_repos |= {r for p in papers for u in p["links"].get("weights", []) for r in [hf_model_repo(u)] if r}

    prev_path = os.path.join(METRICS, "latest.json")
    prev = json.load(open(prev_path, encoding="utf-8")) if os.path.exists(prev_path) else {}
    out = {"date": args.date,
           "papers": {a: dict(prev.get("papers", {}).get(a, {})) for a in arxiv},
           "repos": {r: dict(prev.get("repos", {}).get(r, {})) for r in repos},
           "models": {r: dict(prev.get("models", {}).get(r, {})) for r in sorted(hf_repos)}}

    s2_headers = {"x-api-key": os.environ["S2_API_KEY"]} if os.environ.get("S2_API_KEY") else {}
    for i in range(0, len(arxiv), 500):
        chunk = arxiv[i:i + 500]
        res = get_json(S2_BATCH, data={"ids": [f"arXiv:{a}" for a in chunk]}, headers=s2_headers) or []
        for a, r in zip(chunk, res):
            if r and r.get("citationCount") is not None:
                out["papers"][a].update(citations=r["citationCount"], influential=r.get("influentialCitationCount"),
                                        citations_source="semanticscholar")

    mailto = os.environ.get("OPENALEX_MAILTO")

    def paper_extras(a):
        oa = get_json(f"https://api.openalex.org/works/doi:10.48550/arXiv.{a}" +
                      (f"?mailto={urllib.parse.quote(mailto)}" if mailto else ""))
        return a, oa, get_json(f"https://huggingface.co/api/papers/{a}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        extras = list(pool.map(paper_extras, arxiv))
    for a, oa, hf in extras:
        m = out["papers"][a]
        if oa:
            m["openalex_citations"] = oa.get("cited_by_count")
            if m.get("citations_source") != "semanticscholar" and oa.get("cited_by_count") is not None:
                m.update(citations=oa["cited_by_count"], citations_source="openalex")
            insts = []
            for au in oa.get("authorships", []):
                for inst in au.get("institutions", []):
                    if inst.get("display_name") and inst["display_name"] not in insts:
                        insts.append(inst["display_name"])
            if insts:
                m["institutions"] = insts
        if hf and hf.get("upvotes") is not None:
            m["hf_upvotes"] = hf["upvotes"]

    gh_headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        gh_headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        gh = list(pool.map(lambda r: (r, get_json(f"https://api.github.com/repos/{r}", headers=gh_headers)), repos))
        hfm = list(pool.map(lambda r: (r, get_json(f"https://huggingface.co/api/models/{r}")), sorted(hf_repos)))
    for r, res in gh:
        if res and res.get("stargazers_count") is not None:
            out["repos"][r] = {"stars": res["stargazers_count"], "pushed_at": res.get("pushed_at")}
    for r, res in hfm:
        if res:
            out["models"][r] = {"downloads": res.get("downloads", 0), "likes": res.get("likes", 0)}

    os.makedirs(os.path.join(METRICS, "history"), exist_ok=True)
    text = json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    for path in (prev_path, os.path.join(METRICS, "history", f"{args.date}.json")):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    missing = [a for a in arxiv if out["papers"][a].get("citations") is None]
    print(f"{len(arxiv)} papers ({len(missing)} without citations), {len(repos)} repos, {len(hf_repos)} HF models "
          f"-> data/metrics/latest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
