#!/usr/bin/env python3
"""Independent second implementations of all fifteen headline verifiers (eight published-table, seven table-free) (pure Python, exact integer arithmetic, no NumPy), and a
cross-check of every stored feasible answer of those families against the primary verifier.

    python3 bench/crosscheck.py                 # cross-check all stored A3 (and ladder) answers of the fifteen headline families
    python3 bench/crosscheck.py --tier A3

A disagreement between the two implementations is a verifier bug; both the primary and this file must accept an
object (with the same objective) for a score to stand."""
import argparse, glob, json, os, sys
from collections import deque
from itertools import combinations
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
from openceiling import FAMILIES, expand_answer  # noqa: E402
from run_ladder import extract_json  # noqa: E402

PANEL1 = ["capset", "kissing", "matmul", "degdiam", "apfree_q", "mols", "schur", "covering"]
PANEL2 = ["labs", "heilbronn", "corners", "kissing_theta", "heilbronn_shape", "lineq", "kakeya"]


def capset2(p, ans):
    d = p["d"]
    if not isinstance(ans, list) or not ans: return False, 0
    vs = []
    for w in ans:
        if not isinstance(w, str) or len(w) != d or any(c not in "012" for c in w): return False, 0
        vs.append(tuple(int(c) for c in w))
    S = set(vs)
    if len(S) != len(vs): return False, 0
    for x, y in combinations(vs, 2):
        z = tuple((-(a + b)) % 3 for a, b in zip(x, y))
        if z in S and z != x and z != y: return False, 0
    return True, len(vs)


def kissing2(p, ans, cos_num=1, cos_den=2):
    """pairwise angle >= arccos(cos_num/cos_den): dot <= 0 or dot^2 * den^2 <= num^2 |u|^2 |v|^2, exact integers."""
    if isinstance(ans, dict) and "quadratic_vectors" in ans:
        if (cos_num, cos_den) != (1, 2):
            return False, 0
        return kissing_quadratic2(p, ans)
    d = p["d"]
    if not isinstance(ans, list) or not ans: return False, 0
    if p.get("representation") == "quadratic" and (
            type(d) is not int or not 1 <= d <= 16 or len(ans) > 20000):
        return False, 0
    for v in ans:
        if not (isinstance(v, list) and len(v) == d and all(type(c) is int for c in v)): return False, 0
        if p.get("representation") == "quadratic" and any(abs(c) > 1000 for c in v):
            return False, 0
    n2 = [sum(c * c for c in v) for v in ans]
    if any(x == 0 for x in n2): return False, 0
    if len({tuple(v) for v in ans}) != len(ans): return False, 0
    for i in range(len(ans)):
        vi = ans[i]
        for j in range(i + 1, len(ans)):
            dot = sum(a * b for a, b in zip(vi, ans[j]))
            if dot > 0 and dot * dot * cos_den * cos_den > cos_num * cos_num * n2[i] * n2[j]: return False, 0
    return True, len(ans)


def kissing_quadratic2(p, ans):
    """Independent pure-Python check using integer square-root intervals.

    This intentionally does not share parsing or arithmetic with the NumPy
    verifier. The field is Q(sqrt(3)); no approximate coordinates are used.
    """
    from math import isqrt
    d = p.get("d")
    if p.get("representation") != "quadratic" or type(d) is not int or not 1 <= d <= 16:
        return False, 0
    if type(ans) is not dict or set(ans) != {"quadratic_vectors"}:
        return False, 0
    data = ans["quadratic_vectors"]
    if type(data) is not dict or set(data) != {"radicand", "vectors"}:
        return False, 0
    if type(data["radicand"]) is not int or data["radicand"] != 3:
        return False, 0
    vectors = data["vectors"]
    if type(vectors) is not list or not 1 <= len(vectors) <= 20000:
        return False, 0
    for v in vectors:
        if type(v) is not list or len(v) != d:
            return False, 0
        if any(type(c) is not list or len(c) != 2
               or any(type(x) is not int or x < -1000 or x > 1000 for x in c) for c in v):
            return False, 0
        if not any(a or b for a, b in v):
            return False, 0

    def multiply(x, y):
        a, b = x; c, e = y
        return a * c + 3 * b * e, a * e + b * c

    def dot(u, v):
        x = y = 0
        for c, e in zip(u, v):
            a, b = multiply(c, e); x += a; y += b
        return x, y

    def sign(x):
        a, b = x
        if not b:
            return (a > 0) - (a < 0)
        floor = isqrt(3 * b * b)
        # |b|sqrt(3) lies strictly between floor and floor+1.
        return 1 if (a + floor >= 0 if b > 0 else a > floor) else -1

    norms = [dot(v, v) for v in vectors]
    for i, u in enumerate(vectors):
        for j in range(i):
            g = dot(u, vectors[j])
            if sign(g) <= 0:
                continue
            g2 = multiply(g, g); n2 = multiply(norms[i], norms[j])
            if sign((n2[0] - 4 * g2[0], n2[1] - 4 * g2[1])) < 0:
                return False, 0
    return True, len(vectors)


