"""Verifier regression tests: known objects must pass with the known objective, known violations must be rejected.

    python3 bench/test_verifiers.py          (plain python, no framework; exits non-zero on the first failure)

Known objects are either constructed here or taken from verified rows in bench/results (committed data)."""
import glob, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
from openceiling import FAMILIES, expand_answer, eg_bound, textbook_zero, verify_with_timeout  # noqa: E402

fails = 0
def check(name, fam, p, ans, expect_ok, expect_obj=None):
    global fails
    ans = expand_answer(FAMILIES[fam], p, ans)
    ok, obj, msg = FAMILIES[fam].verify(p, ans)
    good = (ok == expect_ok) and (expect_obj is None or not ok or abs(obj - expect_obj) < 1e-9)
    print(f"{'PASS' if good else 'FAIL'}  {name:58s} ok={ok!s:5s} obj={obj} {msg[:50]}")
    fails += (not good)

def stored(model_substr, config_substr, family, seed, tier):
    """First feasible stored answer matching the filters."""
    for f in glob.glob(os.path.join(ROOT, "bench", "results", f"*{model_substr}*{config_substr}*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if r["family"] == family and r["seed"] == seed and r.get("tier", "A1") == tier and r["feasible"] and r.get("content"):
                try:
                    return r["params"], json.loads(r["content"])["answer"], r["objective"]
                except Exception:
                    pass
    return None

# --- constructed objects ---
check("E8 kissing (240) via orbit: D8 roots + half-spin", "kissing", {"d": 8},
      {"orbit": [[1, 1, 0, 0, 0, 0, 0, 0]], "signs": True, "perms": True}, True, 112)   # D8 roots alone: 112
half = [v for v in __import__("itertools").product((1, -1), repeat=8) if sum(1 for c in v if c < 0) % 2 == 0]
d8 = expand_answer(FAMILIES["kissing"], {"d": 8}, {"orbit": [[1, 1, 0, 0, 0, 0, 0, 0]], "signs": True, "perms": True})
check("E8 kissing: D8 roots + even-sign (+-1)^8 = 240", "kissing", {"d": 8}, d8 + [list(v) for v in half], True, 240)
check("E8 + all (+-1)^8 must fail (odd-sign vectors too close)", "kissing", {"d": 8},
      d8 + [list(v) for v in __import__("itertools").product((1, -1), repeat=8)], False)
check("cap set d=10: product of 4-caps = 1024", "capset", {"d": 10}, {"product": [["00", "01", "10", "11"]] * 5}, True, 1024)
check("cap set with a line must fail", "capset", {"d": 2}, ["00", "11", "22"], False)
check("AP-free n=20000 via base-3 digits {0,1} = 560", "apfree", {"k": 3, "n": 20000},
      {"digits": {"base": 3, "allowed": [0, 1], "length": 10, "sum_squares": None, "offset": 1}}, True, 560)
check("AP-free with a progression must fail", "apfree", {"k": 3, "n": 10}, [1, 2, 3], False)
check("lineq x+2y=3z: base-3 digits {0,1} is NOT free (1+2*4=3*3)", "lineq", {"a": 1, "b": 2, "n": 20000},
      {"digits": {"base": 3, "allowed": [0, 1], "length": 10, "sum_squares": None, "offset": 1}}, False)
check("lineq x+2y=3z: base-4 digits {0,1} is free", "lineq", {"a": 1, "b": 2, "n": 20000},
      {"digits": {"base": 4, "allowed": [0, 1], "length": 8, "sum_squares": None, "offset": 1}}, True)
check("Batcher network n=19 sorts (91 comparators)", "sortnet", {"n": 19}, FAMILIES["sortnet"].naive({"n": 19}), True, 91)
bad = FAMILIES["sortnet"].naive({"n": 12})[:-1]
check("Batcher n=12 minus its last comparator must fail", "sortnet", {"n": 12}, bad, False)
check("Strassen-block scheme 4x4x5 = 72 products", "matmul", {"n": 4, "m": 4, "p": 5}, FAMILIES["matmul"]._scheme(4, 4, 5), True, 72)
check("MacNeish MOLS n=15: 2 squares", "mols", {"n": 15}, FAMILIES["mols"].search({"n": 15}, 1, None), True, 2)
check("two equal Latin squares are not orthogonal", "mols", {"n": 5}, [FAMILIES["mols"].naive({"n": 5})[0]] * 2, False)
tz = textbook_zero(FAMILIES["kakeya"], {"q": 7, "n": 3})
print(f"{'PASS' if tz and tz[0] == 133 else 'FAIL'}  {'Kakeya recursive Saraf-Sudan q=7 n=3 = 133':58s} {tz}"); fails += not (tz and tz[0] == 133)
check("Kakeya: whole space is a Kakeya set", "kakeya", {"q": 5, "n": 3}, FAMILIES["kakeya"].naive({"q": 5, "n": 3}), True, 125)
check("Kakeya: a single line is not", "kakeya", {"q": 5, "n": 2}, [[t, 0] for t in range(5)], False)
check("progression-free {0,1}^4 in F_5^4 = 16", "apfree_q", {"q": 5, "n": 4}, FAMILIES["apfree_q"].naive({"q": 5, "n": 4}), True, 16)
check("progression 000,111,222 in F_5^3 must fail", "apfree_q", {"q": 5, "n": 3}, ["000", "111", "222"], False)
print(f"{'PASS' if eg_bound(3, 4) == 45 and eg_bound(3, 8) == 2781 else 'FAIL'}  {'Ellenberg-Gijswijt count (q=3: d=4 -> 45, d=8 -> 2781)':58s}")
fails += not (eg_bound(3, 4) == 45 and eg_bound(3, 8) == 2781)
check("degdiam: circulant C(13;1,5) has degree 4, diameter 2, 13 vertices", "degdiam", {"d": 4, "k": 2},
      {"cayley": {"moduli": [13], "generators": [[1], [5]]}}, True, 13)
check("degdiam: a path of 6 vertices exceeds diameter 2", "degdiam", {"d": 2, "k": 2}, [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]], False)

# --- stored objects from the study (committed rows) ---
for label, args, expect in [
    ("Fable 5.1: 512-point cap set in F_3^8 (FunSearch size)", ("fable", "headless-high@128k#A2", "capset", 0, "A2"), 512),
    ("Opus 5: 256-word binary code (17, 6)", ("opus", "headless-xhigh@128k#A2", "code", 0, "A2"), 256),
    ("Opus 5: Paley Hadamard matrix of order 20", ("opus", "agent-notools#A2", "hadamard", 0, "A2"), 0),
    ("astra high: 39-product scheme for 3x3x5", ("astra", "codex-medium@nocap#A2", "matmul", 0, "A2"), 39),
]:
    got = stored(*args)
    if got is None:
        print(f"SKIP  {label:58s} (no stored row)"); continue
    p, ans, obj = got
    check(label, args[2], p, ans, True, expect)

# --- families added to the suite after the external review (2026-09-13) ---
import itertools, time
check("LABS: Legendre naive N=13 is a valid sequence", "labs", {"N": 13}, FAMILIES["labs"].naive({"N": 13}), True)
check("LABS: wrong length must fail", "labs", {"N": 13}, [1] * 12, False)
check("LABS: JSON booleans must fail", "labs", {"N": 13}, [True] * 13, False)
check("Heilbronn: three collinear points are valid with area 0", "heilbronn", {"n": 3}, [[0, 0], [1, 1], [2, 2]], True, 0)
check("Heilbronn: duplicate points must fail", "heilbronn", {"n": 3}, [[0, 0], [0, 0], [5, 5]], False)
check("Heilbronn: JSON booleans must fail", "heilbronn", {"n": 3}, [[False, False], [True, False], [False, True]], False)
check("corners: naive construction is corner-free", "corners", {"n": 20}, FAMILIES["corners"].naive({"n": 20}), True)
check("corners: (0,0),(1,0),(0,1) is a corner", "corners", {"n": 5}, [[0, 0], [1, 0], [0, 1]], False)
check("corners: negative-direction corner must fail", "corners", {"n": 5}, [[1, 1], [0, 1], [1, 0]], False)
check("unit distance: naive construction is valid", "unitdist", {"n": 50}, FAMILIES["unitdist"].naive({"n": 50}), True)
check("unit distance: duplicate points must fail", "unitdist", {"n": 3}, [[0, 0], [0, 0], [1, 0]], False)
d6 = FAMILIES["kissing"].naive({"d": 6})
check("spherical code: D6 roots (60 vectors) pass at cos = 0.50", "kissing_theta", {"d": 6, "cos100": 50}, d6, True, 60)
check("spherical code: D6 roots fail at cos = 0.48 (60-degree pairs)", "kissing_theta", {"d": 6, "cos100": 48}, d6, False)
check("spherical code: d = 31 is refused (exact-arithmetic range)", "kissing_theta", {"d": 31, "cos100": 24}, [[1000] * 31] * 5, False)
T = [[0, 0], [4000, 0], [0, 4000]]
check("Heilbronn (shape): 4 points in a triangle, normalised min area 1/4", "heilbronn_shape", {"n": 4, "T": T},
      [[0, 0], [4000, 0], [0, 4000], [1000, 1000]], True, 0.25)
check("Heilbronn (shape): a point outside the triangle must fail", "heilbronn_shape", {"n": 4, "T": T},
      [[0, 0], [4000, 0], [0, 4000], [3000, 3000]], False)
check("cap set: empty answer is rejected (not an exception)", "capset", {"d": 10}, [], False)
check("progression-free F_q^n: empty answer is rejected", "apfree_q", {"q": 5, "n": 6}, [], False)
check("AP-free: JSON booleans must fail", "apfree", {"n": 100, "k": 3}, [True], False)
check("sorting network: boolean wire indices must fail", "sortnet", {"n": 2}, [[False, True]], False)
check("sorting network: 4 n^2 comparator limit is enforced", "sortnet", {"n": 20}, FAMILIES["sortnet"].naive({"n": 20}) + [[0, 1]] * 1601, False)
t0 = time.time()
ok, obj, msg = verify_with_timeout(FAMILIES["apfree"], {"n": 6242, "k": 3}, {"digits": {"base": 3, "allowed": [0, 1], "length": 40, "sum_squares": 40}})
good = (not ok) and time.time() - t0 < 10
print(f"{'PASS' if good else 'FAIL'}  {'digit-set expansion with 2^40 leaves is refused quickly':58s} ok={ok} {msg[:50]} ({time.time() - t0:.1f}s)"); fails += not good
check("cap set d=9: Edel affine 1082-cap frontier is recorded", "capset", {"d": 9}, FAMILIES["capset"].naive({"d": 9}), True)
from openceiling import known_best, anchor
for fam, p, want in [("capset", {"d": 10}, 2432), ("capset", {"d": 11}, 5504), ("schur", {"k": 7}, 1696), ("mols", {"n": 14}, 4), ("mols", {"n": 18}, 5),
                     ("degdiam", {"d": 4, "k": 4}, 104), ("apfree_q", {"q": 5, "n": 5}, 194)]:
    got = known_best(FAMILIES[fam], p); good = got == want
    print(f"{'PASS' if good else 'FAIL'}  {f'literature table {fam} {p} = {want}':58s} got={got}"); fails += not good
b, kind = anchor(FAMILIES["capset"], {"d": 10}); good = (b, kind) == (5619, "bound")
print(f"{'PASS' if good else 'FAIL'}  {'cap set d=10 anchor = 5619 (Versluis 2017), kind bound':58s} got={b},{kind}"); fails += not good

print(f"\n{'ALL PASSED' if not fails else str(fails) + ' FAILURE(S)'}")
sys.exit(1 if fails else 0)
