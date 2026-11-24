#!/usr/bin/env python3
"""Fetch citation, star, upvote and download counts into data/metrics/latest.json and history/<date>.json.

Sources (public APIs, no login): Semantic Scholar (citations, influential citations), OpenAlex (citations,
institutions), Hugging Face papers (upvotes), GitHub (stars of linked code repos), Hugging Face models
(downloads in the last 30 days, likes), Hacker News search by Algolia (points of stories linking the paper).
When the GitHub API refuses a repo (rate limit), its star count from the Hugging Face paper page is used instead.
`citations` is the higher of the Semantic Scholar and OpenAlex counts. A value that fails to fetch keeps its
previous value. A history snapshot is written when the newest one is at least 7 days old, so a daily run keeps one
snapshot per week.
Optional env: S2_API_KEY, GITHUB_TOKEN, OPENALEX_API_KEY, OPENALEX_MAILTO (raise rate limits; without a key, OpenAlex
shares a small daily budget among everyone on the same IP); https_proxy / http_proxy are honored.
Usage: python3 scripts/fetch_metrics.py [--date YYYY-MM-DD]
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate as V  # noqa: E402
from build import gh_repo, hf_model_repo  # noqa: E402

UA = "awesome-loop-metrics (+https://github.com/sjy1203/awesome-loop)"
S2_BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch?fields=citationCount,influentialCitationCount"
HN_SEARCH = "https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=50&restrictSearchableAttributes=url&query="
METRICS = os.path.join(V.ROOT, "data", "metrics")


def redact(url):
    return re.sub(r"api_key=[^&]+", "api_key=***", url)


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
                    print(f"warn: {redact(url)}: HTTP {e.code}", file=sys.stderr)
                return None
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            if i == tries - 1:
                print(f"warn: {redact(url)}: {e}", file=sys.stderr)
                return None
        time.sleep(3 * 2 ** i)
    return None


def norm_url(url):
    """URL without scheme, www., query, fragment or trailing slash, lowercased, for exact comparison."""
    u = url.lower().split("#")[0].split("?")[0].split("://", 1)[-1]
    return (u[4:] if u.startswith("www.") else u).rstrip("/")


def hn_points(p):
    """Total points of Hacker News stories linking the paper: any URL with its arXiv id, else its exact page URL."""
    pid = p["id"]
    if pid[:1].isdigit():
        pat = re.compile(rf"(?<![\d.]){re.escape(pid)}(?!\d)")
        query, match = pid, lambda url: bool(pat.search(url))
    else:
        target = norm_url(p["links"]["paper"])
        query, match = target, lambda url: norm_url(url) == target
    res = get_json(HN_SEARCH + urllib.parse.quote(query))
    if res is None:
        return None
    return sum(h.get("points") or 0 for h in res.get("hits", []) if h.get("url") and match(h["url"]))


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
    ids = sorted(p["id"] for p in papers)
    out = {"date": args.date,
           "papers": {i: dict(prev.get("papers", {}).get(i, {})) for i in ids},
           "repos": {r: dict(prev.get("repos", {}).get(r, {})) for r in repos},
           "models": {r: dict(prev.get("models", {}).get(r, {})) for r in sorted(hf_repos)}}

    s2_headers = {"x-api-key": os.environ["S2_API_KEY"]} if os.environ.get("S2_API_KEY") else {}
    for i in range(0, len(arxiv), 500):
        chunk = arxiv[i:i + 500]
        res = get_json(S2_BATCH, data={"ids": [f"arXiv:{a}" for a in chunk]}, headers=s2_headers) or []
        for a, r in zip(chunk, res):
            if r and r.get("citationCount") is not None:
                out["papers"][a].update(s2_citations=r["citationCount"], influential=r.get("influentialCitationCount"))

    oa_env = (("mailto", "OPENALEX_MAILTO"), ("api_key", "OPENALEX_API_KEY"))
    oa_params = urllib.parse.urlencode({k: os.environ[v] for k, v in oa_env if os.environ.get(v)})

    def paper_extras(a):
        oa = get_json(f"https://api.openalex.org/works/doi:10.48550/arXiv.{a}" + (f"?{oa_params}" if oa_params else ""))
        return a, oa, get_json(f"https://huggingface.co/api/papers/{a}")

    hf_stars = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        extras = list(pool.map(paper_extras, arxiv))
    for a, oa, hf in extras:
        m = out["papers"][a]
        if oa:
            if oa.get("cited_by_count") is not None:
                m["openalex_citations"] = oa["cited_by_count"]
            insts = []
            for au in oa.get("authorships", []):
                for inst in au.get("institutions", []):
                    if inst.get("display_name") and inst["display_name"] not in insts:
                        insts.append(inst["display_name"])
            if insts:
                m["institutions"] = insts
        if hf and hf.get("upvotes") is not None:
            m["hf_upvotes"] = hf["upvotes"]
        if hf and hf.get("githubRepo") and hf.get("githubStars") is not None and gh_repo(hf["githubRepo"].rstrip("/")):
            hf_stars[gh_repo(hf["githubRepo"].rstrip("/")).lower()] = hf["githubStars"]
        # The two indexes sometimes split a paper into several records; the higher count is the better-merged one.
        counts = [(m[k], src) for k, src in (("s2_citations", "semanticscholar"), ("openalex_citations", "openalex"))
                  if m.get(k) is not None]
        if counts:
            m["citations"], m["citations_source"] = max(counts, key=lambda c: c[0])

    gh_headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        gh_headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        gh = list(pool.map(lambda r: (r, get_json(f"https://api.github.com/repos/{r}", headers=gh_headers)), repos))
        hfm = list(pool.map(lambda r: (r, get_json(f"https://huggingface.co/api/models/{r}")), sorted(hf_repos)))
        hn = list(pool.map(lambda p: (p["id"], hn_points(p)), papers))
    for r, res in gh:
        if res and res.get("stargazers_count") is not None:
            out["repos"][r] = {"stars": res["stargazers_count"], "pushed_at": res.get("pushed_at")}
        elif r.lower() in hf_stars:  # GitHub API refused (rate limit): Hugging Face's copy of the same repo's count
            out["repos"][r] = {"stars": hf_stars[r.lower()], "stars_source": "huggingface"}
    for r, res in hfm:
        if res:
            out["models"][r] = {"downloads": res.get("downloads", 0), "likes": res.get("likes", 0)}
    for pid, points in hn:
        if points is not None:
            out["papers"][pid]["hn_points"] = points

    hist = os.path.join(METRICS, "history")
    os.makedirs(hist, exist_ok=True)
    snaps = sorted(n[:-5] for n in os.listdir(hist) if n.endswith(".json"))
    week_ago = (datetime.date.fromisoformat(args.date) - datetime.timedelta(days=7)).isoformat()
    paths = [prev_path]
    if not snaps or snaps[-1] <= week_ago or snaps[-1] == args.date:
        paths.append(os.path.join(hist, f"{args.date}.json"))
    text = json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    for path in paths:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    missing = [a for a in arxiv if out["papers"][a].get("citations") is None]
    print(f"{len(papers)} papers ({len(arxiv)} on arXiv, {len(missing)} of them without citations), "
          f"{len(repos)} repos, {len(hf_repos)} HF models -> {', '.join(os.path.relpath(p, V.ROOT) for p in paths)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