def matmul2(p, ans):
    """sum_k u_k (x) v_k (x) w_k must equal the (n x m)(m x p) multiplication tensor, exactly."""
    n, m, q = p["n"], p["m"], p["p"]
    if not isinstance(ans, list) or not ans: return False, 0
    T = {}
    for t in ans:
        if not (isinstance(t, list) and len(t) == 3): return False, 0
        u, v, w = t
        if (len(u), len(v), len(w)) != (n * m, m * q, n * q): return False, 0
        if not all(type(c) is int for c in u + v + w): return False, 0
        for a, ua in enumerate(u):
            if not ua: continue
            for b, vb in enumerate(v):
                if not vb: continue
                for c, wc in enumerate(w):
                    if not wc: continue
                    T[(a, b, c)] = T.get((a, b, c), 0) + ua * vb * wc
    for i in range(n):
        for j in range(m):
            for l in range(q):
                a, b, c = i * m + j, j * q + l, i * q + l
                if T.pop((a, b, c), 0) != 1: return False, 0
    if any(v != 0 for v in T.values()): return False, 0
    return True, len(ans)


def degdiam2(p, ans):
    d, k = p["d"], p["k"]
    if not isinstance(ans, list) or not ans: return False, 0
    adj = {}
    for e in ans:
        if not (isinstance(e, list) and len(e) == 2 and all(type(x) is int and x >= 0 for x in e)) or e[0] == e[1]: return False, 0
        a, b = e
        adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
    if any(len(nb) > d for nb in adj.values()): return False, 0
    V = list(adj); N = len(V)
    for s in V:                                         # BFS eccentricity <= k for every vertex
        dist = {s: 0}; dq = deque([s])
        while dq:
            x = dq.popleft()
            for y in adj[x]:
                if y not in dist:
                    dist[y] = dist[x] + 1; dq.append(y)
        if len(dist) != N or max(dist.values()) > k: return False, 0
    return True, N


def apfree_q2(p, ans):
    q, n = p["q"], p["n"]
    if not isinstance(ans, list) or not ans: return False, 0
    vs = []
    for w in ans:
        if not isinstance(w, str) or len(w) != n or any(not c.isdigit() or int(c) >= q for c in w): return False, 0
        vs.append(tuple(int(c) for c in w))
    S = set(vs)
    if len(S) != len(vs): return False, 0
    for x, y in combinations(vs, 2):
        z = tuple((2 * b - a) % q for a, b in zip(x, y))    # x, y, z with x + z = 2y
        if z in S and z != x and z != y: return False, 0
        z = tuple((2 * a - b) % q for a, b in zip(x, y))    # y, x, z with y + z = 2x
        if z in S and z != x and z != y: return False, 0
    return True, len(vs)


def mols2(p, ans):
    n = p["n"]
    if not isinstance(ans, list) or not ans: return False, 0
    for L in ans:
        if not (isinstance(L, list) and len(L) == n and all(isinstance(r, list) and len(r) == n for r in L)): return False, 0
        for r in L:
            if sorted(r) != list(range(n)): return False, 0
        for j in range(n):
            if sorted(L[i][j] for i in range(n)) != list(range(n)): return False, 0
    for A, B in combinations(ans, 2):
        if len({(A[i][j], B[i][j]) for i in range(n) for j in range(n)}) != n * n: return False, 0
    return True, len(ans)


