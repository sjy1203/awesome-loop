#!/usr/bin/env python3
"""Validate papers/, models/ and claims/ against schema/ and the cross-file rules.

Usage: python3 scripts/validate.py          (exit 1 and print every problem if anything is wrong)
Needs PyYAML and jsonschema.
"""
import datetime
import json
import os
import re
import sys

import jsonschema
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = {"papers": "paper", "models": "model", "claims": "claim"}
# Schema enum locations -> vocab section that must label every value.
ENUM_VOCAB = {
    ("paper", "category"): "category",
    ("paper", "facets", "placement"): "placement",
    ("paper", "facets", "sharing"): "sharing",
    ("paper", "facets", "depth_train"): "depth_train",
    ("paper", "facets", "depth_test"): "depth_test",
    ("paper", "facets", "injection"): "injection",
    ("paper", "facets", "kv"): "kv",
    ("paper", "facets", "gradient"): "gradient",
    ("paper", "facets", "origin"): "origin",
    ("paper", "facets", "ffn"): "ffn",
    ("paper", "facets", "attention"): "attention",
    ("paper", "budget", "baseline_tuned"): "baseline_tuned",
    ("paper", "status"): "status",
    ("paper", "$defs", "budget_items"): "budget_item",
    ("paper", "$defs", "repro"): "repro",
    ("model", "kv"): "kv",
    ("model", "inference"): "inference",
    ("claim", "status"): "claim_status",
    ("claim", "evidence", "stance"): "stance",
}


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return normalize(yaml.safe_load(f))


def normalize(obj):
    """Unquoted YAML dates become datetime.date; turn them back into ISO strings."""
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()[:10]
    return obj


def load_all():
    """{"paper": [(path, entry), ...], "model": [...], "claim": [...]}, sorted by file name."""
    out = {}
    for folder, kind in KINDS.items():
        d = os.path.join(ROOT, folder)
        names = sorted(n for n in os.listdir(d) if n.endswith(".yaml")) if os.path.isdir(d) else []
        out[kind] = []
        for n in names:
            try:
                entry = load_yaml(os.path.join(d, n))
            except yaml.YAMLError as e:  # reported by validate()
                entry = e
            out[kind].append((os.path.join(folder, n), entry))
    return out


def load_schemas():
    schemas = {}
    for kind in KINDS.values():
        with open(os.path.join(ROOT, "schema", f"{kind}.schema.json"), encoding="utf-8") as f:
            schemas[kind] = json.load(f)
    return schemas


def load_vocab():
    return load_yaml(os.path.join(ROOT, "schema", "vocab.yaml"))


def schema_enum(schemas, path):
    """Enum list at a path such as ("paper", "facets", "kv") or ("paper", "$defs", "repro")."""
    kind, *keys = path
    node = schemas[kind]
    in_defs = False
    for key in keys:
        if key == "$defs":
            node, in_defs = node["$defs"], True
            continue
        if not in_defs:
            node = node.get("items", node).get("properties", {})
        node, in_defs = node.get(key, {}), False
    return node.get("items", node).get("enum")


def check_vocab(schemas, vocab, errors):
    for path, section in ENUM_VOCAB.items():
        values = schema_enum(schemas, path)
        if not values:
            errors.append(f"schema: no enum found at {'/'.join(path)}")
            continue
        labels = vocab.get(section, {})
        for v in values:
            if v not in labels:
                errors.append(f"schema/vocab.yaml: [{section}] has no label for '{v}'")
            elif "en" not in labels[v] or "zh" not in labels[v]:
                errors.append(f"schema/vocab.yaml: [{section}] '{v}' needs both en and zh labels")


CJK_SPACE = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef] [\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")


def walk_textlists(obj, where, errors, path):
    """Bilingual lists must have the same number of items in both languages; Chinese text must not contain a space
    between two Chinese characters (usually a YAML line fold: keep zh text on one line)."""
    if isinstance(obj, dict):
        if set(obj) >= {"en", "zh"} and isinstance(obj["en"], list) and isinstance(obj["zh"], list):
            if len(obj["en"]) != len(obj["zh"]):
                errors.append(f"{where}: {path or '/'} has {len(obj['en'])} en items but {len(obj['zh'])} zh items")
        zh = obj.get("zh")
        for text in (zh if isinstance(zh, list) else [zh]):
            m = CJK_SPACE.search(text) if isinstance(text, str) else None
            if m:
                errors.append(f"{where}: {path}/zh has a space between Chinese characters near '{m.group(0)}'")
        for k, v in obj.items():
            walk_textlists(v, where, errors, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_textlists(v, where, errors, f"{path}/{i}")


def validate(data=None):
    """Return a list of problems (empty when everything is valid)."""
    errors = []
    schemas, vocab = load_schemas(), load_vocab()
    check_vocab(schemas, vocab, errors)
    data = data or load_all()
    for kind, entries in data.items():
        validator = jsonschema.Draft202012Validator(schemas[kind])
        seen = set()
        for path, entry in entries:
            if isinstance(entry, yaml.YAMLError):
                errors.append(f"{path}: YAML syntax error: {' '.join(str(entry).split())}")
                continue
            if not isinstance(entry, dict):
                errors.append(f"{path}: not a mapping")
                continue
            for err in sorted(validator.iter_errors(entry), key=lambda e: list(e.absolute_path)):
                loc = "/".join(str(p) for p in err.absolute_path) or "/"
                errors.append(f"{path}: {loc}: {err.message}")
            eid = entry.get("id")
            stem = os.path.basename(path)[:-5]
            if isinstance(eid, str) and eid != stem:
                errors.append(f"{path}: id '{eid}' must equal the file name '{stem}' (quote numeric ids)")
            if eid in seen:
                errors.append(f"{path}: duplicate id '{eid}'")
            seen.add(eid)
            walk_textlists(entry, path, errors, "")
    data = {k: [(path, e) for path, e in v if isinstance(e, dict)] for k, v in data.items()}
    papers = {e.get("id"): e for _, e in data["paper"]}
    for path, p in data["paper"]:
        pid = p.get("id", "")
        if isinstance(pid, str) and pid[:1].isdigit():
            want = f"https://arxiv.org/abs/{pid}"
            if p.get("links", {}).get("paper") != want:
                errors.append(f"{path}: links.paper must be {want}")
        segs = p.get("loop", {}).get("segments", [])
        if segs and not any(s.get("role") == "core" for s in segs):
            errors.append(f"{path}: loop.segments needs at least one core segment")
    for path, m in data["model"]:
        if m.get("paper") not in papers:
            errors.append(f"{path}: paper '{m.get('paper')}' is not in papers/")
    for path, c in data["claim"]:
        for i, ev in enumerate(c.get("evidence", [])):
            if ev.get("paper") not in papers:
                errors.append(f"{path}: evidence/{i} paper '{ev.get('paper')}' is not in papers/")
    return errors


def main():
    errors = validate()
    for e in errors:
        print(e)
    if errors:
        print(f"{len(errors)} problem(s)")
        return 1
    data = load_all()
    print("ok: " + ", ".join(f"{len(v)} {k}s" for k, v in data.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
