#!/usr/bin/env python3
"""Freeze the frontier and anchor tables of a spec version, so that scores stay recomputable after later updates.

    python3 bench/freeze_frontier.py --version v1          # writes bench/frontiers/v1.json from the current code
    python3 bench/report.py --tier A3 --spec v1 ...        # scores against that frozen table (default: newest file)

The file lists, for every instance that has a reference (all tiers found in bench/refs), the published human value
(`known_best`, or null), whether it is cited rather than re-verified, and the anchor (value, kind).  When a version is
loaded, `openceiling.known_best` and `openceiling.anchor` answer from the file instead of the code.
Optional verified offline constructions also come from this snapshot. Published scoring snapshots
retain their reference values so that later evaluations remain comparable."""
import argparse, glob, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
import openceiling as O  # noqa: E402

DIR = os.path.join(ROOT, "bench", "frontiers")


def derive_core(source="v1", target="v1-core"):
    """Preserve the source snapshot and derive the core-family view with the Kakeya bound correction."""
    import hashlib
    from copy import deepcopy
    source_path = os.path.join(DIR, f"{source}.json")
    raw = open(source_path, "rb").read()
    data = deepcopy(json.loads(raw))
    changed = []
    for key_, entry in data["entries"].items():
        if entry["family"] == "kakeya":
            old = entry["anchor"]
            new = O.FAMILIES["kakeya"].upper(entry["params"])
            entry["anchor"] = new
            entry["anchor_kind"] = "bound"
            if old != new:
                changed.append({"key": key_, "old": old, "new": new})
    data.update(version=target, publication_version="version 1", selection="core",
                derived_from=source, source_sha256=hashlib.sha256(raw).hexdigest(),
                change_note="Bukh-Chao (2021), Theorem 1; Kakeya is now a control. All published frontiers preserved.",
                changed_anchors=changed)
    out = os.path.join(DIR, f"{target}.json")
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"
    if os.path.exists(out) and open(out).read() != text:
        raise ValueError(f"Refusing to overwrite a different snapshot: {out}")
    open(out, "w").write(text)
    return data


def derive_codes(source="v1-core", target="v1-codes"):
    """Extend an immutable snapshot with admitted code-family A3 references only."""
    import hashlib
    source_path = os.path.join(DIR, f"{source}.json")
    raw = open(source_path,"rb").read(); data=json.loads(raw)
    additions=[]
    for fam in ("shannon","trifference"):
        for path in sorted(glob.glob(os.path.join(ROOT,"bench","refs",f"A3-{fam}-*-t10.json"))):
            ref=json.load(open(path));p=ref["params"];F=O.FAMILIES[fam];k=key(fam,p)
            if k in data["entries"]:raise ValueError(f"entry already frozen: {k}")
            a,kind=O.anchor(F,p)
            data["entries"][k]={"family":fam,"params":p,"known_best":None,"cited":False,"anchor":a,"anchor_kind":kind,
                                "reference_sha256":hashlib.sha256(open(path,"rb").read()).hexdigest()}
            additions.append(k)
    if len(additions)!=8:raise ValueError("expected eight admitted code instances")
    data.update(version=target,publication_version="version 1",selection="core",derived_from=source,
                source_sha256=hashlib.sha256(raw).hexdigest(),added_instances=additions,
                change_note="Add Shannon and trifference; all existing entries preserved. New denominators are verified construction stand-ins.")
    out=os.path.join(DIR,f"{target}.json");text=json.dumps(data,indent=1,sort_keys=True)+"\n"
    if os.path.exists(out) and open(out).read()!=text:raise ValueError(f"Refusing to overwrite different snapshot: {out}")
    open(out,"w").write(text)
    return data


def derive_trifference(source="v1-codes", target="v1-trifference"):
    """Add certified-scale instances while retaining every frozen A3 entry."""
    import hashlib
    source_path=os.path.join(DIR,f"{source}.json");raw=open(source_path,"rb").read();data=json.loads(raw)
    added=[]
    for tier in ("T1","T2","T3","T4"):
        path=os.path.join(ROOT,"bench","refs",f"{tier}-trifference-0-t10.json")
        r=json.load(open(path));p=r["params"];k=key("trifference",p)
        if k in data["entries"]:raise ValueError("instance already frozen")
        b,kind=O.anchor(O.FAMILIES["trifference"],p)
        data["entries"][k]={"family":"trifference","params":p,"known_best":None,"cited":False,
                            "anchor":b,"anchor_kind":kind,"reference_sha256":hashlib.sha256(open(path,"rb").read()).hexdigest()}
        added.append(k)
    data.update(version=target,derived_from=source,source_sha256=hashlib.sha256(raw).hexdigest(),
                added_instances=added,change_note="Add four certified trifference scale points; all earlier entries preserved.")
    out=os.path.join(DIR,f"{target}.json");text=json.dumps(data,indent=1,sort_keys=True)+"\n"
    if os.path.exists(out) and open(out).read()!=text:raise ValueError("refusing to replace a frozen snapshot")
    open(out,"w").write(text);return data


def key(fam, p):
    return f"{fam}|{json.dumps(p, sort_keys=True)}"


def freeze(version):
    os.makedirs(DIR, exist_ok=True)
    table = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "bench", "refs", "*-t10.json"))):
        base = os.path.basename(f)[:-len("-t10.json")]
        tier, rest = base.split("-", 1); fam, seed = rest.rsplit("-", 1)
        if fam not in O.FAMILIES: continue
        p = json.load(open(f))["params"]; F = O.FAMILIES[fam]
        kb = O.known_best(F, p); a, kind = O.anchor(F, p)
        cited = bool(getattr(F, "KNOWN_CITED", None)) and (tuple(p.get(k) for k in ("q", "n")) in F.KNOWN_CITED if fam == "apfree_q" else False)
        entry = {"family": fam, "params": p, "known_best": kb, "cited": cited, "anchor": a, "anchor_kind": kind}
        construction = O.construction_reference(F, p)
        if construction is not None:
            entry["construction_reference"] = construction
        table[key(fam, p)] = entry
    out = os.path.join(DIR, f"{version}.json")
    json.dump({"version": version, "entries": table}, open(out, "w"), indent=1, sort_keys=True)
    print(f"wrote {out}: {len(table)} instances")


def load(version=None):
    """Install a frozen table into openceiling (known_best / anchor answer from it).  Returns the version name."""
    files = sorted(glob.glob(os.path.join(DIR, "*.json")))
    if not files:
        return None
    path = os.path.join(DIR, f"{version}.json") if version else files[-1]
    with open(path) as source:
        data = json.load(source)
    table = data["entries"]
    kb0, an0 = O.known_best, O.anchor

    def known_best(fam, p):
        e = table.get(key(fam.name, p))
        return e["known_best"] if e else kb0(fam, p)

    def anchor(fam, p):
        e = table.get(key(fam.name, p))
        return (e["anchor"], e["anchor_kind"]) if e else an0(fam, p)
    O.known_best, O.anchor = known_best, anchor
    # Do not leak live or previously selected construction references into a
    # different snapshot. In particular an older file without this field means
    # its original construction floor, not the newest calibrated value.
    O._CONSTRUCTION_REFERENCE_TABLE = {k: e["construction_reference"] for k, e in table.items()
                                       if "construction_reference" in e}
    O._ZERO_CACHE.clear()
    O.FROZEN_SPEC = data["version"]
    return data["version"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--version", required=True); a = ap.parse_args()
    freeze(a.version)