def schur2(p, ans):
    """k-colouring of 1..N (ans[i-1] = colour of i, integers in 0..k-1) with no x + y = z in one colour, x = y allowed."""
    k = p["k"]
    if not isinstance(ans, list) or not ans: return False, 0
    if any(type(c) is not int or not 0 <= c < k for c in ans): return False, 0
    N = len(ans); col = {i + 1: c for i, c in enumerate(ans)}
    for x in range(1, N + 1):
        for y in range(x, N + 1 - x):                       # z = x + y <= N
            if col[x] == col[y] == col[x + y]: return False, 0
    return True, N


def covering2(p, ans):
    """Every t-subset of 0..v-1 lies in some block (a list of k distinct integers); objective = number of blocks."""
    v, k, t = p["v"], p["k"], p["t"]
    if not isinstance(ans, list) or not ans: return False, 0
    blocks = []
    for b in ans:
        if not (isinstance(b, list) and len(b) == k and all(type(x) is int and 0 <= x < v for x in b) and len(set(b)) == k): return False, 0
        blocks.append(frozenset(b))
    by_point = {x: [b for b in blocks if x in b] for x in range(v)}     # blocks through the smallest point of the subset
    for sub in combinations(range(v), t):
        if not any(all(x in b for x in sub) for b in by_point[sub[0]]): return False, 0
    return True, len(blocks)


# ---- the seven table-free families (panel 2); geometry in exact integer arithmetic, the same float expression at the end
def labs2(p, ans):
    """+-1 sequence of length N; merit factor N^2 / (2 E), E = sum over shifts k >= 1 of the squared aperiodic autocorrelation."""
    N = p["N"]
    if not isinstance(ans, list) or len(ans) != N or any(type(v) is not int or v not in (1, -1) for v in ans): return False, 0
    E = 0
    for k in range(1, N):
        c = 0
        for i in range(N - k): c += ans[i] * ans[i + k]
        E += c * c
    return True, (N * N / (2 * E) if E else float("inf"))


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _grid_points(ans, n, D):
    if not isinstance(ans, list) or len(ans) != n: return None
    pts = []
    for q in ans:
        if not (isinstance(q, list) and len(q) == 2 and all(type(c) is int and 0 <= c <= D for c in q)): return None
        pts.append((q[0], q[1]))
    return pts if len(set(pts)) == len(pts) else None


def heilbronn2(p, ans, D=10000):
    """n distinct grid points in [0, D]^2; objective = smallest triangle area as a fraction of the square (twice-area / 2D^2)."""
    pts = _grid_points(ans, p["n"], D)
    if pts is None: return False, 0
    best = min(abs(_cross(a, b, c)) for a, b, c in combinations(pts, 3))
    return True, best / (2 * D * D)


def heilbronn_shape2(p, ans, D=10000):
    """As heilbronn2, inside the triangle T (boundary allowed); objective relative to the area of T."""
    pts = _grid_points(ans, p["n"], D); T = [tuple(v) for v in p["T"]]
    if pts is None: return False, 0
    for q in pts:                                        # same side of (or on) every edge: all cross signs >= 0 or all <= 0
        sg = [_cross(T[i], T[(i + 1) % 3], q) for i in range(3)]
        if not (min(sg) >= 0 or max(sg) <= 0): return False, 0
    best = min(abs(_cross(a, b, c)) for a, b, c in combinations(pts, 3))
    return True, best / abs(_cross(*T))


def corners2(p, ans):
    """Distinct grid points in [0, n)^2 with no (x, y), (x + d, y), (x, y + d), d != 0 (either sign)."""
    n = p["n"]
    if not isinstance(ans, list): return False, 0
    pts = []
    for q in ans:
        if not (isinstance(q, list) and len(q) == 2 and all(type(c) is int and 0 <= c < n for c in q)): return False, 0
        pts.append((q[0], q[1]))
    S = set(pts)
    if len(S) != len(pts): return False, 0
    cols = {}
    for (x, y) in pts: cols.setdefault(x, set()).add(y)
    for (x, y) in pts:                                   # for the corner's right angle at (x, y): a point (x, y + d) above
        for y2 in cols[x]:                               # and (x + d, y) to the right, with the same d
            d = y2 - y
            if d and (x + d, y) in S: return False, 0
    return True, len(pts)


def kissing_theta2(p, ans, B=1000):
    """Spherical code: integer vectors in [-B, B]^d, d <= 16, pairwise cos <= c/100 (exact: 100^2 dot^2 <= c^2 |u|^2 |v|^2 when dot > 0)."""
    d, c = p["d"], p["cos100"]
    if d > 16 or not isinstance(ans, list) or not ans: return False, 0
    for v in ans:
        if not (isinstance(v, list) and len(v) == d and all(type(x) is int and -B <= x <= B for x in v)): return False, 0
    return kissing2(p, ans, cos_num=c, cos_den=100)     # includes the zero-vector and distinctness checks


def lineq2(p, ans):
    """Subset of 1..n with no solution of a x + b y = (a + b) z except x = y = z."""
    a, b, n = p["a"], p["b"], p["n"]; c = a + b
    if not isinstance(ans, list) or any(type(v) is not int or not 1 <= v <= n for v in ans): return False, 0
    S = set(ans)
    if len(S) != len(ans): return False, 0
    L = sorted(S)
    for x in L:
        for y in L:
            t = a * x + b * y
            if t % c == 0 and (t // c) in S and not (x == y == t // c): return False, 0
    return True, len(S)


def kakeya2(p, ans):
    """Kakeya set in F_q^n: distinct points containing a full line in every direction (directions up to scaling)."""
    from itertools import product
    q, n = p["q"], p["n"]
    if not isinstance(ans, list) or not ans: return False, 0
    pts = []
    for v in ans:
        if not (isinstance(v, list) and len(v) == n and all(type(x) is int and 0 <= x < q for x in v)): return False, 0
        pts.append(tuple(v))
    K = set(pts)
    if len(K) != len(pts): return False, 0
    for dvec in product(range(q), repeat=n):
        nz = [x for x in dvec if x]
        if not nz or nz[0] != 1: continue                # one representative per direction
        if not any(all(tuple((a[i] + t * dvec[i]) % q for i in range(n)) in K for t in range(q)) for a in pts): return False, 0
    return True, len(pts)


SECOND = {"capset": capset2, "kissing": kissing2, "matmul": matmul2, "degdiam": degdiam2, "apfree_q": apfree_q2, "mols": mols2,
          "schur": schur2, "covering": covering2, "labs": labs2, "heilbronn": heilbronn2, "corners": corners2,
          "kissing_theta": kissing_theta2, "heilbronn_shape": heilbronn_shape2, "lineq": lineq2, "kakeya": kakeya2}

from candidate_families import shannon_second, trifference_second, zarank_second
SECOND.update(shannon=shannon_second, trifference=trifference_second, zarank=zarank_second)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tier", default=None); a = ap.parse_args()
    n = bad = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "bench", "results", "*.jsonl"))):
        for line in open(f):
            r = json.loads(line)
            if r["family"] not in SECOND or not r.get("feasible") or not r.get("content"): continue
            if a.tier and r.get("tier", "A1") != a.tier: continue
            if r["model"] in ("naive", "search", "garbage"): continue
            ans = extract_json(r["content"])          # same extraction as the scorer: {"answer": X} or a bare compact form
            if ans is None: continue
            F = FAMILIES[r["family"]]; p = r["params"]
            ans = expand_answer(F, p, ans)
            ok1, obj1, _ = F.verify(p, ans); ok2, obj2 = SECOND[r["family"]](p, ans)
            n += 1
            if (ok1, obj1) != (ok2, obj2) or ok1 != r["feasible"] or obj1 != r["objective"]:
                bad += 1; print(f"DISAGREE {os.path.basename(f)} {r['family']} seed {r['seed']}: primary {ok1},{obj1}  second {ok2},{obj2}  stored {r['feasible']},{r['objective']}")
    print(f"cross-checked {n} stored answers of {len(SECOND)} families: {bad} disagreement(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
