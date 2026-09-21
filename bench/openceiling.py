#!/usr/bin/env python3
"""Endless Exam: open-ceiling construction problems (module name kept as openceiling).

Every family here has four properties that the fixed-instance research
benchmarks (HorizonMath, AlphaEvolve's list) do not all have at once:

  * a purely programmatic verifier -- a mathematical property, never a test
    set and never an LLM judge, so disclosure of the checker is harmless;
  * an optimum that is unknown or unproven at the instance sizes drawn;
  * parametric, seeded instances -- unlimited fresh problems, no fixed n to
    memorise;
  * a continuous objective with a computable naive construction and a
    budgeted search baseline, so a score means "how far below the frontier",
    not "did you beat the literature".

    python3 bench/openceiling.py gen    --family apfree --seed 7
    python3 bench/openceiling.py verify --family apfree --seed 7 --answer ans.json
    python3 bench/openceiling.py demo   --time 3            # naive vs search, every family
"""
import argparse
import json
import math
import random
import sys
import time
from itertools import combinations
from math import comb, gcd

try:
    import numpy as np
except ImportError:          # LABS falls back to pure Python
    np = None


def now():
    return time.time()


# ----------------------------------------------------------------------------
# Families whose answer is a subset of a finite ground set, objective = size.
# Subclasses supply ground(), can_add(), add(), verify(), naive(), upper().
# The search is an iterated randomised greedy that never needs a remove():
# a state is rebuilt by re-running greedy over the kept elements.
# ----------------------------------------------------------------------------
class SetFamily:
    sense = "max"
    answer_format = "JSON list"

    def new_state(self, p):
        return {"S": set()}

    def add(self, p, st, x):
        st["S"].add(x)

    def greedy(self, p, order, st=None):
        st = st or self.new_state(p)
        for x in order:
            if x not in st["S"] and self.can_add(p, st, x):
                self.add(p, st, x)
        return st

    def candidates(self, p, rng):
        g = list(self.ground(p))
        rng.shuffle(g)
        return g

    def search(self, p, seconds, rng):
        end = now() + seconds
        best = self.greedy(p, list(self.ground(p)))
        while now() < end:
            st = self.greedy(p, self.candidates(p, rng))
            if len(st["S"]) > len(best["S"]):
                best = st
            keep = sorted(best["S"])
            for x in rng.sample(keep, max(1, len(keep) // 6)):
                keep.remove(x)
            st = self.greedy(p, self.candidates(p, rng), self.greedy(p, keep))
            if len(st["S"]) >= len(best["S"]):
                best = st
        return sorted(best["S"])

    def objective(self, p, ans):
        return len(ans)


class APFree(SetFamily):
    name = "apfree"
    title = "AP-Free"

    def law(self, p, obj):
        """Behrend form |S| = n * exp(-c sqrt(ln n)); smaller c is a better construction.
        Reference: exact r_3(211) = 43 gives c = 0.687.  Asymptotically c -> 0 is not
        excluded (Kelley-Meka), so the scale has no fixed floor; it is monotone and n-free."""
        n = p["n"]
        c = -math.log(obj / n) / math.sqrt(math.log(n)) if obj > 0 else float("inf")
        return {"name": f"behrend_c_k{p['k']}", "value": c, "better": "lower", "lower": None,
                "upper": 0.687 if p["k"] == 3 else None,
                "note": "k=3: upper = value at the best exact table entry (n=211); k=4 uses the same form as a proxy"}

    def params(self, rng):
        return {"k": rng.choice([3, 3, 4]), "n": rng.randint(300, 1500)}

    def statement(self, p):
        return (f"Find a subset S of {{1, 2, ..., {p['n']}}} of maximum possible size "
                f"containing no {p['k']}-term arithmetic progression. "
                f"Output: all elements of S in strictly increasing order, as a JSON list of integers.")

    def ground(self, p):
        return range(1, p["n"] + 1)

    def can_add(self, p, st, x):
        S, k, n = st["S"], p["k"], p["n"]
        if k == 3:
            for s in S:
                if 2 * s - x in S or 2 * x - s in S or ((x + s) % 2 == 0 and (x + s) // 2 in S):
                    return False
            return True
        # x may sit at any position i of the progression; the largest usable d
        # is therefore max_i min((x-1)//i, (n-x)//(k-1-i)), not an end-point bound.
        dmax = max(min((x - 1) // i if i else n, (n - x) // (k - 1 - i) if i < k - 1 else n)
                   for i in range(k))
        for d in range(1, dmax + 1):
            for i in range(k):
                a = x - i * d
                if a < 1 or a + (k - 1) * d > n:
                    continue
                if all((a + j * d) in S for j in range(k) if j != i):
                    return False
        return True

    def verify(self, p, ans):
        n, k = p["n"], p["k"]
        if not isinstance(ans, list) or any(not isinstance(v, int) or isinstance(v, bool) for v in ans):
            return False, 0, "answer must be a list of integers"
        if len(set(ans)) != len(ans) or any(v < 1 or v > n for v in ans):
            return False, 0, "elements must be distinct and in range"
        S = set(ans)
        for a in ans:
            for d in range(1, (n - a) // (k - 1) + 1):
                if all(a + j * d in S for j in range(1, k)):
                    return False, 0, f"contains the {k}-AP starting at {a} with difference {d}"
        return True, len(ans), ""

    def naive(self, p):
        if p["k"] == 3:                       # base-3 digits in {0,1}, shifted into [1,n]
            out = []
            for m in range(p["n"]):
                t, ok = m, True
                while t:
                    if t % 3 == 2:
                        ok = False
                        break
                    t //= 3
                if ok:
                    out.append(m + 1)
            return out
        return sorted(self.greedy(p, list(self.ground(p)))["S"])

    def upper(self, p):
        return None                            # exact values known only to n = 211


class Sidon(SetFamily):
    name = "sidon"
    title = "Sidon"

    def law(self, p, obj):
        """Second-order term t = (|S| - sqrt n) / n^(1/4).  Lindstrom: t <= 1 + n^(-1/4)."""
        n = p["n"]
        t = (obj - math.sqrt(n)) / n ** 0.25
        return {"name": "sidon_t", "value": t, "better": "higher", "lower": None, "upper": 1.0,
                "note": "constructions reach sqrt(n)(1-o(1)); whether t -> 1 is attainable is open"}

    def params(self, rng):
        return {"n": rng.randint(200, 3000)}

    def statement(self, p):
        return (f"Find a subset S of {{1, 2, ..., {p['n']}}} of maximum possible size such that "
                f"all pairwise sums a + b (a <= b, both in S) are distinct (a Sidon set). "
                f"Output: the elements of S in increasing order, as a JSON list of integers.")

    def ground(self, p):
        return range(1, p["n"] + 1)

    def new_state(self, p):
        return {"S": set(), "sums": set()}

    def can_add(self, p, st, x):
        if 2 * x in st["sums"]:
            return False
        sums = st["sums"]
        return all((x + s) not in sums for s in st["S"])

    def add(self, p, st, x):
        for s in st["S"]:
            st["sums"].add(x + s)
        st["sums"].add(2 * x)
        st["S"].add(x)

    def verify(self, p, ans):
        n = p["n"]
        if not isinstance(ans, list) or any(not isinstance(v, int) for v in ans):
            return False, 0, "answer must be a list of integers"
        if len(set(ans)) != len(ans) or any(v < 1 or v > n for v in ans):
            return False, 0, "elements must be distinct and in range"
        seen = set()
        for i, a in enumerate(ans):
            for b in ans[i:]:
                if a + b in seen:
                    return False, 0, f"repeated pairwise sum {a + b}"
                seen.add(a + b)
        return True, len(ans), ""

    def naive(self, p):                        # Mian-Chowla greedy
        return sorted(self.greedy(p, list(self.ground(p)))["S"])

    def upper(self, p):                        # Lindstrom 1969
        return int(math.sqrt(p["n"]) + p["n"] ** 0.25 + 1)


class BinaryCode(SetFamily):
    name = "code"
    title = "Binary-Code"

    def law(self, p, obj):
        """Rate R = log2(M)/n at relative distance delta = d/n, against the finite-n
        Gilbert-Varshamov guarantee and the Hamming/Singleton upper bound, both valid at this n."""
        n, d = p["n"], p["d"]
        delta = d / n
        gv = (1 << n) / sum(comb(n, i) for i in range(d))
        return {"name": "rate", "value": math.log2(obj) / n if obj > 0 else float("-inf"), "better": "higher",
                "lower": math.log2(gv) / n, "upper": math.log2(self.upper(p)) / n,
                "note": f"delta={delta:.3f}; finite-n GV lower and Hamming/Singleton upper"}

    def params(self, rng):
        return {"n": rng.randint(14, 17), "d": rng.choice([6, 7, 8])}

    def statement(self, p):
        return (f"Find as many binary words of length {p['n']} as possible such that any two of them "
                f"differ in at least {p['d']} positions. Output: a JSON list of the words as strings of 0/1.")

    def ground(self, p):
        return range(1 << p["n"])

    def candidates(self, p, rng):
        return rng.sample(range(1 << p["n"]), min(1 << p["n"], 20000))

    def can_add(self, p, st, x):
        d = p["d"]
        return all(bin(x ^ s).count("1") >= d for s in st["S"])

    def verify(self, p, ans):
        n, d = p["n"], p["d"]
        if not isinstance(ans, list) or len(ans) > 5000:
            return False, 0, "answer must be a list of at most 5000 words"
        try:
            words = [int(w, 2) for w in ans]
        except (TypeError, ValueError):
            return False, 0, "words must be 0/1 strings"
        if any(len(w) != n for w in ans) or len(set(words)) != len(words):
            return False, 0, "words must be distinct and of the stated length"
        for a, b in combinations(words, 2):
            if bin(a ^ b).count("1") < d:
                return False, 0, "two words are closer than d"
        return True, len(words), ""

    def naive(self, p):                        # lexicode
        return sorted(self.greedy(p, list(self.ground(p)))["S"])

    def upper(self, p):
        n, d = p["n"], p["d"]
        n2, d2 = (n - 1, d - 1) if d % 2 == 0 else (n, d)
        t = (d2 - 1) // 2
        hamming = (1 << n2) // sum(comb(n2, i) for i in range(t + 1))
        return min(hamming, 1 << (n - d + 1))

    def objective(self, p, ans):
        return len(ans)

    def search(self, p, seconds, rng):
        return [format(w, f"0{p['n']}b") for w in super().search(p, seconds, rng)]

    def naive_fmt(self, p):
        return [format(w, f"0{p['n']}b") for w in self.naive(p)]


class CapSet(SetFamily):
    name = "capset"
    title = "Cap-Set"
    # best known (lower, upper) bounds from the literature; d<=6 exact.  Check before publishing.
    KNOWN = {4: (20, 20), 5: (45, 45), 6: (112, 112), 7: (236, 288), 8: (512, 771), 9: (1082, 2070), 10: (2432, 5619),
             11: (5504, 16857), 12: (12928, 50571)}   # d=7 upper 288 (Thackeray, arXiv:2206.09804); d=8-10 upper 771/2070/5619 (Versluis 2017,
    # TU Delft thesis, recursive bounds); d=11 upper 3 x 5619 (a cap meets each of 3 parallel hyperplanes in a cap of AG(10,3)).
    # Lower values: see known_best(). d=11 updated and double-checked 2026-09-16.

    def law(self, p, obj):
        """Exponent lambda = |S|^(1/d).  Known: lambda >= 2.2174 (asymptotic constructions),
        lambda <= 2.756 (Ellenberg-Gijswijt).  Small d sits below the asymptotic lower bound."""
        return {"name": "capset_lambda", "value": obj ** (1 / p["d"]), "better": "higher",
                "lower": 2.2174, "upper": 2.756, "note": "d<=6 exact: 2.115, 2.141, 2.195"}

    def params(self, rng):
        return {"d": rng.randint(5, 7)}

    def statement(self, p):
        return (f"Find a subset S of F_3^{p['d']} (vectors of length {p['d']} with entries in {{0,1,2}}) "
                f"of maximum possible size containing no three distinct vectors x, y, z with "
                f"x + y + z = 0 (mod 3) coordinate-wise -- a cap set. Output: a JSON list of the vectors, "
                f"each written as a string of {p['d']} digits (at most 20000 vectors are accepted).")

    def _tables(self, p):
        d = p["d"]
        if getattr(self, "_d", None) != d:
            self._d = d
            self._dec = [tuple((v // 3 ** i) % 3 for i in range(d)) for v in range(3 ** d)]
            self._enc = {t: v for v, t in enumerate(self._dec)}
        return self._dec, self._enc

    def ground(self, p):
        return range(3 ** p["d"])

    def can_add(self, p, st, x):
        dec, enc = self._tables(p)
        xt, S = dec[x], st["S"]
        for s in S:
            st_ = dec[s]
            z = enc[tuple((-(a + b)) % 3 for a, b in zip(xt, st_))]
            if z in S:
                return False
        return True

    def verify(self, p, ans):
        d = p["d"]
        if not isinstance(ans, list) or any(not isinstance(w, str) or len(w) != d or set(w) - set("012") for w in ans):
            return False, 0, f"answer must be a list of strings of {d} digits 0/1/2"
        vecs = [tuple(int(c) for c in w) for w in ans]
        if not vecs:
            return False, 0, "answer must be a non-empty list"
        if len(set(vecs)) != len(vecs):
            return False, 0, "vectors must be distinct"
        if len(vecs) > 20000:
            return False, 0, "too many vectors (limit 20000)"
        A = np.asarray(vecs, dtype=np.int64)
        pw = 3 ** np.arange(d, dtype=np.int64)
        codes = A @ pw
        S = set(codes.tolist())
        m = len(vecs)
        step = max(1, 2_000_000 // max(1, m))
        for i0 in range(0, m, step):                       # third points z = -(x+y) mod 3 for all pairs, in blocks
            X = A[i0:i0 + step]
            Z = (-(X[:, None, :] + A[None, :, :])) % 3
            zc = Z @ pw
            ii, jj = np.nonzero(np.isin(zc, list(S)) if False else np.vectorize(S.__contains__)(zc))
            for a, b in zip(ii.tolist(), jj.tolist()):
                x, y = i0 + a, b
                if x < y:
                    z = int(zc[a, b])
                    if z != int(codes[x]) and z != int(codes[y]):
                        return False, 0, "contains a line"
        return True, len(vecs), ""

    def naive(self, p):                        # product of the 4-point cap in F_3^2 (and {0,1} if d odd)
        d = p["d"]
        blocks = [[(0, 0), (0, 1), (1, 0), (1, 1)]] * (d // 2) + ([[(0,), (1,)]] if d % 2 else [])
        vecs = [()]
        for b in blocks:
            vecs = [v + w for v in vecs for w in b]
        return ["".join(map(str, v)) for v in vecs]

    def upper(self, p):
        d = p["d"]
        tab = self.KNOWN.get(d, (None, None))[1]
        return tab if tab is not None else min((2 * 3 ** d) // d, eg_bound(3, d))   # Meshulam (1995) / Ellenberg-Gijswijt (2017)

    def search(self, p, seconds, rng):
        dec, _ = self._tables(p)
        return ["".join(map(str, dec[v])) for v in super().search(p, seconds, rng)]


class NoThreeInLine(SetFamily):
    name = "no3inline"
    title = "No-Three-In-Line"

    def law(self, p, obj):
        """alpha = |S| / n.  Proven: 1.5 <= alpha <= 2 for all n; Guy-Kelly conjecture: alpha -> pi/sqrt(3) = 1.814."""
        return {"name": "alpha", "value": obj / p["n"], "better": "higher", "lower": 1.5, "upper": 2.0,
                "note": "2n reached for n<=46; conjectured limit 1.814"}

    def params(self, rng):
        return {"n": rng.randint(30, 100)}

    def statement(self, p):
        n = p["n"]
        return (f"Place as many points as possible on the {n} x {n} integer grid {{0..{n-1}}}^2 so that "
                f"no three of them are collinear. Output: a JSON list of [x, y] pairs.")

    def ground(self, p):
        return range(p["n"] * p["n"])

    @staticmethod
    def _dir(ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        g = gcd(abs(dx), abs(dy))
        dx, dy = dx // g, dy // g
        if dx < 0 or (dx == 0 and dy < 0):
            dx, dy = -dx, -dy
        return dx, dy

    def can_add(self, p, st, x):
        n = p["n"]
        xx, xy = divmod(x, n)
        seen = set()
        for s in st["S"]:
            sx, sy = divmod(s, n)
            dr = self._dir(xx, xy, sx, sy)
            if dr in seen:
                return False
            seen.add(dr)
        return True

    def verify(self, p, ans):
        n = p["n"]
        if not isinstance(ans, list) or any(not (isinstance(q, list) and len(q) == 2) for q in ans):
            return False, 0, "answer must be a list of [x, y] pairs"
        pts = [tuple(q) for q in ans]
        if any(not all(isinstance(c, int) and 0 <= c < n for c in q) for q in pts) or len(set(pts)) != len(pts):
            return False, 0, "points must be distinct integer grid points in range"
        for a in pts:
            seen = set()
            for b in pts:
                if a == b:
                    continue
                dr = self._dir(*a, *b)
                if dr in seen:
                    return False, 0, "three collinear points"
                seen.add(dr)
        return True, len(pts), ""

    def naive(self, p):
        n = p["n"]
        return [list(divmod(v, n)) for v in sorted(self.greedy(p, list(self.ground(p)))["S"])]

    def upper(self, p):
        return 2 * p["n"]

    def search(self, p, seconds, rng):
        n = p["n"]
        return [list(divmod(v, n)) for v in super().search(p, seconds, rng)]


# ----------------------------------------------------------------------------
# Sequence / point-set families with a continuous objective.
# ----------------------------------------------------------------------------
class LABS:
    name = "labs"
    title = "Low-Autocorrelation"
    sense = "max"

    def law(self, p, obj):
        """The merit factor is already scale-free.  Constructions: 6.34 (rotated Legendre, asymptotic);
        Golay's conjecture: 12.32."""
        return {"name": "merit_factor", "value": obj, "better": "higher", "lower": 6.34, "upper": 12.32,
                "note": "search reaches ~9 at N~100-300; optimum unknown beyond N=66"}

    def params(self, rng):
        return {"N": rng.randint(40, 160)}

    def statement(self, p):
        N = p["N"]
        return (f"Find a sequence s_1..s_{N} with each s_i in {{+1, -1}} maximising the merit factor "
                f"F = N^2 / (2 * sum_{{k=1}}^{{N-1}} C_k^2), where C_k = sum_{{i=1}}^{{N-k}} s_i s_(i+k). "
                f"Output: the sequence as a JSON list of +1/-1.")

    def objective(self, p, s):
        N = len(s)
        if np is not None:
            a = np.asarray(s, dtype=np.int64)
            c = np.correlate(a, a, "full")[N:]
            E = int((c * c).sum())
        else:
            E = sum(sum(s[i] * s[i + k] for i in range(N - k)) ** 2 for k in range(1, N))
        return N * N / (2 * E) if E else float("inf")

    def verify(self, p, ans):
        N = p["N"]
        if not isinstance(ans, list) or len(ans) != N or any(isinstance(v, bool) or v not in (1, -1) for v in ans):
            return False, 0, f"answer must be a list of {N} values +1/-1"
        return True, self.objective(p, ans), ""

    def naive(self, p):                        # Legendre sequence of the largest prime <= N, padded
        N = p["N"]
        q = N
        while not all(q % i for i in range(2, int(q ** 0.5) + 1)):
            q -= 1
        qr = {(i * i) % q for i in range(1, q)}
        s = [1] + [1 if i in qr else -1 for i in range(1, q)]
        return s + [1] * (N - q)

    def upper(self, p):
        return None                            # no finite bound; Golay's asymptotic conjecture F -> 12.32

    def search(self, p, seconds, rng):
        N, end = p["N"], now() + seconds
        best = self.naive(p)
        bestF = self.objective(p, best)
        while now() < end:
            s = [rng.choice((1, -1)) for _ in range(N)]
            F = self.objective(p, s)
            improved = True
            while improved and now() < end:
                improved = False
                for i in rng.sample(range(N), N):
                    s[i] = -s[i]
                    F2 = self.objective(p, s)
                    if F2 > F:
                        F, improved = F2, True
                    else:
                        s[i] = -s[i]
            if F > bestF:
                best, bestF = s[:], F
        return best


class Heilbronn:
    name = "heilbronn"
    title = "Heilbronn"
    sense = "max"
    D = 10000

    def law(self, p, obj):
        """Delta(n) ~ n^(-beta); smaller beta is a better construction.  Known: beta <= 2 (with a log
        factor, Komlos-Pintz-Szemeredi), beta >= 8/7 + 1/2000 (Cohen-Pohoata-Zakharov 2023: Delta(n) <= n^{-8/7-1/2000})."""
        n = p["n"]
        beta = -math.log(obj) / math.log(n) if obj > 0 else None      # a degenerate (collinear) set has no constant
        return {"name": "heilbronn_beta", "value": beta, "better": "lower", "lower": 8 / 7, "upper": 2.0,
                "note": "small n: low-order terms dominate; treat as an estimate"}

    def params(self, rng):
        return {"n": rng.randint(8, 20)}

    def statement(self, p):
        return (f"Place {p['n']} points in the unit square, with coordinates given as integers on the "
                f"{self.D} x {self.D} grid (i.e. x/{self.D}, y/{self.D}), so as to maximise the smallest area "
                f"of a triangle formed by any three of the points. Output: a JSON list of [x, y] integer pairs.")

    def objective(self, p, pts):
        best = None
        for (ax, ay), (bx, by), (cx, cy) in combinations(pts, 3):
            a = abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax))
            if best is None or a < best:
                best = a
        return best / (2 * self.D * self.D)

    def verify(self, p, ans):
        n, D = p["n"], self.D
        if not isinstance(ans, list) or len(ans) != n or any(not (isinstance(q, list) and len(q) == 2) for q in ans):
            return False, 0, f"answer must be a list of {n} [x, y] pairs"
        pts = [tuple(q) for q in ans]
        if any(not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= D for c in q) for q in pts) or len(set(pts)) != len(pts):
            return False, 0, "coordinates must be distinct integers in [0, D]"
        return True, self.objective(p, pts), ""

    def _random(self, p, rng):
        return [(rng.randint(0, self.D), rng.randint(0, self.D)) for _ in range(p["n"])]

    def naive(self, p):
        rng = random.Random(0)
        best, bestv = None, -1
        for _ in range(300):
            pts = self._random(p, rng)
            v = self.objective(p, pts)
            if v > bestv:
                best, bestv = pts, v
        return [list(q) for q in best]

    def upper(self, p):
        return None                            # best known only to n ~ 16

    def search(self, p, seconds, rng):
        end, D = now() + seconds, self.D
        pts = [tuple(q) for q in self.naive(p)]
        v = self.objective(p, pts)
        radius = D // 4
        while now() < end:
            i = rng.randrange(len(pts))
            cand = pts[:]
            cand[i] = (min(D, max(0, pts[i][0] + rng.randint(-radius, radius))),
                       min(D, max(0, pts[i][1] + rng.randint(-radius, radius))))
            if len(set(cand)) < len(cand):
                continue
            v2 = self.objective(p, cand)
            if v2 >= v:
                pts, v = cand, v2
            elif rng.random() < 0.02:
                radius = max(10, radius // 2) if rng.random() < 0.5 else min(D // 4, radius * 2)
        return [list(q) for q in pts]


class Mono3AP:
    name = "mono3ap"
    title = "Monochromatic-3AP"
    sense = "min"

    def law(self, p, obj):
        """Density of monochromatic 3-APs among all 3-APs.  Known: 0.05112 <= min density <= 0.05337
        (Parrilo-Robertson-Saracino); random colourings give 0.25."""
        return {"name": "mono_density", "value": obj / self.total_aps(p), "better": "lower",
                "lower": 0.05112, "upper": 0.05337, "note": "asymptotic interval; finite n slightly higher"}

    def params(self, rng):
        return {"n": rng.randint(100, 500)}

    def statement(self, p):
        return (f"Colour each of 1, 2, ..., {p['n']} red or blue so as to minimise the number of "
                f"monochromatic 3-term arithmetic progressions. Output: a string of length {p['n']} over {{0,1}}.")

    def objective(self, p, c):
        n, cnt = len(c), 0
        for a in range(n):
            for d in range(1, (n - 1 - a) // 2 + 1):
                if c[a] == c[a + d] == c[a + 2 * d]:
                    cnt += 1
        return cnt

    def verify(self, p, ans):
        n = p["n"]
        if not isinstance(ans, str) or len(ans) != n or set(ans) - set("01"):
            return False, 0, f"answer must be a 0/1 string of length {n}"
        return True, self.objective(p, ans), ""

    def _through(self, c, i):
        n, cnt = len(c), 0
        for d in range(1, n):
            hit = False
            for lo in (i - 2 * d, i - d, i):
                if lo >= 0 and lo + 2 * d < n and c[lo] == c[lo + d] == c[lo + 2 * d]:
                    cnt += 1
                    hit = True
            if not hit and i - 2 * d < 0 and i + 2 * d >= n:
                break
        return cnt

    def naive(self, p):
        rng = random.Random(0)
        best, bestv = None, None
        for _ in range(50):
            c = "".join(rng.choice("01") for _ in range(p["n"]))
            v = self.objective(p, c)
            if bestv is None or v < bestv:
                best, bestv = c, v
        return best

    def total_aps(self, p):
        n = p["n"]
        return sum((n - 1 - a) // 2 for a in range(n))

    def upper(self, p):                        # a LOWER bound here (sense=min); asymptotic, informational
        return round(0.05112 * self.total_aps(p))

    def search(self, p, seconds, rng):
        n, end = p["n"], now() + seconds
        best = list(self.naive(p))
        bestv = self.objective(p, best)
        c, v = best[:], bestv
        while now() < end:
            improved = False
            for i in rng.sample(range(n), n):
                before = self._through(c, i)
                c[i] = "1" if c[i] == "0" else "0"
                after = self._through(c, i)
                if after <= before:
                    v += after - before
                    improved = improved or after < before
                else:
                    c[i] = "1" if c[i] == "0" else "0"
                if now() >= end:
                    break
            if v < bestv:
                best, bestv = c[:], v
            if not improved:                   # random kick
                for i in rng.sample(range(n), max(1, n // 20)):
                    c[i] = "1" if c[i] == "0" else "0"
                v = self.objective(p, c)
        return "".join(best)


# ----------------------------------------------------------------------------
# Small-object, deep-problem families: the object stays a few hundred to a few
# thousand symbols while the difficulty grows super-exponentially.  Each is the
# continuous relaxation of a famous existence question -- minimise violations;
# zero violations at a parameter beyond the known frontier settles the question.
# Known values below are from the literature and must be re-checked before
# publication.
# ----------------------------------------------------------------------------
def _popcount(x):
    return bin(x).count("1")


class Ramsey:
    """2-colour the edges of K_n; minimise (#K_s in colour 0) + (#K_t in colour 1)."""
    name = "ramsey"
    title = "Ramsey"
    sense = "min"
    # exact values and best lower bounds for R(s,t): n < R  => zero violations achievable
    KNOWN_R = {(3, 3): 6, (3, 4): 9, (3, 5): 14, (3, 6): 18, (3, 7): 23, (3, 8): 28, (3, 9): 36,
               (4, 4): 18, (4, 5): 25}
    LOWER_R = {(3, 10): 40, (4, 6): 36, (5, 5): 43}          # lower bounds; exact value open

    def params(self, rng):
        s, t = rng.choice([(3, 4), (3, 5), (4, 4), (3, 6), (4, 5), (3, 7)])
        R = self.KNOWN_R[(s, t)]
        return {"s": s, "t": t, "n": rng.randint(R - 2, R + 1)}

    def statement(self, p):
        s, t, n = p["s"], p["t"], p["n"]
        return (f"Colour every edge of the complete graph K_{n} on vertices 0..{n-1} red or blue so as to "
                f"minimise the number of red K_{s} plus the number of blue K_{t} (complete subgraphs on "
                f"{s} resp. {t} vertices all of whose edges have that colour). Output: a string of length "
                f"{n*(n-1)//2} over {{0,1}}, one character per edge {{i,j}} with i<j, ordered "
                f"(0,1),(0,2),...,(0,{n-1}),(1,2),...,({n-2},{n-1}); 0 = red, 1 = blue.")

    def _adj(self, p, col):
        n = p["n"]
        adj = [[0] * n, [0] * n]
        k = 0
        for i in range(n):
            for j in range(i + 1, n):
                c = int(col[k]); k += 1
                adj[c][i] |= 1 << j
                adj[c][j] |= 1 << i
        return adj

    def _cliques(self, adj_c, cand, k):
        if k == 0:
            return 1
        total = 0
        while cand:
            v = cand & -cand
            cand ^= v
            vi = v.bit_length() - 1
            total += self._cliques(adj_c, cand & adj_c[vi], k - 1)
        return total

    def objective(self, p, col):
        n = p["n"]
        adj = self._adj(p, col)
        full = (1 << n) - 1
        return self._cliques(adj[0], full, p["s"]) + self._cliques(adj[1], full, p["t"])

    def verify(self, p, ans):
        m = p["n"] * (p["n"] - 1) // 2
        if not isinstance(ans, str) or len(ans) != m or set(ans) - set("01"):
            return False, 0, f"answer must be a 0/1 string of length {m}"
        return True, self.objective(p, ans), ""

    def _through(self, adj_c, u, v, size):
        """monochromatic cliques of the given size in colour c that contain edge (u,v)"""
        W = adj_c[u] & adj_c[v]
        k = size - 2
        if k == 0:
            return 1
        if k == 1:
            return _popcount(W)
        total = 0
        cand = W
        while cand:
            w = cand & -cand
            cand ^= w
            wi = w.bit_length() - 1
            total += self._cliques(adj_c, cand & adj_c[wi], k - 1)
        return total

    def naive(self, p):
        n = p["n"]
        if n > 2 and n % 4 == 1 and all(n % i for i in range(2, int(n ** 0.5) + 1)):
            qr = {(i * i) % n for i in range(1, n)}                 # Paley colouring
            return "".join("0" if (j - i) % n in qr else "1" for i in range(n) for j in range(i + 1, n))
        rng = random.Random(0)
        best, bestv = None, None
        for _ in range(20):
            c = "".join(rng.choice("01") for _ in range(n * (n - 1) // 2))
            v = self.objective(p, c)
            if bestv is None or v < bestv:
                best, bestv = c, v
        return best

    def upper(self, p):                     # a LOWER bound on violations (sense = min)
        st = (p["s"], p["t"])
        R = self.KNOWN_R.get(st) or self.LOWER_R.get(st)
        return 0 if (R and p["n"] < R) else None

    def law(self, p, obj):
        from math import comb as _c
        tot = _c(p["n"], p["s"]) + _c(p["n"], p["t"])
        return {"name": f"ramsey_density_{p['s']}{p['t']}", "value": obj / tot, "better": "lower",
                "lower": 0.0 if self.upper(p) == 0 else None, "upper": None,
                "note": "0 attainable iff n < R(s,t); a zero at n >= the known lower bound is a new Ramsey bound"}

    def search(self, p, seconds, rng):
        n, s, t, end = p["n"], p["s"], p["t"], now() + seconds
        col = list(self.naive(p))
        adj = self._adj(p, col)
        v = self.objective(p, col)
        best, bestv = col[:], v
        edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
        size = {0: s, 1: t}
        while now() < end:
            improved = False
            for k in rng.sample(range(len(edges)), len(edges)):
                i, j = edges[k]
                c = int(col[k]); d = 1 - c
                loss = self._through(adj[c], i, j, size[c])
                adj[c][i] &= ~(1 << j); adj[c][j] &= ~(1 << i)
                adj[d][i] |= 1 << j; adj[d][j] |= 1 << i
                gain = self._through(adj[d], i, j, size[d])
                if gain <= loss:
                    col[k] = str(d); v += gain - loss
                    improved = improved or gain < loss
                else:
                    adj[d][i] &= ~(1 << j); adj[d][j] &= ~(1 << i)
                    adj[c][i] |= 1 << j; adj[c][j] |= 1 << i
                if now() >= end:
                    break
            if v < bestv:
                best, bestv = col[:], v
            if bestv == 0:
                break
            if not improved:
                for k in rng.sample(range(len(edges)), max(1, len(edges) // 20)):
                    col[k] = "1" if col[k] == "0" else "0"
                adj = self._adj(p, col); v = self.objective(p, col)
        return "".join(best)


class VanDerWaerden:
    """2-colour {1..N}; minimise the number of monochromatic k-term APs."""
    name = "vdw"
    title = "Van-der-Waerden"
    sense = "min"
    KNOWN_W = {3: 9, 4: 35, 5: 178, 6: 1132}           # exact W(2,k); W(2,7) >= 3703 open
    LOWER_W = {7: 3703}

    def params(self, rng):
        k = rng.choice([4, 5, 6])
        W = self.KNOWN_W[k]
        return {"k": k, "N": rng.randint(int(W * 0.85), W + 2)}

    def statement(self, p):
        return (f"Colour each of 1, 2, ..., {p['N']} red or blue so as to minimise the number of "
                f"monochromatic {p['k']}-term arithmetic progressions. Output: a string of length {p['N']} over {{0,1}}.")

    def objective(self, p, c):
        N, k, cnt = len(c), p["k"], 0
        for a in range(N):
            for d in range(1, (N - 1 - a) // (k - 1) + 1):
                x = c[a]
                if all(c[a + j * d] == x for j in range(1, k)):
                    cnt += 1
        return cnt

    def total_aps(self, p):
        N, k = p["N"], p["k"]
        return sum((N - 1 - a) // (k - 1) for a in range(N))

    def verify(self, p, ans):
        N = p["N"]
        if not isinstance(ans, str) or len(ans) != N or set(ans) - set("01"):
            return False, 0, f"answer must be a 0/1 string of length {N}"
        return True, self.objective(p, ans), ""

    def _through(self, c, i, k):
        N, cnt = len(c), 0
        for d in range(1, N):
            any_pos = False
            for j in range(k):
                lo = i - j * d
                if lo < 0 or lo + (k - 1) * d >= N:
                    continue
                any_pos = True
                x = c[lo]
                if all(c[lo + m * d] == x for m in range(1, k)):
                    cnt += 1
            if not any_pos and i - (k - 1) * d < 0 and i + (k - 1) * d >= N:
                break
        return cnt

    def naive(self, p):
        rng = random.Random(0)
        best, bestv = None, None
        for _ in range(20):
            c = "".join(rng.choice("01") for _ in range(p["N"]))
            v = self.objective(p, c)
            if bestv is None or v < bestv:
                best, bestv = c, v
        return best

    def upper(self, p):
        W = self.KNOWN_W.get(p["k"]) or self.LOWER_W.get(p["k"])
        return 0 if (W and p["N"] < W) else None

    def law(self, p, obj):
        return {"name": f"vdw_density_k{p['k']}", "value": obj / self.total_aps(p), "better": "lower",
                "lower": 0.0 if self.upper(p) == 0 else None, "upper": None,
                "note": "0 attainable iff N < W(2,k); W(2,7) is open"}

    def search(self, p, seconds, rng):
        N, k, end = p["N"], p["k"], now() + seconds
        best = list(self.naive(p)); bestv = self.objective(p, best)
        c, v = best[:], bestv
        while now() < end and bestv > 0:
            improved = False
            for i in rng.sample(range(N), N):
                before = self._through(c, i, k)
                c[i] = "1" if c[i] == "0" else "0"
                after = self._through(c, i, k)
                if after <= before:
                    v += after - before; improved = improved or after < before
                else:
                    c[i] = "1" if c[i] == "0" else "0"
                if now() >= end:
                    break
            if v < bestv:
                best, bestv = c[:], v
            if not improved:
                for i in rng.sample(range(N), max(1, N // 25)):
                    c[i] = "1" if c[i] == "0" else "0"
                v = self.objective(p, c)
        return "".join(best)


class Golomb:
    """m marks, all pairwise differences distinct; minimise the length."""
    name = "golomb"
    title = "Golomb"
    sense = "min"
    OPT = {2: 1, 3: 3, 4: 6, 5: 11, 6: 17, 7: 25, 8: 34, 9: 44, 10: 55, 11: 72, 12: 85, 13: 106, 14: 127,
           15: 151, 16: 177, 17: 199, 18: 216, 19: 246, 20: 283, 21: 333, 22: 356, 23: 372, 24: 425,
           25: 480, 26: 492, 27: 553}                       # proven optimal lengths; m >= 28 open

    def params(self, rng):
        return {"m": rng.randint(8, 20)}

    def statement(self, p):
        return (f"Find {p['m']} distinct non-negative integers, the first of them 0, such that all pairwise "
                f"differences are distinct (a Golomb ruler), minimising the largest integer (the length). "
                f"Output: the integers in increasing order as a JSON list.")

    def objective(self, p, marks):
        return max(marks) - min(marks)

    def verify(self, p, ans):
        m = p["m"]
        if not isinstance(ans, list) or len(ans) != m or any(not isinstance(v, int) or v < 0 for v in ans):
            return False, 0, f"answer must be a list of {m} non-negative integers"
        if len(set(ans)) != m:
            return False, 0, "marks must be distinct"
        diffs = set()
        for a, b in combinations(sorted(ans), 2):
            if b - a in diffs:
                return False, 0, f"repeated difference {b - a}"
            diffs.add(b - a)
        return True, self.objective(p, ans), ""

    def naive(self, p):                                 # Mian-Chowla prefix
        marks, diffs = [0], set()
        while len(marks) < p["m"]:
            x = marks[-1] + 1
            while True:
                nd = {x - a for a in marks}
                if len(nd) == len(marks) and not (nd & diffs):
                    break
                x += 1
            diffs |= nd; marks.append(x)
        return marks

    def upper(self, p):                                 # a LOWER bound on the length (sense = min)
        return self.OPT.get(p["m"])

    def law(self, p, obj):
        m = p["m"]
        return {"name": "golomb_len_over_m2", "value": obj / (m * m), "better": "lower",
                "lower": (self.OPT[m] / (m * m)) if m in self.OPT else None, "upper": 1.0,
                "note": "Erdos conjecture G(m) < m^2; optimal lengths proven only to m = 27"}

    def search(self, p, seconds, rng):
        m, end = p["m"], now() + seconds
        best = sorted(self.naive(p)); bestv = best[-1]
        cur = best[:]
        while now() < end and bestv > (self.OPT.get(m) or 0):
            r = rng.randint(1, min(3, m - 2))
            keep = [0] + sorted(rng.sample(cur[1:], m - 1 - r))
            diffs = {b - a for a, b in combinations(keep, 2)}
            marks = keep[:]
            ok = True
            while len(marks) < m:
                cap = bestv - 1 if len(marks) == m - 1 else bestv + 20
                feas = []
                for x in range(1, cap + 1):
                    if x in marks:
                        continue
                    nd = {abs(x - a) for a in marks}
                    if len(nd) == len(marks) and not (nd & diffs):
                        feas.append((x, nd))
                        if len(feas) >= 6:
                            break
                if not feas:
                    ok = False
                    break
                x, nd = feas[rng.randrange(len(feas))]
                diffs |= nd; marks.append(x); marks.sort()
            if not ok:
                cur = best[:]
                continue
            cur = marks
            if cur[-1] < bestv:
                best, bestv = cur[:], cur[-1]
            elif rng.random() < 0.5:
                cur = best[:]
        return best


class Costas:
    """A permutation whose difference vectors are all distinct; minimise repeats."""
    name = "costas"
    title = "Costas"
    sense = "min"

    def params(self, rng):
        return {"n": rng.randint(10, 34)}

    def statement(self, p):
        n = p["n"]
        return (f"Find a permutation p of 0..{n-1} such that the {n*(n-1)//2} vectors (j - i, p[j] - p[i]) for "
                f"i < j are all distinct (a Costas array), minimising the number of repeats "
                f"(sum over vectors of max(0, multiplicity - 1)). Output: the permutation as a JSON list.")

    def objective(self, p, perm):
        cnt = {}
        n = len(perm)
        for i in range(n):
            for j in range(i + 1, n):
                v = (j - i, perm[j] - perm[i])
                cnt[v] = cnt.get(v, 0) + 1
        return sum(c - 1 for c in cnt.values() if c > 1)

    def verify(self, p, ans):
        n = p["n"]
        if not isinstance(ans, list) or sorted(ans) != list(range(n)):
            return False, 0, f"answer must be a permutation of 0..{n-1}"
        return True, self.objective(p, ans), ""

    def naive(self, p):                                 # Welch when n+1 is prime, else random
        n = p["n"]; q = n + 1
        if all(q % i for i in range(2, int(q ** 0.5) + 1)):
            for g in range(2, q):
                if len({pow(g, e, q) for e in range(1, q)}) == q - 1:
                    return [pow(g, e, q) - 1 for e in range(1, q)]
        rng = random.Random(0)
        best, bestv = None, None
        for _ in range(20):
            perm = list(range(n)); rng.shuffle(perm)
            v = self.objective(p, perm)
            if bestv is None or v < bestv:
                best, bestv = perm, v
        return best

    def upper(self, p):
        return 0 if p["n"] <= 31 else None             # Costas arrays known for all n <= 31; 32, 33 open

    def law(self, p, obj):
        from math import comb as _c
        return {"name": "costas_repeat_density", "value": obj / _c(p["n"], 2), "better": "lower",
                "lower": 0.0 if p["n"] <= 31 else None, "upper": None,
                "note": "existence open at n = 32, 33"}

    def search(self, p, seconds, rng):
        n, end = p["n"], now() + seconds
        best = list(self.naive(p)); bestv = self.objective(p, best)
        perm, v = best[:], bestv
        while now() < end and bestv > 0:
            i, j = rng.sample(range(n), 2)
            perm[i], perm[j] = perm[j], perm[i]
            v2 = self.objective(p, perm)
            if v2 <= v:
                v = v2
                if v < bestv:
                    best, bestv = perm[:], v
            else:
                perm[i], perm[j] = perm[j], perm[i]
            if rng.random() < 0.01:                        # kick
                a, b = rng.sample(range(n), 2)
                perm[a], perm[b] = perm[b], perm[a]; v = self.objective(p, perm)
        return best


class Hadamard:
    """n x n +-1 matrix; minimise the off-diagonal energy of H H^T (zero = Hadamard)."""
    name = "hadamard"
    title = "Hadamard"
    sense = "min"

    def params(self, rng):
        return {"n": rng.choice([12, 16, 20, 24, 28])}

    def statement(self, p):
        n = p["n"]
        return (f"Find an {n} x {n} matrix H with entries +1/-1 minimising sum over i != j of (row_i . row_j)^2 "
                f"(zero means H is a Hadamard matrix). Output: a JSON list of {n} strings of length {n} over "
                f"{{+,-}}, one per row.")

    def _rows(self, ans):
        return [[1 if ch == "+" else -1 for ch in r] for r in ans]

    def objective(self, p, H):
        if H and isinstance(H[0], str):
            H = self._rows(H)
        n = len(H)
        E = 0
        for i in range(n):
            for j in range(i + 1, n):
                g = sum(a * b for a, b in zip(H[i], H[j]))
                E += 2 * g * g
        return E

    def verify(self, p, ans):
        n = p["n"]
        if not isinstance(ans, list) or len(ans) != n or any(not isinstance(r, str) or len(r) != n or set(r) - set("+-") for r in ans):
            return False, 0, f"answer must be {n} strings of length {n} over +/-"
        return True, self.objective(p, self._rows(ans)), ""

    def _fmt(self, H):
        return ["".join("+" if x > 0 else "-" for x in r) for r in H]

    def naive(self, p):
        n = p["n"]
        if n & (n - 1) == 0:                              # Sylvester
            H = [[1]]
            while len(H) < n:
                H = [r + r for r in H] + [r + [-x for x in r] for r in H]
            return self._fmt(H)
        q = n - 1
        if q % 4 == 3 and all(q % i for i in range(2, int(q ** 0.5) + 1)):   # Paley I
            chi = lambda x: 0 if x % q == 0 else (1 if pow(x % q, (q - 1) // 2, q) == 1 else -1)
            Q = [[chi(j - i) for j in range(q)] for i in range(q)]
            H = [[1] * n] + [[-1] + [Q[i][j] + (1 if i == j else 0) for j in range(q)] for i in range(q)]
            return self._fmt(H)
        rng = random.Random(0)
        best, bestv = None, None
        for _ in range(10):
            H = [[rng.choice((1, -1)) for _ in range(n)] for _ in range(n)]
            v = self.objective(p, H)
            if bestv is None or v < bestv:
                best, bestv = H, v
        return self._fmt(best)

    def upper(self, p):
        return 0                                          # Hadamard matrices exist for every n = 0 mod 4 below 668

    def law(self, p, obj):
        n = p["n"]
        return {"name": "hadamard_energy", "value": obj / (n * n * (n - 1)), "better": "lower",
                "lower": 0.0, "upper": None, "note": "random +-1 rows give about 1; smallest open order is 668"}

    def search(self, p, seconds, rng):
        n, end = p["n"], now() + seconds
        H = self._rows(self.naive(p))
        G = [[sum(a * b for a, b in zip(H[i], H[j])) for j in range(n)] for i in range(n)]
        v = sum(G[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        best, bestv = [r[:] for r in H], v
        while now() < end and bestv > 0:
            i, k = rng.randrange(n), rng.randrange(n)
            old = H[i][k]
            delta = 0
            newG = {}
            for j in range(n):
                if j == i:
                    continue
                g2 = G[i][j] - 2 * old * H[j][k]
                delta += 2 * (g2 * g2 - G[i][j] * G[i][j])
                newG[j] = g2
            if delta <= 0 or rng.random() < 0.002:
                H[i][k] = -old
                for j, g2 in newG.items():
                    G[i][j] = G[j][i] = g2
                v += delta
                if v < bestv:
                    best, bestv = [r[:] for r in H], v
        return self._fmt(best)


FAMILIES = {f.name: f for f in (APFree(), Sidon(), BinaryCode(), CapSet(), NoThreeInLine(), LABS(), Heilbronn(), Mono3AP(),
                                Ramsey(), VanDerWaerden(), Golomb(), Costas(), Hadamard())}


# ----------------------------------------------------------------------------
# Twisted variants: the same verifiers, but each instance carries random data
# (a random ground set, a random forbidden set, a random candidate pool, random
# fixed positions) that no table, formula or memorised construction covers.
# Every instance's optimum is unknown; the fixed-budget search is the anchor.
# ----------------------------------------------------------------------------
class APFreeSub(APFree):
    """Largest 3-AP-free subset of a *given* random subset A of {1..n}."""
    name = "apfree_sub"
    title = "AP-Free-Subset"

    def params(self, rng):
        n = rng.randint(120, 400)
        A = sorted(rng.sample(range(1, n + 1), n // 2))
        return {"k": 3, "n": n, "A": A}

    def statement(self, p):
        return (f"Let A = {p['A']} (a subset of {{1, ..., {p['n']}}}). Find a subset S of A of maximum possible size "
                f"containing no 3-term arithmetic progression. Output: the elements of S in strictly increasing order, "
                f"as a JSON list of integers.")

    def ground(self, p):
        return list(p["A"])

    def verify(self, p, ans):
        ok, obj, msg = super().verify(p, ans)
        if ok and not set(ans) <= set(p["A"]):
            return False, 0, "elements must belong to A"
        return ok, obj, msg

    def naive(self, p):
        return sorted(self.greedy(p, list(p["A"]))["S"])

    def upper(self, p):
        return None

    def law(self, p, obj):
        m = len(p["A"])
        c = -math.log(obj / m) / math.sqrt(math.log(m)) if obj > 0 else float("inf")
        return {"name": "behrend_c_sub", "value": c, "better": "lower", "lower": None, "upper": None,
                "note": "Behrend form relative to |A|; no table applies"}


class SidonMod(SetFamily):
    """Sidon set in Z_m avoiding a random forbidden residue set F: all a+b mod m (a<=b) distinct."""
    name = "sidon_mod"
    title = "Sidon-Mod"

    def params(self, rng):
        m = rng.randint(150, 600)
        F = sorted(rng.sample(range(m), m // 4))
        return {"m": m, "F": F}

    def statement(self, p):
        return (f"Find a subset S of Z_{p['m']} = {{0, ..., {p['m']-1}}} of maximum possible size such that no element "
                f"of S lies in F = {p['F']} and all pairwise sums a + b mod {p['m']} (a <= b, both in S) are distinct. "
                f"Output: the elements of S in increasing order as a JSON list of integers.")

    def ground(self, p):
        F = set(p["F"])
        return [x for x in range(p["m"]) if x not in F]

    def new_state(self, p):
        return {"S": set(), "sums": set()}

    def can_add(self, p, st, x):
        m = p["m"]
        if (2 * x) % m in st["sums"]:
            return False
        seen = set()
        for s in st["S"]:
            v = (x + s) % m
            if v in st["sums"] or v in seen:
                return False
            seen.add(v)
        return (2 * x) % m not in seen

    def add(self, p, st, x):
        m = p["m"]
        for s in st["S"]:
            st["sums"].add((x + s) % m)
        st["sums"].add((2 * x) % m)
        st["S"].add(x)

    def verify(self, p, ans):
        m, F = p["m"], set(p["F"])
        if not isinstance(ans, list) or any(not isinstance(v, int) for v in ans):
            return False, 0, "answer must be a list of integers"
        if len(set(ans)) != len(ans) or any(v < 0 or v >= m for v in ans):
            return False, 0, "elements must be distinct residues in range"
        if any(v in F for v in ans):
            return False, 0, "an element lies in the forbidden set F"
        seen = set()
        for i, a in enumerate(ans):
            for b in ans[i:]:
                v = (a + b) % m
                if v in seen:
                    return False, 0, f"repeated sum {v} mod {m}"
                seen.add(v)
        return True, len(ans), ""

    def naive(self, p):
        return sorted(self.greedy(p, self.ground(p))["S"])

    def upper(self, p):                     # |S|(|S|-1) <= m-1 for a modular Sidon set
        return int((1 + math.sqrt(4 * p["m"] - 3)) / 2)

    def law(self, p, obj):
        return {"name": "sidon_mod_ratio", "value": obj / math.sqrt(p["m"]), "better": "higher",
                "lower": None, "upper": 1.0, "note": "|S|/sqrt(m); the modular bound is ~1 with 3/4 of residues allowed"}


class CodePool(BinaryCode):
    """Largest code with minimum distance d drawn from a given random pool of words."""
    name = "code_pool"
    title = "Code-Pool"

    def params(self, rng):
        n = rng.randint(9, 12); d = rng.choice([3, 4, 5])
        pool = sorted(rng.sample(range(1 << n), (1 << n) // 4))
        return {"n": n, "d": d, "pool": [format(w, f"0{n}b") for w in pool]}

    def statement(self, p):
        return (f"From the pool P of binary words of length {p['n']} listed below, choose as many words as possible "
                f"such that any two chosen words differ in at least {p['d']} positions. P = {p['pool']}. "
                f"Output: a JSON list of the chosen words as strings of 0/1.")

    def ground(self, p):
        return [int(w, 2) for w in p["pool"]]

    def candidates(self, p, rng):
        g = self.ground(p); rng.shuffle(g); return g

    def verify(self, p, ans):
        ok, obj, msg = super().verify(p, ans)
        if ok and not set(ans) <= set(p["pool"]):
            return False, 0, "a word is not in the pool"
        return ok, obj, msg

    def naive(self, p):
        return sorted(self.greedy(p, self.ground(p))["S"])

    def upper(self, p):
        return min(super().upper(p), len(p["pool"]))

    def law(self, p, obj):
        return {"name": "pool_rate", "value": math.log2(obj) / p["n"] if obj > 0 else float("-inf"), "better": "higher",
                "lower": None, "upper": math.log2(self.upper(p)) / p["n"], "note": "rate within a quarter-density random pool"}


class GolombForbid(Golomb):
    """Golomb ruler whose differences must also avoid a random forbidden set F."""
    name = "golomb_forbid"
    title = "Golomb-Forbid"

    def params(self, rng):
        m = rng.randint(6, 12)
        F = sorted(rng.sample(range(1, 4 * m * m), m * m // 2))
        return {"m": m, "F": F}

    def statement(self, p):
        return (f"Find {p['m']} distinct non-negative integers, the first of them 0, such that all pairwise differences "
                f"are distinct and none of them lies in F = {p['F']}, minimising the largest integer (the length). "
                f"Output: the integers in increasing order as a JSON list.")

    def verify(self, p, ans):
        ok, obj, msg = super().verify(p, ans)
        if ok:
            F = set(p["F"])
            for a, b in combinations(sorted(ans), 2):
                if b - a in F:
                    return False, 0, f"difference {b - a} is forbidden"
        return ok, obj, msg

    def _feasible_pos(self, marks, diffs, x, F):
        if x in marks:
            return None
        nd = {abs(x - a) for a in marks}
        if len(nd) != len(marks) or (nd & diffs) or (nd & F):
            return None
        return nd

    def naive(self, p):
        F = set(p["F"]); marks, diffs = [0], set()
        while len(marks) < p["m"]:
            x = marks[-1] + 1
            while True:
                nd = self._feasible_pos(marks, diffs, x, F)
                if nd is not None:
                    break
                x += 1
            diffs |= nd; marks.append(x)
        return marks

    def upper(self, p):
        return None

    def law(self, p, obj):
        m = p["m"]
        return {"name": "golomb_forbid_len_over_m2", "value": obj / (m * m), "better": "lower", "lower": None, "upper": None,
                "note": "no table applies with a random forbidden set"}

    def search(self, p, seconds, rng):
        m, end, F = p["m"], now() + seconds, set(p["F"])
        best = sorted(self.naive(p)); bestv = best[-1]
        cur = best[:]
        while now() < end:
            r = rng.randint(1, min(3, m - 2))
            keep = [0] + sorted(rng.sample(cur[1:], m - 1 - r))
            diffs = {b - a for a, b in combinations(keep, 2)}
            marks = keep[:]; ok = True
            while len(marks) < m:
                cap = bestv - 1 if len(marks) == m - 1 else bestv + 40
                feas = []
                for x in range(1, cap + 1):
                    nd = self._feasible_pos(marks, diffs, x, F)
                    if nd is not None:
                        feas.append((x, nd))
                        if len(feas) >= 6:
                            break
                if not feas:
                    ok = False; break
                x, nd = feas[rng.randrange(len(feas))]
                diffs |= nd; marks.append(x); marks.sort()
            if not ok:
                cur = best[:]; continue
            cur = marks
            if cur[-1] < bestv:
                best, bestv = cur[:], cur[-1]
            elif rng.random() < 0.5:
                cur = best[:]
        return best


class CostasFixed(Costas):
    """Costas array completion: some positions are pre-assigned at random."""
    name = "costas_fixed"
    title = "Costas-Fixed"

    def params(self, rng):
        n = rng.randint(8, 14)
        k = max(2, n // 4)
        perm = list(range(n)); rng.shuffle(perm)
        idx = sorted(rng.sample(range(n), k))
        return {"n": n, "fixed": {str(i): perm[i] for i in idx}}

    def statement(self, p):
        n = p["n"]
        fx = ", ".join(f"p[{i}] = {v}" for i, v in p["fixed"].items())
        return (f"Find a permutation p of 0..{n-1} with the pre-assigned values {fx}, such that the {n*(n-1)//2} vectors "
                f"(j - i, p[j] - p[i]) for i < j are all distinct (a Costas array), minimising the number of repeats "
                f"(sum over vectors of max(0, multiplicity - 1)). Output: the full permutation as a JSON list.")

    def verify(self, p, ans):
        ok, obj, msg = super().verify(p, ans)
        if ok:
            for i, v in p["fixed"].items():
                if ans[int(i)] != v:
                    return False, 0, f"p[{i}] must equal {v}"
        return ok, obj, msg

    def _random_completion(self, p, rng):
        n = p["n"]; fixed = {int(i): v for i, v in p["fixed"].items()}
        free_vals = [v for v in range(n) if v not in fixed.values()]; rng.shuffle(free_vals)
        perm = [None] * n
        for i, v in fixed.items():
            perm[i] = v
        it = iter(free_vals)
        for i in range(n):
            if perm[i] is None:
                perm[i] = next(it)
        return perm

    def naive(self, p):
        rng = random.Random(0); best, bestv = None, None
        for _ in range(20):
            perm = self._random_completion(p, rng); v = self.objective(p, perm)
            if bestv is None or v < bestv:
                best, bestv = perm, v
        return best

    def upper(self, p):
        return None

    def law(self, p, obj):
        from math import comb as _c
        return {"name": "costas_fixed_repeat_density", "value": obj / _c(p["n"], 2), "better": "lower",
                "lower": None, "upper": None, "note": "completion with random fixed positions; optimum unknown per instance"}

    def search(self, p, seconds, rng):
        n, end = p["n"], now() + seconds
        fixed = {int(i) for i in p["fixed"]}
        free = [i for i in range(n) if i not in fixed]
        best = list(self.naive(p)); bestv = self.objective(p, best)
        perm, v = best[:], bestv
        while now() < end and bestv > 0 and len(free) >= 2:
            i, j = rng.sample(free, 2)
            perm[i], perm[j] = perm[j], perm[i]
            v2 = self.objective(p, perm)
            if v2 <= v:
                v = v2
                if v < bestv:
                    best, bestv = perm[:], v
            else:
                perm[i], perm[j] = perm[j], perm[i]
            if rng.random() < 0.01:
                a, b = rng.sample(free, 2); perm[a], perm[b] = perm[b], perm[a]; v = self.objective(p, perm)
        return best


class VdWFixed(VanDerWaerden):
    """Van der Waerden colouring completion: a random 30% of positions are pre-coloured."""
    name = "vdw_fixed"
    title = "VdW-Fixed"

    def params(self, rng):
        k = rng.choice([4, 5])
        W = self.KNOWN_W[k]
        N = rng.randint(int(W * 0.8), W - 1)
        idx = sorted(rng.sample(range(N), int(0.3 * N)))
        return {"k": k, "N": N, "fixed": {str(i + 1): rng.choice("01") for i in idx}}

    def statement(self, p):
        fx = ", ".join(f"{i}:{c}" for i, c in p["fixed"].items())
        return (f"Colour each of 1, 2, ..., {p['N']} red (0) or blue (1) so as to minimise the number of monochromatic "
                f"{p['k']}-term arithmetic progressions, subject to these pre-assigned colours (position:colour): {fx}. "
                f"Output: a string of length {p['N']} over {{0,1}}, whose i-th character (1-indexed) is the colour of i.")

    def _fixed_idx(self, p):
        return {int(i) - 1: c for i, c in p["fixed"].items()}

    def verify(self, p, ans):
        ok, obj, msg = super().verify(p, ans)
        if ok:
            for i, c in self._fixed_idx(p).items():
                if ans[i] != c:
                    return False, 0, f"position {i+1} must be coloured {c}"
        return ok, obj, msg

    def _random_fill(self, p, rng):
        fx = self._fixed_idx(p)
        return "".join(fx.get(i, rng.choice("01")) for i in range(p["N"]))

    def naive(self, p):
        rng = random.Random(0); best, bestv = None, None
        for _ in range(20):
            c = self._random_fill(p, rng); v = self.objective(p, c)
            if bestv is None or v < bestv:
                best, bestv = c, v
        return best

    def upper(self, p):
        return None

    def law(self, p, obj):
        return {"name": f"vdw_fixed_density_k{p['k']}", "value": obj / self.total_aps(p), "better": "lower",
                "lower": None, "upper": None, "note": "completion with 30% pre-coloured positions"}

    def search(self, p, seconds, rng):
        N, k, end = p["N"], p["k"], now() + seconds
        fx = self._fixed_idx(p); free = [i for i in range(N) if i not in fx]
        best = list(self.naive(p)); bestv = self.objective(p, best)
        c, v = best[:], bestv
        while now() < end and bestv > 0 and free:
            improved = False
            for i in rng.sample(free, len(free)):
                before = self._through(c, i, k)
                c[i] = "1" if c[i] == "0" else "0"
                after = self._through(c, i, k)
                if after <= before:
                    v += after - before; improved = improved or after < before
                else:
                    c[i] = "1" if c[i] == "0" else "0"
                if now() >= end:
                    break
            if v < bestv:
                best, bestv = c[:], v
            if not improved:
                for i in rng.sample(free, max(1, len(free) // 25)):
                    c[i] = "1" if c[i] == "0" else "0"
                v = self.objective(p, c)
        return "".join(best)


FAMILIES.update({f.name: f for f in (APFreeSub(), SidonMod(), CodePool(), GolombForbid(), CostasFixed(), VdWFixed())})



# ----------------------------------------------------------------------------
# Open-ceiling additions (2026-09-11).  Selection rule for the headline set: the
# best construction and the best upper bound must diverge with the size, so a
# system can keep scoring all the way up.  HEADROOM below tags every family.
# ----------------------------------------------------------------------------
class Kissing(SetFamily):
    """Kissing configurations; quadratic coordinates are explicitly opt-in."""
    name = "kissing"
    title = "Kissing"
    B = 1000                                   # coordinate bound: keeps int64 arithmetic exact for d <= 16
    KNOWN_LOWER = {5: 40, 6: 72, 7: 126, 8: 240, 9: 306, 10: 510, 11: 604, 12: 841, 13: 1154, 14: 1932, 15: 2564, 16: 4320}   # d=11: 604 (arXiv:2606.10402, 2026), d=12: 841 (arXiv:2606.18984, 2026); checked 2026-09-13
    KNOWN_UPPER = {5: 44, 6: 77, 7: 134, 8: 240, 9: 363, 10: 553, 11: 868, 12: 1355, 13: 2064, 14: 3174, 15: 4853, 16: 7320}   # d=6: 77 (SDP); checked 2026-09-13
    _pools = {}

    def law(self, p, obj):
        d = p["d"]
        lo, hi = self.KNOWN_LOWER.get(d), self.KNOWN_UPPER.get(d)
        return {"name": "kissing_exponent", "value": (math.log2(obj) / d) if obj > 0 else None, "better": "higher",
                "lower": (math.log2(lo) / d) if lo else None, "upper": (math.log2(hi) / d) if hi else None,
                "note": "log2(kissing number)/d; the interval is the known band at this d (table values, re-check); "
                        "asymptotically 0.2075 <= exponent <= 0.401; exact only at d = 1..4, 8, 24"}

    def params(self, rng):
        return {"d": rng.choice([6, 7, 9, 10, 11, 12])}

    def statement(self, p):
        d = p["d"]
        if p.get("representation") == "quadratic":
            return (f"Find as many nonzero vectors in R^{d} as possible such that the angle between any two "
                    "is at least 60 degrees: u.v <= |u| |v| / 2. Coordinates may be integers or exact numbers "
                    "a+b*sqrt(3), where a and b are integers in [-1000,1000]. "
                    f"For integer coordinates, output a JSON list of vectors of {d} integers in [-1000,1000]. "
                    "Alternatively, output {\"quadratic_vectors\": {\"radicand\": 3, \"vectors\": V}}, "
                    f"where V is a list of vectors, each with {d} pairs [a,b] representing a+b*sqrt(3). "
                    "Use [a,0] for an integer coordinate. At most 20000 vectors are accepted. "
                    "All angle comparisons are exact; decimal approximations and symbolic strings are not accepted.")
        return (f"Find as many nonzero integer vectors in Z^{d} as possible (entries in [-{self.B}, {self.B}]) such that the "
                f"angle between any two of them is at least 60 degrees, i.e. for every pair u != v: u.v <= |u| |v| / 2 "
                f"(a kissing configuration: after normalisation the vectors are the centres of non-overlapping unit spheres "
                f"all touching a central unit sphere). Output: a JSON list of vectors, each a JSON list of {d} integers.")

    def compact_hint(self, p):
        if p.get("representation") == "quadratic":
            return ('Compact integer form allowed: {"orbit": [v1, v2, ...], "signs": true, "perms": true}, '
                    'where every generator is a vector of d integers in [-1000,1000]. '
                    'This denotes its coordinate permutations and sign changes as selected by the flags. '
                    'For quadratic coordinates, use the explicit coefficient pairs in quadratic_vectors.')
        return None

    def _pool(self, p):
        d = p["d"]
        if d not in self._pools:
            pool = []
            for i in range(d):
                for j in range(i + 1, d):
                    for si in (1, -1):
                        for sj in (1, -1):
                            v = [0] * d; v[i], v[j] = si, sj; pool.append(tuple(v))
            for i in range(d):
                for si in (1, -1):
                    v = [0] * d; v[i] = si; pool.append(tuple(v))
            for mask in range(1 << d):                                  # (+-1)^d, the E8 / Barnes-Wall ingredient
                pool.append(tuple(1 if mask >> i & 1 else -1 for i in range(d)))
            for k in (3, 4):                                            # sparse {0, +-1} vectors
                for idx in combinations(range(d), k):
                    for signs in range(1 << k):
                        v = [0] * d
                        for t, i in enumerate(idx):
                            v[i] = 1 if signs >> t & 1 else -1
                        pool.append(tuple(v))
            self._pools[d] = pool
        return self._pools[d]

    def ground(self, p):
        return range(len(self._pool(p)))

    def new_state(self, p):
        return {"S": set(), "V": [], "N2": []}

    def add(self, p, st, x):
        v = self._pool(p)[x]
        st["S"].add(x); st["V"].append(v); st["N2"].append(sum(c * c for c in v))

    def can_add(self, p, st, x):
        if not st["V"]:
            return True
        v = np.asarray(self._pool(p)[x], dtype=np.int64)
        A = np.asarray(st["V"], dtype=np.int64)
        dots = A @ v
        bad = (dots > 0) & (4 * dots * dots > np.asarray(st["N2"], dtype=np.int64) * int(v @ v))
        return not bool(bad.any())

    def verify(self, p, ans):
        if isinstance(ans, dict) and "quadratic_vectors" in ans:
            from quadratic_kissing import verify
            return verify(p, ans)
        if p.get("representation") == "quadratic":
            if type(p.get("d")) is not int or not 1 <= p["d"] <= 16:
                return False, 0, "dimension must be an integer from 1 to 16"
            if isinstance(ans, list) and len(ans) > 20000:
                return False, 0, "too many vectors (limit 20000)"
        d, B = p["d"], self.B
        if d > 16:
            return False, 0, "d > 16 is outside the range this verifier evaluates exactly (int64 angle test); not accepted"
        if not isinstance(ans, list) or not ans or any(not (isinstance(v, list) and len(v) == d) for v in ans):
            return False, 0, f"answer must be a non-empty list of integer vectors of length {d}"
        if any(not all(isinstance(c, int) and not isinstance(c, bool) and -B <= c <= B for c in v) for v in ans):
            return False, 0, f"entries must be integers in [-{B}, {B}]"
        A = np.asarray(ans, dtype=np.int64)
        n2 = (A * A).sum(axis=1)
        if (n2 == 0).any():
            return False, 0, "the zero vector is not allowed"
        G = A @ A.T
        m = len(ans)
        iu = np.triu_indices(m, 1)
        g = G[iu]
        bad = (g > 0) & (4 * g * g > n2[iu[0]] * n2[iu[1]])
        if bad.any():
            i, j = iu[0][bad.argmax()], iu[1][bad.argmax()]
            return False, 0, f"vectors {i} and {j} are less than 60 degrees apart"
        return True, m, ""

    def naive(self, p):                        # the D_d root system: 2 d (d - 1) vectors
        d = p["d"]
        out = []
        for i in range(d):
            for j in range(i + 1, d):
                for si in (1, -1):
                    for sj in (1, -1):
                        v = [0] * d; v[i], v[j] = si, sj; out.append(v)
        return out

    def upper(self, p):
        return self.KNOWN_UPPER.get(p["d"])

    def search(self, p, seconds, rng):
        pool = self._pool(p)
        return [list(pool[i]) for i in super().search(p, seconds, rng)]


class Corners(SetFamily):
    """Subset of the n x n grid with no corner (x,y), (x+d,y), (x,y+d), d != 0."""
    name = "corners"
    title = "Corner-Free"

    def law(self, p, obj):
        n = p["n"]
        dens = obj / (n * n)
        c = (-math.log(dens) / math.sqrt(math.log(n))) if 0 < dens < 1 and n > 2 else None
        return {"name": "corner_c", "value": c, "better": "lower", "lower": None, "upper": None,
                "note": "|S| = n^2 exp(-c sqrt(ln n)); Behrend-type constructions give a finite c; the upper bound "
                        "n^2 / (log log n)^c' (Shkredov) leaves the growth open"}

    def params(self, rng):
        return {"n": rng.randint(12, 40)}

    def statement(self, p):
        n = p["n"]
        return (f"Find a subset S of the grid {{0..{n-1}}}^2 of maximum possible size containing no corner, i.e. no three "
                f"points (x, y), (x + d, y), (x, y + d) with d != 0 (d may be negative). Output: a JSON list of [x, y] "
                f"integer pairs.")

    def ground(self, p):
        return range(p["n"] * p["n"])

    def new_state(self, p):
        return {"S": set(), "rows": {}, "cols": {}}

    def add(self, p, st, x):
        n = p["n"]
        xx, yy = divmod(x, n)
        st["S"].add(x)
        st["rows"].setdefault(yy, set()).add(xx)
        st["cols"].setdefault(xx, set()).add(yy)

    def can_add(self, p, st, x):
        n = p["n"]
        xx, yy = divmod(x, n)
        S = st["S"]
        for x2 in st["rows"].get(yy, ()):          # corner with horizontal leg (xx,yy)-(x2,yy)
            d = x2 - xx
            if 0 <= yy + d < n and (xx * n + yy + d) in S:      # (xx, yy) is the corner point
                return False
            if 0 <= yy - d < n and (x2 * n + yy - d) in S:      # (x2, yy) is the corner point
                return False
        for y2 in st["cols"].get(xx, ()):          # (xx, yy) is the top point (a, b + d) of a corner at (xx, y2)
            d = yy - y2
            if 0 <= xx + d < n and ((xx + d) * n + y2) in S:
                return False
        return True

    def verify(self, p, ans):
        n = p["n"]
        if not isinstance(ans, list) or any(not (isinstance(q, list) and len(q) == 2) for q in ans):
            return False, 0, "answer must be a list of [x, y] pairs"
        pts = [tuple(q) for q in ans]
        if any(not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < n for c in q) for q in pts) or len(set(pts)) != len(pts):
            return False, 0, "points must be distinct integer grid points in range"
        S = set(pts)
        rows = {}
        for (x, y) in pts:
            rows.setdefault(y, []).append(x)
        for y, xs in rows.items():
            for x1 in xs:
                for x2 in xs:
                    d = x2 - x1
                    if d and (x1, y + d) in S:
                        return False, 0, f"corner at ({x1}, {y}), ({x2}, {y}), ({x1}, {y + d})"
        return True, len(pts), ""

    def naive(self, p):                        # {(x, y): x - y in A}, A a shifted base-3 {0,1}-digit set (3-AP-free)
        n = p["n"]
        A = set()
        t = 0
        while t <= 2 * n - 2:
            if all(c in "01" for c in _base3(t)):
                A.add(t - (n - 1))
            t += 1
        return [[x, y] for x in range(n) for y in range(n) if (x - y) in A]

    def upper(self, p):
        return None

    def search(self, p, seconds, rng):
        n = p["n"]
        return [list(divmod(v, n)) for v in super().search(p, seconds, rng)]


def _base3(t):
    if t == 0:
        return "0"
    out = ""
    while t:
        out = str(t % 3) + out; t //= 3
    return out


class UnitDistance:
    """n integer points; maximise the number of pairs at the most frequent squared distance."""
    name = "unitdist"
    title = "Unit-Distance"
    sense = "max"
    G = 1000

    def law(self, p, obj):
        n = p["n"]
        a = (math.log(obj / n) / math.log(n)) if obj > n else 0.0
        return {"name": "unit_distance_exponent", "value": a, "better": "higher", "lower": 0.0, "upper": 1 / 3,
                "note": "u(n) = n^(1 + a); lattice sections give a ~ c / log log n, the proven bound is a <= 1/3"}

    def params(self, rng):
        return {"n": rng.randint(20, 80)}

    def statement(self, p):
        n, G = p["n"], self.G
        return (f"Place {n} distinct points with integer coordinates in [0, {G}]^2 so as to maximise the number of pairs "
                f"of points at the most frequent squared distance, i.e. maximise max over D of #{{ {{P, Q}} : |P - Q|^2 = D }} "
                f"(the unit-distance problem after scaling). Output: a JSON list of exactly {n} [x, y] integer pairs.")

    def objective(self, p, pts):
        cnt = {}
        m = len(pts)
        for i in range(m):
            xi, yi = pts[i]
            for j in range(i + 1, m):
                dx, dy = xi - pts[j][0], yi - pts[j][1]
                D = dx * dx + dy * dy
                cnt[D] = cnt.get(D, 0) + 1
        return max(cnt.values()) if cnt else 0

    def verify(self, p, ans):
        n, G = p["n"], self.G
        if not isinstance(ans, list) or len(ans) != n or any(not (isinstance(q, list) and len(q) == 2) for q in ans):
            return False, 0, f"answer must be a list of exactly {n} [x, y] pairs"
        pts = [tuple(q) for q in ans]
        if any(not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= G for c in q) for q in pts) or len(set(pts)) != n:
            return False, 0, "points must be distinct integer points in range"
        return True, self.objective(p, pts), ""

    def _grid(self, n, k):
        pts = [(i, j) for i in range(k) for j in range(k)]
        return [list(q) for q in pts[:n]]

    def naive(self, p):
        n = p["n"]
        return self._grid(n, math.ceil(math.sqrt(n)))

    def upper(self, p):
        return None                            # u(n) <= c n^{4/3}; the constant is not the point

    def search(self, p, seconds, rng):
        n, end = p["n"], now() + seconds
        best, bestF = None, -1
        for k in range(math.ceil(math.sqrt(n)), math.ceil(math.sqrt(n)) + 3):           # square sections
            for shape in ("square", "disc"):
                if shape == "square":
                    cand = self._grid(n, k)
                else:
                    c = k / 2
                    cells = sorted(((i - c) ** 2 + (j - c) ** 2, i, j) for i in range(k + 1) for j in range(k + 1))
                    cand = [[i, j] for _, i, j in cells[:n]]
                if len(cand) < n:
                    continue
                F = self.objective(p, cand)
                if F > bestF:
                    best, bestF = cand, F
        pts = [tuple(q) for q in best]
        while now() < end:                                                            # hill climb on single points
            i = rng.randrange(n)
            anchor = pts[rng.randrange(n)]
            q = (anchor[0] + rng.randint(-4, 4), anchor[1] + rng.randint(-4, 4))
            if q in pts or not (0 <= q[0] <= self.G and 0 <= q[1] <= self.G):
                continue
            trial = pts[:i] + [q] + pts[i + 1:]
            F = self.objective(p, trial)
            if F >= bestF:
                pts, bestF = trial, F
        return [list(q) for q in pts]


HEADROOM = {                                   # does the gap between best construction and best bound grow with the size?
    "open":    ["capset", "labs", "heilbronn", "kissing", "corners"],   # apfree_sub: search control, see "bounded"
    # 2026-09-14 (ladder result): apfree and unitdist are controls -- at A3 every strong system and the 10 s search return the same
    # textbook object (Behrend digit set; lattice section), the bound is trivial, and the ratio is 1 for all of them.
    "bounded": ["code", "code_pool", "no3inline", "ramsey", "apfree_sub", "apfree", "unitdist"],
    "tight":   ["sidon", "sidon_mod", "golomb", "golomb_forbid", "mono3ap", "vdw", "vdw_fixed", "costas", "costas_fixed", "hadamard"],
}
FAMILIES.update({f.name: f for f in (Kissing(), Corners(), UnitDistance())})


# ----------------------------------------------------------------------------
# Deformed families (2026-09-13): the same mathematics, parameters moved off the
# tabulated values so there is no published object to recall.
# ----------------------------------------------------------------------------
class SphericalCode(Kissing):
    """Integer vectors in Z^d with pairwise angle >= theta, cos(theta) = c/100 for a random c in [20, 48]
    (theta from about 61 to 78 degrees).  Tables exist only for special angles (60, 90); the layered-lattice
    constructions still transfer, so insight pays and recall does not."""
    name = "kissing_theta"
    title = "Spherical-Code"

    def upper(self, p):
        """Cap-packing bound: A(d, theta) <= 1 / mu(cap of angular radius theta/2), mu = normalised surface measure
        on S^{d-1}; mu(cap(phi)) = int_0^phi sin^{d-2} t dt / int_0^pi sin^{d-2} t dt (Simpson's rule, 20000 panels)."""
        d = p["d"]; theta = math.acos(p["cos100"] / 100.0); phi = theta / 2
        def integral(a, b, m=20000):
            h = (b - a) / m
            tot = math.sin(a) ** (d - 2) + math.sin(b) ** (d - 2)
            for k in range(1, m):
                tot += (4 if k % 2 else 2) * math.sin(a + k * h) ** (d - 2)
            return tot * h / 3
        mu = integral(0, phi) / integral(0, math.pi)
        return int(math.floor(1.0 / mu)) if mu > 0 else None

    def law(self, p, obj):
        d = p["d"]
        return {"name": "spherical_code_exponent", "value": (math.log2(obj) / d) if obj > 0 else None, "better": "higher",
                "lower": None, "upper": None,
                "note": f"log2(|code|)/d at cos(theta) = {p['cos100']}/100; A(d, theta) is open for every d >= 3 except special angles"}

    def params(self, rng):
        return {"d": rng.choice([6, 7, 8, 9, 10, 11, 12]), "cos100": rng.randint(20, 48)}

    def statement(self, p):
        d, c = p["d"], p["cos100"]
        theta = math.degrees(math.acos(c / 100))
        return (f"Find as many nonzero integer vectors in Z^{d} as possible (entries in [-{self.B}, {self.B}]) such that the "
                f"angle between any two of them is at least {theta:.2f} degrees, i.e. for every pair u != v: "
                f"u.v <= ({c}/100) |u| |v| exactly (a spherical code with cos(theta) = {c}/100). "
                f"Output: a JSON list of vectors, each a JSON list of {d} integers.")

    def _bad(self, dots, n2, nv, c):
        return (dots > 0) & (10000 * dots * dots > (c * c) * n2 * nv)

    def can_add(self, p, st, x):
        if not st["V"]:
            return True
        v = np.asarray(self._pool(p)[x], dtype=np.int64)
        A = np.asarray(st["V"], dtype=np.int64)
        return not bool(self._bad(A @ v, np.asarray(st["N2"], dtype=np.int64), int(v @ v), p["cos100"]).any())

    def verify(self, p, ans):
        d, B, c = p["d"], self.B, p["cos100"]
        if d > 16:
            return False, 0, "d > 16 is outside the range this verifier evaluates exactly (int64 angle test); not accepted"
        if not isinstance(ans, list) or not ans or any(not (isinstance(v, list) and len(v) == d) for v in ans):
            return False, 0, f"answer must be a non-empty list of integer vectors of length {d}"
        if any(not all(isinstance(x, int) and not isinstance(x, bool) and -B <= x <= B for x in v) for v in ans):
            return False, 0, f"entries must be integers in [-{B}, {B}]"
        A = np.asarray(ans, dtype=np.int64)
        n2 = (A * A).sum(axis=1)
        if (n2 == 0).any():
            return False, 0, "the zero vector is not allowed"
        G = A @ A.T
        iu = np.triu_indices(len(ans), 1)
        bad = self._bad(G[iu], n2[iu[0]], n2[iu[1]], c)
        if bad.any():
            i, j = iu[0][bad.argmax()], iu[1][bad.argmax()]
            return False, 0, f"vectors {i} and {j} are closer than the required angle"
        return True, len(ans), ""

    def naive(self, p):                        # the cross-polytope +-e_i: pairwise 90 or 180 degrees, valid for any theta <= 90
        d = p["d"]
        out = []
        for i in range(d):
            for si in (1, -1):
                v = [0] * d; v[i] = si; out.append(v)
        return out



class HeilbronnShape(Heilbronn):
    """Heilbronn's problem inside a random triangle T (integer vertices on the D x D grid, area >= D^2/4).
    The objective is the smallest triangle area divided by the area of T, so the scale-free law is unchanged;
    the tabulated square configurations no longer apply."""
    name = "heilbronn_shape"
    title = "Heilbronn-Triangle"          # a random triangle is an affine image of the standard one: the family is Heilbronn's
                                           # problem in a triangle on an integer grid, not a new continuous problem (review 2026-09-13)

    def params(self, rng):
        return {"n": rng.randint(8, 20), "T": self._triangle(rng)}

    def _triangle(self, rng):
        D = self.D
        while True:
            T = [[rng.randint(0, D), rng.randint(0, D)] for _ in range(3)]
            if abs(self._cross(T[0], T[1], T[2])) >= D * D // 2:      # twice the area >= D^2/2  <=>  area >= D^2/4
                return T

    @staticmethod
    def _cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def _inside(self, T, q):
        s = [self._cross(T[i], T[(i + 1) % 3], q) for i in range(3)]
        return all(x >= 0 for x in s) or all(x <= 0 for x in s)

    def statement(self, p):
        T = p["T"]
        return (f"Place {p['n']} distinct points inside (or on the boundary of) the triangle with vertices "
                f"{tuple(T[0])}, {tuple(T[1])}, {tuple(T[2])} on the {self.D} x {self.D} integer grid, so as to maximise "
                f"the smallest area of a triangle formed by any three of the points (reported as a fraction of the area "
                f"of the container triangle). Output: a JSON list of [x, y] integer pairs.")

    def objective(self, p, pts):
        best = None
        for a, b, c in combinations(pts, 3):
            v = abs(self._cross(a, b, c))
            if best is None or v < best:
                best = v
        return best / abs(self._cross(*p["T"]))

    def verify(self, p, ans):
        n, D = p["n"], self.D
        if not isinstance(ans, list) or len(ans) != n or any(not (isinstance(q, list) and len(q) == 2) for q in ans):
            return False, 0, f"answer must be a list of {n} [x, y] pairs"
        pts = [tuple(q) for q in ans]
        if any(not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= D for c in q) for q in pts) or len(set(pts)) != len(pts):
            return False, 0, "coordinates must be distinct integers in [0, D]"
        for q in pts:
            if not self._inside(p["T"], q):
                return False, 0, f"point {list(q)} lies outside the triangle"
        return True, self.objective(p, pts), ""

    def _random(self, p, rng):
        T, D = p["T"], self.D
        pts = set()
        while len(pts) < p["n"]:
            q = (rng.randint(0, D), rng.randint(0, D))
            if self._inside(T, q):
                pts.add(q)
        return list(pts)

    def search(self, p, seconds, rng):
        end, D, T = now() + seconds, self.D, p["T"]
        pts = [tuple(q) for q in self.naive(p)]
        v = self.objective(p, pts)
        radius = D // 4
        while now() < end:
            i = rng.randrange(len(pts))
            q = (min(D, max(0, pts[i][0] + rng.randint(-radius, radius))), min(D, max(0, pts[i][1] + rng.randint(-radius, radius))))
            if not self._inside(T, q):
                continue
            cand = pts[:]; cand[i] = q
            if len(set(cand)) < len(cand):
                continue
            v2 = self.objective(p, cand)
            if v2 >= v:
                pts, v = cand, v2
            elif rng.random() < 0.02:
                radius = max(10, radius // 2) if rng.random() < 0.5 else min(D // 4, radius * 2)
        return [list(q) for q in pts]


FAMILIES.update({f.name: f for f in (SphericalCode(), HeilbronnShape())})
HEADROOM["open"] += ["kissing_theta", "heilbronn_shape"]


# ----------------------------------------------------------------------------
# Four families from other disciplines (2026-09-13): algorithms (sorting networks),
# algebra (matrix-multiplication schemes = tensor rank), Boolean functions
# (nonlinearity), graph theory (degree-diameter).  Same selection rule as the
# rest of the headline set: the best construction and the best proven bound
# diverge with the size, verification is cheap, the object is listable.
# Table values quoted from memory of the literature: re-check before publication.
# ----------------------------------------------------------------------------
class SortingNetwork:
    """A comparator network on n wires that sorts every input; minimise the number of comparators."""
    name = "sortnet"
    title = "Sorting-Network"
    sense = "min"
    KNOWN_BEST = {2: 1, 3: 3, 4: 5, 5: 9, 6: 12, 7: 16, 8: 19, 9: 25, 10: 29, 11: 35, 12: 39, 13: 45, 14: 51, 15: 56,
                  16: 60, 17: 71, 18: 77, 19: 85, 20: 91, 21: 99, 22: 106, 23: 114, 24: 120}   # optimal to n = 12; n=21-23 per bertdobbelaere.github.io (checked 2026-09-13)
    KNOWN_LOWER = {13: 44, 14: 48, 15: 53, 16: 57, 17: 63, 18: 68, 19: 73, 20: 78, 21: 84, 22: 89, 23: 95, 24: 100}   # proven size lower bounds (Harder; OEIS A003075 table); corrected 2026-09-13

    def law(self, p, obj):
        n = p["n"]
        base = n * math.log2(n)
        best = self.KNOWN_BEST.get(n, len(self.naive(p)))
        return {"name": "sortnet_c", "value": obj / base, "better": "lower",
                "lower": math.log2(math.factorial(n)) / base, "upper": best / base,
                "note": "comparators / (n log2 n); information-theoretic bound below, best known network above; "
                        "optimal sizes proven only to n = 12"}

    def params(self, rng):
        return {"n": rng.randint(9, 16)}

    def statement(self, p):
        n = p["n"]
        return (f"Find a sorting network on {n} wires (numbered 0..{n-1}) with as few comparators as possible. A "
                f"comparator [i, j] with i < j compares the values on wires i and j and puts the smaller on wire i and "
                f"the larger on wire j; comparators are applied in the listed order, and the network must sort every "
                f"input into increasing order along the wires 0..{n-1}. Output: the comparators as a JSON list of "
                f"[i, j] pairs, in order. The verifier accepts at most {4 * n * n} comparators.")

    @staticmethod
    def _wires(n):
        # 0-1 principle: wire k holds a 2^n-bit integer whose bit t is the value of wire k on input t
        N = 1 << n
        w = []
        for k in range(n):
            unit = ((1 << (1 << k)) - 1) << (1 << k)          # 2^k zeros then 2^k ones
            v, L = unit, 1 << (k + 1)
            while L < N:
                v |= v << L
                L <<= 1
            w.append(v)
        return w

    def _sorts(self, n, comps):
        w = self._wires(n)
        for i, j in comps:
            a, b = w[i], w[j]
            w[i], w[j] = a & b, a | b
        return all((w[k] & ~w[k + 1]) == 0 for k in range(n - 1))

    def verify(self, p, ans):
        n = p["n"]
        if not isinstance(ans, list) or any(not (isinstance(c, list) and len(c) == 2) for c in ans):
            return False, 0, "answer must be a list of [i, j] comparator pairs"
        if any(not (isinstance(i, int) and isinstance(j, int) and not isinstance(i, bool) and not isinstance(j, bool) and 0 <= i < j < n) for i, j in ans):
            return False, 0, f"each comparator must be [i, j] with 0 <= i < j < {n}"
        if len(ans) > 4 * n * n:
            return False, 0, f"too many comparators (limit 4 n^2 = {4 * n * n})"
        if not self._sorts(n, [tuple(c) for c in ans]):
            return False, 0, "the network does not sort every input"
        return True, len(ans), ""

    def naive(self, p):                                    # Batcher's merge exchange (Knuth 5.2.2, Algorithm M)
        n = p["n"]
        comps = []
        t = max(1, math.ceil(math.log2(n)))
        pp = 1 << (t - 1)
        while pp > 0:
            q, r, d = 1 << (t - 1), 0, pp
            while True:
                for i in range(n - d):
                    if (i & pp) == r:
                        comps.append([i, i + d])
                if q == pp:
                    break
                d, q, r = q - pp, q >> 1, pp
            pp >>= 1
        return comps

    def objective(self, p, ans):
        return len(ans)

    def upper(self, p):                                    # a LOWER bound on the size (sense = min)
        n = p["n"]
        return self.KNOWN_LOWER.get(n, self.KNOWN_BEST.get(n, math.ceil(math.log2(math.factorial(n)))))

    def search(self, p, seconds, rng):
        """Prune redundant comparators from the naive network, in random orders, within the budget."""
        n, end = p["n"], now() + seconds
        best = [tuple(c) for c in self.naive(p)]
        while now() < end:
            cur = best[:]
            order = list(range(len(cur)))
            rng.shuffle(order)
            removed = set()
            for idx in order:
                if now() >= end:
                    break
                trial = [c for t, c in enumerate(cur) if t != idx and t not in removed]
                if self._sorts(n, trial):
                    removed.add(idx)
            cur = [c for t, c in enumerate(cur) if t not in removed]
            if len(cur) < len(best):
                best = cur
        return [list(c) for c in best]


class MatMul:
    """Bilinear algorithm for (n x m)(m x p) matrix multiplication with r products; minimise r (the tensor rank)."""
    name = "matmul"
    title = "Matrix-Multiplication"
    sense = "min"
    B = 4                                                   # coefficient bound
    # (4,4,4): 49 = Strassen^2 over Z; the rank-48 schemes (AlphaEvolve 2025 over C, Dumas-Pernet-Sedoglavic 2025 over Q with
    # denominators 2/4/8) are not expressible in this integer format, so 48 is not the frontier for this instance format.
    KNOWN_BEST = {(2, 2, 2): 7, (2, 2, 3): 11, (2, 2, 4): 14, (2, 3, 3): 15, (2, 3, 4): 20, (2, 4, 4): 26, (3, 3, 3): 23,
                  (3, 3, 4): 29, (3, 3, 5): 36, (3, 4, 4): 38, (3, 4, 5): 47, (4, 4, 4): 49, (3, 5, 5): 58, (4, 4, 5): 61,   # (4,4,4)=48: AlphaEvolve 2025, valid over Q (arXiv:2506.13242); checked 2026-09-13
                  (4, 5, 5): 76, (5, 5, 5): 93}
    KNOWN_LOWER = {(2, 2, 2): 7, (2, 2, 3): 11, (2, 3, 3): 15, (3, 3, 3): 19}
    _memo = {}

    def law(self, p, obj):
        n, m, q = p["n"], p["m"], p["p"]
        return {"name": "matmul_exponent", "value": math.log(obj) / math.log((n * m * q) ** (1 / 3)), "better": "lower",
                "lower": 2.0, "upper": 3.0,
                "note": "log r / log (nmp)^{1/3}; 2 <= omega <= 2.37 asymptotically; rank(3x3) in [19, 23], rank(4x4) <= 49 (47 mod 2)"}

    def params(self, rng):
        return dict(zip(("n", "m", "p"), rng.choice([(2, 2, 3), (2, 3, 3), (3, 3, 3), (3, 3, 4), (3, 4, 4), (4, 4, 4)])))

    def statement(self, p):
        n, m, q, B = p["n"], p["m"], p["p"], self.B
        return (f"Find a bilinear algorithm that multiplies an {n} x {m} matrix A by an {m} x {q} matrix B using as few "
                f"products as possible. Index A row-major as A[0..{n*m-1}] (entry (i, j) at i*{m} + j), B as B[0..{m*q-1}] "
                f"(entry (j, l) at j*{q} + l) and C = A B as C[0..{n*q-1}] (entry (i, l) at i*{q} + l). The algorithm "
                f"is a list of r products; product k is [u_k, v_k, w_k] with integer vectors u_k (length {n*m}), v_k "
                f"(length {m*q}), w_k (length {n*q}), entries in [-{B}, {B}], meaning M_k = (sum_a u_k[a] A[a]) * "
                f"(sum_b v_k[b] B[b]) and C[c] = sum_k w_k[c] M_k must hold identically for all A, B. Output: a JSON "
                f"list of r triples [u_k, v_k, w_k]. The verifier accepts at most {4 * n * m * q} products.")

    def _target(self, n, m, q):
        T = np.zeros((n * m, m * q, n * q), dtype=np.int64)
        for i in range(n):
            for j in range(m):
                for l in range(q):
                    T[i * m + j, j * q + l, i * q + l] = 1
        return T

    def verify(self, p, ans):
        n, m, q, B = p["n"], p["m"], p["p"], self.B
        if not isinstance(ans, list) or not ans:
            return False, 0, "answer must be a non-empty list of [u, v, w] triples"
        for k, t in enumerate(ans):
            if not (isinstance(t, list) and len(t) == 3 and all(isinstance(x, list) for x in t)):
                return False, 0, f"product {k} must be a triple of integer lists"
            if (len(t[0]), len(t[1]), len(t[2])) != (n * m, m * q, n * q):
                return False, 0, f"product {k}: vector lengths must be {n*m}, {m*q}, {n*q}"
            for vec in t:
                if any(not isinstance(c, int) or isinstance(c, bool) or abs(c) > B for c in vec):
                    return False, 0, f"product {k}: entries must be integers in [-{B}, {B}]"
        if len(ans) > 4 * n * m * q:
            return False, 0, f"too many products (limit {4 * n * m * q})"
        U = np.array([t[0] for t in ans], dtype=np.int64)
        V = np.array([t[1] for t in ans], dtype=np.int64)
        W = np.array([t[2] for t in ans], dtype=np.int64)
        T = np.einsum("ka,kb,kc->abc", U, V, W)
        if not np.array_equal(T, self._target(n, m, q)):
            return False, 0, "the products do not compute A B for all A, B"
        return True, len(ans), ""

    def objective(self, p, ans):
        return len(ans)

    def naive(self, p):
        n, m, q = p["n"], p["m"], p["p"]
        return self._scheme(n, m, q, strassen=False)

    def upper(self, p):                                    # a LOWER bound on the rank (sense = min)
        n, m, q = p["n"], p["m"], p["p"]
        return self.KNOWN_LOWER.get((n, m, q), max(n * m, m * q, n * q))

    # -- constructive reference: Strassen on even blocks, splits on odd dimensions, memoised --
    def _scheme(self, n, m, q, strassen=True):
        key = (n, m, q, strassen)
        if key in self._memo:
            return self._memo[key]
        def e(size, idx):
            v = [0] * size; v[idx] = 1; return v
        if min(n, m, q) == 1 or not strassen:
            out = [[e(n * m, i * m + j), e(m * q, j * q + l), e(n * q, i * q + l)]
                   for i in range(n) for j in range(m) for l in range(q)]
            self._memo[key] = out
            return out
        cands = []
        if n % 2 == 0 and m % 2 == 0 and q % 2 == 0:
            cands.append(self._strassen(n, m, q))
        for dim in "nmp":
            size = {"n": n, "m": m, "p": q}[dim]
            if size >= 2:
                cands.append(self._split(n, m, q, dim, size // 2))
        best = min(cands, key=len)
        self._memo[key] = best
        return best

    def _embed(self, sub, n, m, q, rows, cols_m, cols_p):
        """Lift a sub-scheme for (len(rows) x len(cols_m)) (len(cols_m) x len(cols_p)) into the full index spaces."""
        out = []
        n2, m2, q2 = len(rows), len(cols_m), len(cols_p)
        for u, v, w in sub:
            U = [0] * (n * m); V = [0] * (m * q); W = [0] * (n * q)
            for i in range(n2):
                for j in range(m2):
                    U[rows[i] * m + cols_m[j]] += u[i * m2 + j]
            for j in range(m2):
                for l in range(q2):
                    V[cols_m[j] * q + cols_p[l]] += v[j * q2 + l]
            for i in range(n2):
                for l in range(q2):
                    W[rows[i] * q + cols_p[l]] += w[i * q2 + l]
            out.append([U, V, W])
        return out

    def _split(self, n, m, q, dim, h):
        if dim == "n":
            a = self._embed(self._scheme(h, m, q), n, m, q, list(range(h)), list(range(m)), list(range(q)))
            b = self._embed(self._scheme(n - h, m, q), n, m, q, list(range(h, n)), list(range(m)), list(range(q)))
        elif dim == "m":
            a = self._embed(self._scheme(n, h, q), n, m, q, list(range(n)), list(range(h)), list(range(q)))
            b = self._embed(self._scheme(n, m - h, q), n, m, q, list(range(n)), list(range(h, m)), list(range(q)))
        else:
            a = self._embed(self._scheme(n, m, h), n, m, q, list(range(n)), list(range(m)), list(range(h)))
            b = self._embed(self._scheme(n, m, q - h), n, m, q, list(range(n)), list(range(m)), list(range(h, q)))
        return a + b

    def _strassen(self, n, m, q):
        """Strassen's seven block products with a sub-scheme for the half-size blocks."""
        h1, h2, h3 = n // 2, m // 2, q // 2
        sub = self._scheme(h1, h2, h3)
        # Strassen: block coefficients for A (2x2 of (I,J)), B (2x2 of (J,L)), C (2x2 of (I,L))
        A_ = [{(0, 0): 1, (1, 1): 1}, {(1, 0): 1, (1, 1): 1}, {(0, 0): 1}, {(1, 1): 1}, {(0, 0): 1, (0, 1): 1}, {(1, 0): 1, (0, 0): -1}, {(0, 1): 1, (1, 1): -1}]
        B_ = [{(0, 0): 1, (1, 1): 1}, {(0, 0): 1}, {(0, 1): 1, (1, 1): -1}, {(1, 0): 1, (0, 0): -1}, {(1, 1): 1}, {(0, 0): 1, (0, 1): 1}, {(1, 0): 1, (1, 1): 1}]
        C_ = [{(0, 0): 1, (1, 1): 1}, {(1, 0): 1, (1, 1): -1}, {(0, 1): 1, (1, 1): 1}, {(0, 0): 1, (1, 0): 1}, {(0, 0): -1, (0, 1): 1}, {(1, 1): 1}, {(0, 0): 1}]
        out = []
        for t in range(7):
            for u, v, w in sub:
                U = [0] * (n * m); V = [0] * (m * q); W = [0] * (n * q)
                for (I, J), c in A_[t].items():
                    for i in range(h1):
                        for j in range(h2):
                            U[(I * h1 + i) * m + (J * h2 + j)] += c * u[i * h2 + j]
                for (J, L), c in B_[t].items():
                    for j in range(h2):
                        for l in range(h3):
                            V[(J * h2 + j) * q + (L * h3 + l)] += c * v[j * h3 + l]
                for (I, L), c in C_[t].items():
                    for i in range(h1):
                        for l in range(h3):
                            W[(I * h1 + i) * q + (L * h3 + l)] += c * w[i * h3 + l]
                out.append([U, V, W])
        return out

    def search(self, p, seconds, rng):
        return self._scheme(p["n"], p["m"], p["p"])


class BooleanNonlinearity:
    """Boolean function on n (odd) variables with the largest nonlinearity."""
    name = "boolnl"
    title = "Boolean-Nonlinearity"
    sense = "max"
    KNOWN_BEST = {7: 56, 9: 242, 11: 996, 13: 4040, 15: 16276}     # 7 optimal; 9 Kavut-Maitra; 15 Patterson-Wiedemann; others re-check

    def law(self, p, obj):
        n = p["n"]
        return {"name": "nl_deficit", "value": (2 ** (n - 1) - obj) / 2 ** ((n - 1) / 2), "better": "lower",
                "lower": 2 ** -0.5, "upper": 1.0,
                "note": "(2^(n-1) - nl) / 2^((n-1)/2): 1.0 for quadratic (bent-like) functions, 0.707 is the covering-radius bound; "
                        "open for every odd n >= 9"}

    def params(self, rng):
        return {"n": rng.choice([9, 11])}

    def statement(self, p):
        n = p["n"]
        return (f"Find a Boolean function f: {{0,1}}^{n} -> {{0,1}} with the largest possible nonlinearity, i.e. the "
                f"largest minimum Hamming distance from f to the set of all affine functions a.x + b (a in {{0,1}}^{n}, "
                f"b in {{0,1}}). Output f in algebraic normal form: a JSON list of monomials, each monomial a list of "
                f"distinct variable indices in 0..{n-1} (the empty list is the constant 1), f being the XOR of the "
                f"listed monomials; e.g. [[0,1],[2,3],[4]] means x0 x1 + x2 x3 + x4. (A truth-table string of "
                f"{2 ** n} characters 0/1, character t being f at the input whose bit i is bit i of t, is also accepted.)")

    def objective(self, p, tt):
        n = p["n"]
        h = np.array([1 - 2 * (c == "1") for c in tt], dtype=np.int64)
        L = 1
        while L < len(h):
            h = h.reshape(-1, 2, L)
            h = np.concatenate([h[:, 0, :] + h[:, 1, :], h[:, 0, :] - h[:, 1, :]], axis=1).reshape(-1)
            L <<= 1
        return (2 ** n - int(np.abs(h).max())) // 2

    def _anf_to_tt(self, n, monomials):
        t = np.arange(2 ** n)
        f = np.zeros(2 ** n, dtype=np.int64)
        for mono in monomials:
            term = np.ones(2 ** n, dtype=np.int64)
            for i in mono:
                term &= (t >> i) & 1
            f ^= term
        return "".join("1" if b else "0" for b in f)

    def verify(self, p, ans):
        n = p["n"]
        if isinstance(ans, list):
            if len(ans) > 2 ** n or any(not (isinstance(m, list) and all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < n for i in m) and len(set(m)) == len(m)) for m in ans):
                return False, 0, f"ANF must be a list of monomials, each a list of distinct variable indices in 0..{n-1}"
            tt = self._anf_to_tt(n, ans)
        elif isinstance(ans, str):
            tt = "".join(ans.split())
            if len(tt) != 2 ** n or set(tt) - {"0", "1"}:
                return False, 0, f"a truth-table answer must be a 0/1 string of length {2 ** n} (got {len(tt)}); the ANF form is easier"
        else:
            return False, 0, "answer must be an ANF (list of monomials) or a 0/1 truth-table string"
        return True, self.objective(p, tt), ""

    def naive(self, p):                                    # x1x2 + x3x4 + ... : nonlinearity 2^(n-1) - 2^((n-1)/2)
        n = p["n"]
        out = []
        for t in range(2 ** n):
            f = 0
            for i in range(0, n - 1, 2):
                f ^= ((t >> i) & 1) & ((t >> (i + 1)) & 1)
            out.append("1" if f else "0")
        return "".join(out)

    def upper(self, p):
        n = p["n"]
        return int(math.floor(2 ** (n - 1) - 2 ** (n / 2 - 1)))

    def search(self, p, seconds, rng):
        n, end = p["n"], now() + seconds
        best = list(self.naive(p)); bestv = self.objective(p, best)
        cur, curv = best[:], bestv
        N = 2 ** n
        while now() < end:
            i = rng.randrange(N)
            cur[i] = "1" if cur[i] == "0" else "0"
            v = self.objective(p, cur)
            if v >= curv:
                curv = v
                if v > bestv:
                    best, bestv = cur[:], v
            else:
                cur[i] = "1" if cur[i] == "0" else "0"
        return "".join(best)


class DegreeDiameter:
    """Largest graph with maximum degree d and diameter at most k."""
    name = "degdiam"
    title = "Degree-Diameter"
    sense = "max"
    KNOWN_BEST = {(3, 2): 10, (3, 3): 20, (3, 4): 38, (3, 5): 70, (3, 6): 132, (3, 7): 196, (4, 2): 15, (4, 3): 41, (4, 4): 104, (4, 6): 745, (4, 7): 1320, (4, 8): 3243, (3, 8): 360, (3, 9): 600, (3, 10): 1250,
                  (11, 2): 104, (12, 2): 133, (13, 2): 162, (14, 2): 183, (15, 2): 188, (16, 2): 200,   # Comellas' table, 2026-09-12 update (table values)
                  (4, 5): 364, (5, 2): 24, (5, 3): 72, (5, 4): 212, (6, 2): 32, (6, 3): 111, (7, 2): 50, (7, 3): 168,
                  (8, 2): 57, (9, 2): 74, (10, 2): 91}          # Moore graphs at (3,2) and (7,2); the rest are lower bounds

    @staticmethod
    def moore(d, k):
        return 1 + d * sum((d - 1) ** i for i in range(k))

    def law(self, p, obj):
        d, k = p["d"], p["k"]
        return {"name": "degdiam_ratio", "value": obj / self.moore(d, k), "better": "higher", "lower": None, "upper": 1.0,
                "note": "|V| / Moore bound; 1 only for the Moore graphs (K_{d+1}, C_5, Petersen, Hoffman-Singleton); "
                        "the ratio of the best known graphs falls with k"}

    def params(self, rng):
        return dict(zip(("d", "k"), rng.choice([(3, 3), (4, 2), (5, 2), (4, 3), (3, 4), (5, 3)])))

    def statement(self, p):
        d, k = p["d"], p["k"]
        return (f"Find a simple undirected graph with maximum degree at most {d} and diameter at most {k} on as many "
                f"vertices as possible. Vertices are 0..V-1 for the V vertices you use; every vertex must appear in at "
                f"least one edge and the graph must be connected. Output: a JSON list of [u, v] edges with u < v, no "
                f"repeats.")

    def _diameter_ok(self, V, adj, k):
        A = np.zeros((V, V), dtype=np.float32)
        for u, nb in enumerate(adj):
            for v in nb:
                A[u, v] = 1.0
        R = np.minimum(A + np.eye(V, dtype=np.float32), 1.0)
        P = R
        for _ in range(k - 1):
            P = np.minimum(P @ R, 1.0)
        return bool((P > 0).all())

    def verify(self, p, ans):
        d, k = p["d"], p["k"]
        if not isinstance(ans, list) or not ans or any(not (isinstance(e, list) and len(e) == 2) for e in ans):
            return False, 0, "answer must be a non-empty list of [u, v] edges"
        if any(not (isinstance(u, int) and isinstance(v, int) and 0 <= u < v) for u, v in ans):
            return False, 0, "edges must be [u, v] with 0 <= u < v"
        edges = {tuple(e) for e in ans}
        if len(edges) != len(ans):
            return False, 0, "repeated edge"
        V = max(v for _, v in edges) + 1
        if V > 4000:
            return False, 0, "too many vertices"
        adj = [[] for _ in range(V)]
        for u, v in edges:
            adj[u].append(v); adj[v].append(u)
        if any(len(a) > d for a in adj):
            return False, 0, f"a vertex has degree above {d}"
        if any(len(a) == 0 for a in adj):
            return False, 0, "every vertex 0..V-1 must have an edge"
        if not self._diameter_ok(V, adj, k):
            return False, 0, f"the diameter exceeds {k}"
        return True, V, ""

    def objective(self, p, ans):
        return max(v for _, v in ans) + 1

    def naive(self, p):                                    # the Moore tree of depth floor(k/2): diameter 2 floor(k/2) <= k
        d, k = p["d"], p["k"]
        depth = k // 2
        edges, nxt = [], 1
        frontier = [0]
        for lvl in range(depth):
            new = []
            for u in frontier:
                for _ in range(d if lvl == 0 else d - 1):
                    edges.append([u, nxt]); new.append(nxt); nxt += 1
            frontier = new
        return edges

    def upper(self, p):
        return self.moore(p["d"], p["k"])

    def _circulant(self, V, S):
        edges = set()
        for u in range(V):
            for s in S:
                v = (u + s) % V
                edges.add((min(u, v), max(u, v)))
        return [list(e) for e in sorted(edges)]

    def search(self, p, seconds, rng):
        """Random circulant graphs C(V, S), largest V with diameter <= k (vertex-transitive: one BFS suffices)."""
        d, k, end = p["d"], p["k"], now() + seconds
        best = self.naive(p); bestV = self.objective(p, best)
        V = min(self.moore(d, k), self.KNOWN_BEST.get((d, k), self.moore(d, k)) + 20)
        while V > bestV and now() < end:
            for _ in range(40):
                if now() >= end:
                    break
                if d % 2 == 1 and V % 2 == 1:
                    break
                half = d // 2
                offs = rng.sample(range(1, (V + 1) // 2), half) if half else []
                S = offs + ([V // 2] if d % 2 == 1 else [])
                # BFS from 0
                dist = {0: 0}; frontier = [0]
                for step in range(k):
                    nxt = []
                    for u in frontier:
                        for s in S:
                            for v in ((u + s) % V, (u - s) % V):
                                if v not in dist:
                                    dist[v] = step + 1; nxt.append(v)
                    frontier = nxt
                if len(dist) == V:
                    edges = self._circulant(V, S)
                    ok, obj, _ = self.verify(p, edges)
                    if ok and obj > bestV:
                        best, bestV = edges, obj
                    break
            V -= 1
        return best


FAMILIES.update({f.name: f for f in (SortingNetwork(), MatMul(), BooleanNonlinearity(), DegreeDiameter())})
HEADROOM["open"] += ["matmul", "degdiam"]
HEADROOM["bounded"] += ["sortnet"]       # zero-to-bound gap at n = 20-22 is ln(97/78) = 0.22 < ln 1.4: fails the A3 size rule (review 2026-09-13)
HEADROOM["tight"] += ["boolnl"]          # nl <= 2^(n-1) - 2^(n/2-1) and the best constructions sit within 0.3% of it: the gap closes with n


def known_best(fam, p):
    """Best construction in the literature for this instance, or None (values from memory: re-check before publication)."""
    n = fam.name
    if n == "capset":
        # d=8: FunSearch (Nature 2023). d=9/10: doubled Edel projective caps, 1082 / 2432; re-verified 2026-09-13.
        # d=11: Karapetyan-Karapetyan, CSIT 2023, Corollary 2, 5504 points; reconstructed and double-checked
        # 2026-09-16, witness in frontier_audits/2026-09-16/capset_d11_5504.json.
        # d=12: the 6464-cap in PG(11,3) (Edel's table) doubled to 12928, re-verified 2026-09-14.
        return {6: 112, 7: 236, 8: 512, 9: 1082, 10: 2432, 11: 5504, 12: 12928}.get(p["d"])
    if n == "kissing":
        return fam.KNOWN_LOWER.get(p["d"])
    if n == "sortnet":
        return fam.KNOWN_BEST.get(p["n"])
    if n == "matmul":
        return fam.KNOWN_BEST.get((p["n"], p["m"], p["p"]))
    if n == "boolnl":
        return fam.KNOWN_BEST.get(p["n"])
    if n == "degdiam":
        return fam.KNOWN_BEST.get((p["d"], p["k"]))
    if n == "mols":
        return fam.KNOWN_BEST.get(p["n"])
    if n == "apfree_q":
        return fam.KNOWN.get((p["q"], p["n"]))
    if n == "schur":
        return fam.KNOWN_BEST.get(p["k"])
    if n == "covering":
        e = fam.entry(p)
        return e[0] if e else None
    return None


def conjectured(fam, p):
    """A conjectured limit used as the 1.0 end where neither a proven bound nor a table exists."""
    if fam.name == "labs":
        return 12.32                                                 # Golay's conjectured asymptotic merit factor
    return None


def trivial_bound(fam, p):
    """A proven but loose bound used as the last-resort anchor (kind 'trivial'): it keeps the score ordinal and
    additive at the price of resolution.  apfree: |S| <= n.  corners: |S| <= n^2.  heilbronn / heilbronn_shape:
    a triangulation of the n points has at least n - 2 triangles inside a region of area 1, so the smallest has
    area <= 1/(n - 2).  unitdist: u(n) <= 1.94 n^{4/3} (Agoston-Palvolgyi 2022; constant to re-check)."""
    n = fam.name
    if n in ("apfree", "lineq"):
        return p["n"]
    if n == "corners":
        return p["n"] * p["n"]
    if n in ("heilbronn", "heilbronn_shape"):
        return 1.0 / (p["n"] - 2) if p["n"] > 2 else None
    if n == "unitdist":
        return 1.94 * p["n"] ** (4 / 3)
    return None


def anchor(fam, p):
    """The 1.0 end of the closed-gap score: (value, kind) with kind in {'bound', 'literature', 'conjecture',
    'trivial'}, or (None, None).  For sense='min' families upper() returns a proven LOWER bound on the objective,
    which is the right anchor."""
    b = fam.upper(p)
    if b is not None:
        return b, "bound"
    v = known_best(fam, p)
    if v is not None:
        return v, "literature"
    v = conjectured(fam, p)
    if v is not None:
        return v, "conjecture"
    v = trivial_bound(fam, p)
    if v is not None:
        return v, "trivial"
    return None, None


SEARCH_TYPE = ["heilbronn", "heilbronn_shape", "labs", "degdiam", "matmul"]     # no closed-form textbook; compute helps
_ZERO_CACHE = {}
_CONSTRUCTION_REFERENCE_TABLE = None


def construction_reference(fam, p):
    """A separately verified offline construction; frozen loads select their own table."""
    global _CONSTRUCTION_REFERENCE_TABLE
    if _CONSTRUCTION_REFERENCE_TABLE is None:
        from pathlib import Path
        path = Path(__file__).with_name("construction_references.json")
        _CONSTRUCTION_REFERENCE_TABLE = json.loads(path.read_text())["entries"] if path.exists() else {}
    return _CONSTRUCTION_REFERENCE_TABLE.get(f"{fam.name}|{json.dumps(p, sort_keys=True)}")


def textbook_zero(fam, p, ref_search=None):
    """The construction floor of the closed-gap score, including verified offline references.
    Stronger than naive() where naive() is only a placeholder (2026-09-13):
      labs        Legendre sequence at its best rotation (merit factor ~ 6 asymptotically), not the unrotated one
      heilbronn   Erdos's parabola (i, i^2 mod p), scaled to the grid; heilbronn_shape: the same inside the
                  half-area parallelogram of the triangle
      capset      the best product of the tabulated optimal small caps (2, 4, 9, 20, 45, 112, 236, 512), as a value
      kissing     the laminated-lattice values (= the literature): a recall family, scored only above the literature
      degdiam, matmul  the reference search itself (no textbook construction exists beyond the naive one)
    Returns (value, label); 'T' is textbook, 'C' offline construction, 'S' search."""
    key = (fam.name, json.dumps(p, sort_keys=True), ref_search if fam.name in ("degdiam", "matmul") else None)
    if key in _ZERO_CACHE:
        return _ZERO_CACHE[key]
    n = fam.name
    out = None
    if n == "labs":
        N = p["N"]; q = N
        while not all(q % i for i in range(2, int(q ** 0.5) + 1)):
            q -= 1
        qr = {(i * i) % q for i in range(1, q)}
        base = np.array([1] + [1 if i in qr else -1 for i in range(1, q)], dtype=np.int64)
        best = 0.0
        for rot in range(q):
            sq = np.roll(base, rot)
            sq = np.concatenate([sq, np.ones(N - q, dtype=np.int64)]) if N > q else sq
            c = np.correlate(sq, sq, "full")[N:]
            E = int((c * c).sum())
            best = max(best, N * N / (2 * E) if E else 0.0)
        out = (best, "T")
    elif n in ("heilbronn", "heilbronn_shape"):
        m = p["n"]; pr = m
        while not all(pr % i for i in range(2, int(pr ** 0.5) + 1)):
            pr += 1
        D = fam.D if hasattr(fam, "D") else 10000
        if n == "heilbronn":
            pts = [[int(i * D / pr), int(((i * i) % pr) * D / pr)] for i in range(m)]
        else:                                                           # affine image in the half-area parallelogram
            (ax, ay), (bx, by), (cx, cy) = [tuple(v) for v in p["T"]]
            pts = []
            for i in range(m):
                u, v = i / pr, ((i * i) % pr) / pr
                pts.append([int(round(ax + u * (bx - ax) / 2 + v * (cx - ax) / 2)), int(round(ay + u * (by - ay) / 2 + v * (cy - ay) / 2))])
        ok, val, _ = fam.verify(p, pts)
        out = (val, "T") if ok and val > 0 else None
    elif n == "capset":
        best_small = {1: 2, 2: 4, 3: 9, 4: 20, 5: 45, 6: 112, 7: 236, 8: 512}
        d = p["d"]; dp = [1] + [0] * d
        for i in range(1, d + 1):
            dp[i] = max(dp[i - j] * best_small[j] for j in range(1, min(8, i) + 1))
        out = (dp[d], "T")
    elif n == "kissing":
        v = fam.KNOWN_LOWER.get(p["d"])
        out = (v, "T") if v else None
    elif n == "mols":                              # the classical pairs/sets (Parker 1959, Johnson-Dulmage-Mendelsohn 1961,
        v = fam.KNOWN_BEST.get(p["n"])             # difference matrices) are printed in textbooks: recall earns nothing
        out = (v, "T") if v else None
    elif n == "apfree_q":                          # product of the exact one-dimensional values r_3(Z_q): 2 for q=5, 3 for q=7
        r1 = {5: 2, 7: 3, 11: 4, 13: 4}.get(p["q"])
        out = (r1 ** p["n"], "T") if r1 else None
    elif n == "kakeya":                            # textbook (Saraf-Sudan type): K = {(x, t): x_i + t^2 is a square or 0
        q, nn = p["q"], p["n"]                     # for all i} covers every direction (d, 1); the hyperplane t = 0 covers
        from itertools import product              # the directions (d, 0).  Size q ((q+1)/2)^{n-1} + q^{n-1} ~ q^n / 2^{n-1}.
        sq0 = {(t * t) % q for t in range(q)}
        def K(m):                                  # recursive: the (d, 0) directions are covered by K_{m-1} x {0}
            if m == 1:
                return [[t] for t in range(q)]
            pts = [list(x) + [t] for t in range(q) for x in product(range(q), repeat=m - 1) if all(((xi + t * t) % q) in sq0 for xi in x)]
            seen = {tuple(v) for v in pts}
            for v in K(m - 1):
                w = v + [0]
                if tuple(w) not in seen:
                    pts.append(w); seen.add(tuple(w))
            return pts
        pts = K(nn)
        ok, val, _ = fam.verify(p, pts)
        out = (val, "T") if ok else None
    elif n in ("degdiam", "matmul") and ref_search is not None:
        out = (ref_search, "S")
    construction = construction_reference(fam, p)
    if construction is not None:
        value = construction["objective"]
        if out is None or (value > out[0] if fam.sense == "max" else value < out[0]):
            out = (value, "C")
    _ZERO_CACHE[key] = out
    return out


def human_frontier(fam, p, naive, ref_search=None):
    """The best value humans have reached on this instance: max(textbook zero, literature); None if unknown."""
    z = textbook_zero(fam, p, ref_search); zero = z[0] if z else naive
    lit = known_best(fam, p)
    if lit is None:
        return zero, False
    better = (lit > zero) if fam.sense == "max" else (lit < zero)
    return (lit if better else zero), True


def discovery_gap(fam, p, naive, obj, feasible, ref_search=None):
    """Fraction of the log-gap between the HUMAN FRONTIER and the proven bound that an answer closes: 0 for anything
    at or below what humans have published, > 0 only for a new record.  This is the ASI axis; it is 0 for every
    system today.  None when there is no proven-bound anchor (literature anchors would make it degenerate)."""
    a, kind = anchor(fam, p)
    if a is None or kind != "bound":
        return None
    hf, has_lit = human_frontier(fam, p, naive, ref_search)
    if not has_lit:                                                # no published value to beat: not a discovery instance
        return None
    if hf is None or hf <= 0 or a <= 0 or a == hf:
        return None
    o = obj if feasible else hf
    if fam.sense == "max":
        num, den = math.log(o / hf), math.log(a / hf)
    else:
        num, den = math.log(hf / o), math.log(hf / a)
    return max(0.0, num / den) if den > 0 else None

VERIFY_SECONDS = 60                         # tier rule: expansion + verification of one answer within this budget


class VerifyTimeout(Exception):
    pass


def _raise_timeout(*_):
    raise VerifyTimeout("expansion/verification exceeded the time budget")


def verify_with_timeout(fam, p, ans, seconds=VERIFY_SECONDS):
    """expand_answer + fam.verify under a SIGALRM wall-clock limit (main thread, Unix).  A timeout is an infeasible
    answer: (False, 0, 'timed out').  Outside the main thread the call runs without a limit."""
    import signal, threading
    can_alarm = hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread()
    if can_alarm:
        old = signal.signal(signal.SIGALRM, _raise_timeout); signal.alarm(int(seconds))
    try:
        ans = expand_answer(fam, p, ans)
        if ans is None:
            return False, 0, "no JSON answer found"
        return fam.verify(p, ans)
    except VerifyTimeout:
        return False, 0, f"expansion/verification timed out ({seconds} s)"
    finally:
        if can_alarm:
            signal.alarm(0); signal.signal(signal.SIGALRM, old)


def effective_frontier(fam, p, naive, ref_search=None):
    """The denominator of the human-frontier ratio: the published value when one exists (has_lit True), else the
    better of the expert construction and the 10 s reference search.  Returns (value, has_lit)."""
    hf, has_lit = human_frontier(fam, p, naive, ref_search)
    if hf is None or hf <= 0:
        return None, has_lit
    if not has_lit and ref_search is not None:
        better = (ref_search > hf) if fam.sense == "max" else (ref_search < hf)
        if better:
            hf = ref_search
    return hf, has_lit


def frontier_ratio(fam, p, naive, obj, feasible, ref_search=None):
    """HEADLINE.  Human-frontier ratio: the answer divided by the best construction humans have published for this
    instance (for a minimisation family, frontier / answer).  1 = parity with the human frontier, > 1 = a verified
    record, 0 = no valid answer.  Returns (ratio, kind): kind 'literature' when a published value exists for the
    instance, 'textbook' when the frontier is the best expert construction (deformed / random-parameter families,
    where nothing better has been published)."""
    hf, has_lit = effective_frontier(fam, p, naive, ref_search)
    if hf is None:
        return None, None
    kind = "literature" if has_lit else "textbook"
    if not feasible or obj is None or obj <= 0:
        return 0.0, kind
    return (obj / hf if fam.sense == "max" else hf / obj), kind

def _log_ratio(x, y):
    """Keep ordinary ratios accurate and support integer sizes beyond float range."""
    try:
        ratio = x / y
    except OverflowError:
        ratio = float("inf")
    if 0 < ratio < float("inf"):
        return math.log(ratio)
    return math.log(x) - math.log(y)


def _reference_gap(fam, p, naive, obj, feasible, ref_search, allowed_kinds):
    b, kind = anchor(fam, p)
    h, _ = effective_frontier(fam, p, naive, ref_search)
    if kind not in allowed_kinds or b is None or h is None or b <= 0 or h <= 0:
        return None, kind
    den = _log_ratio(b, h) if fam.sense == "max" else _log_ratio(h, b)
    if den <= 0:
        return None, kind
    if not feasible or obj is None or obj <= 0:
        return 0.0, kind
    num = _log_ratio(obj, h) if fam.sense == "max" else _log_ratio(h, obj)
    value = max(0.0, num / den)
    if value > 1.0 and kind in ("bound", "trivial"):
        kind += "!"  # A verified object beyond a proven bound requires investigation.
    return value, kind


def closed_gap(fam, p, naive, obj, feasible, ref_search=None):
    """Logarithmic progress from the fixed scoring reference to a proven bound.

    Use exactly the same h as frontier_ratio: published frontier when available,
    otherwise the fixed construction reference. Invalid answers and answers no
    better than h score zero. Conjectures, missing bounds and nonpositive
    reference-to-bound gaps are excluded (None), independently of model outcome.
    No upper clipping hides a bound inconsistency; such results are tagged '!'.
    """
    return _reference_gap(fam, p, naive, obj, feasible, ref_search, ("bound", "trivial"))


def conjectured_gap(fam, p, naive, obj, feasible, ref_search=None):
    """Progress from the same fixed reference to a conjectured target, reported separately."""
    return _reference_gap(fam, p, naive, obj, feasible, ref_search, ("conjecture",))



# ----------------------------------------------------------------------------
# Two search-resistant families (2026-09-13): progress on them comes from algebraic / additive structure, and
# local search stalls near the textbook construction even with large compute.
# ----------------------------------------------------------------------------
class LinEqFree(SetFamily):
    """Subset of {1..n} with no non-trivial solution of a x + b y = (a + b) z (Ruzsa's framework; a = b = 1 is 3-AP-free)."""
    name = "lineq"
    title = "Linear-Equation-Free"

    def law(self, p, obj):
        n = p["n"]
        c = (-math.log(obj / n) / math.sqrt(math.log(n))) if 0 < obj < n and n > 2 else None
        return {"name": "lineq_c", "value": c, "better": "lower", "lower": None, "upper": None,
                "note": "|S| = n exp(-c sqrt(ln n)); Behrend-type constructions give a finite c for every invariant equation, "
                        "the Roth-type upper bounds leave the growth open; no tables exist for (a, b) != (1, 1)"}

    def params(self, rng):
        a, b = rng.choice([(1, 2), (1, 3), (2, 3), (1, 4), (3, 4), (2, 5), (3, 5), (1, 5)])
        return {"a": a, "b": b, "n": rng.randint(300, 1200)}

    def statement(self, p):
        a, b, n = p["a"], p["b"], p["n"]
        return (f"Find a subset S of {{1, 2, ..., {n}}} of maximum possible size containing no non-trivial solution of "
                f"{a}*x + {b}*y = {a + b}*z with x, y, z in S (a solution is trivial only when x = y = z). Output: the "
                f"elements of S in increasing order, as a JSON list of integers.")

    def ground(self, p):
        return range(1, p["n"] + 1)

    def can_add(self, p, st, x):
        a, b, c = p["a"], p["b"], p["a"] + p["b"]
        S = st["S"]
        for y in S:
            t = a * x + b * y                       # x in role 1, y in role 2
            if t % c == 0 and (t // c) in S and not (x == y):
                return False
            t = a * y + b * x                       # x in role 2
            if t % c == 0 and (t // c) in S and not (x == y):
                return False
            t = c * x - a * y                       # x in role 3 (z), y in role 1
            if t % b == 0 and (t // b) in S and not (y == x):
                return False
        # x with itself in two roles: a x + b x = c x -> z = x, trivial; c x = a x + b v -> v = x, trivial
        return True

    def verify(self, p, ans):
        a, b, c, n = p["a"], p["b"], p["a"] + p["b"], p["n"]
        if not isinstance(ans, list) or any(not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= n for v in ans):
            return False, 0, f"answer must be a list of integers in 1..{n}"
        if len(set(ans)) != len(ans):
            return False, 0, "elements must be distinct"
        S = set(ans)
        arr = np.asarray(sorted(S), dtype=np.int64)
        for x in arr.tolist():
            t = a * x + b * arr
            ok = (t % c == 0)
            z = t[ok] // c
            ys = arr[ok]
            for zz, yy in zip(z.tolist(), ys.tolist()):
                if zz in S and not (x == yy == zz):
                    return False, 0, f"non-trivial solution {a}*{x} + {b}*{yy} = {c}*{zz}"
        return True, len(S), ""

    def naive(self, p):
        return sorted(self.greedy(p, list(self.ground(p)))["S"])

    def upper(self, p):
        return None


class Kakeya:
    """Smallest subset of F_q^n containing a full line in every direction."""
    name = "kakeya"
    title = "Kakeya"
    sense = "min"

    def law(self, p, obj):
        q, n = p["q"], p["n"]
        return {"name": "kakeya_density", "value": obj / q ** n, "better": "lower",
                "lower": self.upper(p) / q ** n, "upper": None,
                "note": "|K| / q^n; Bukh-Chao (2021) lower bound (2 - 1/q)^-(n-1); "
                        "the known construction matches its leading term for fixed n and growing q"}

    def params(self, rng):
        return dict(zip(("q", "n"), rng.choice([(5, 3), (7, 3), (11, 3), (5, 4)])))

    def statement(self, p):
        q, n = p["q"], p["n"]
        return (f"Find a subset K of F_{q}^{n} (vectors of length {n} with entries in 0..{q - 1}, arithmetic mod {q}) of "
                f"minimum possible size that contains a full line in every direction: for every nonzero direction d "
                f"(directions are taken up to nonzero scalar multiples; there are {(q ** n - 1) // (q - 1)} of them) there "
                f"must be a point a with all {q} points a + t d (t in F_{q}) in K. Output: the points of K as a JSON list of "
                f"lists of {n} integers.")

    def _dirs(self, q, n):
        from itertools import product
        out = []
        for v in product(range(q), repeat=n):
            nz = [c for c in v if c]
            if nz and nz[0] == 1:                   # normalised: first nonzero coordinate is 1
                out.append(v)
        return out

    def _enc(self, v, q):
        e = 0
        for c in v:
            e = e * q + c
        return e

    def verify(self, p, ans):
        q, n = p["q"], p["n"]
        if not isinstance(ans, list) or not ans or any(not (isinstance(v, list) and len(v) == n) for v in ans):
            return False, 0, f"answer must be a non-empty list of vectors of length {n}"
        if any(not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < q for c in v) for v in ans):
            return False, 0, f"entries must be integers in 0..{q - 1}"
        pts = [tuple(v) for v in ans]
        if len(set(pts)) != len(pts):
            return False, 0, "points must be distinct"
        K = {self._enc(v, q) for v in pts}
        by_zero = [[a for a in pts if a[i] == 0] for i in range(n)]     # every line in direction d (first nonzero
        for d in self._dirs(q, n):                                       # coordinate i) meets {a_i = 0} exactly once
            i = next(k for k, c in enumerate(d) if c)
            found = False
            for a in by_zero[i]:
                if all(self._enc(tuple((ai + t * di) % q for ai, di in zip(a, d)), q) in K for t in range(1, q)):
                    found = True
                    break
            if not found:
                return False, 0, f"no full line in direction {list(d)}"
        return True, len(pts), ""

    def objective(self, p, ans):
        return len(ans)

    def naive(self, p):                        # the whole space: every line through the origin
        from itertools import product
        return [list(v) for v in product(range(p["q"]), repeat=p["n"])]

    def upper(self, p):                        # a LOWER bound on |K|: Bukh-Chao 2021, Theorem 1
        q, n = p["q"], p["n"]
        num, den = q ** (2*n-1), (2*q-1) ** (n-1)
        return (num + den - 1) // den

    def search(self, p, seconds, rng):
        """Greedy cover: for each uncovered direction add the line (over sampled base points) that costs fewest new points."""
        q, n, end = p["q"], p["n"], now() + seconds
        dirs = self._dirs(q, n)
        best = None
        while best is None or now() < end:
            order = dirs[:]
            rng.shuffle(order)
            K = set()
            for d in order:
                if now() >= end and best is not None:
                    break
                i = next(k for k, c in enumerate(d) if c)           # base points with a_i = 0 hit every line once
                cands = []
                for _ in range(min(300, q ** (n - 1))):
                    a = [rng.randrange(q) for _ in range(n)]; a[i] = 0
                    a = tuple(a)
                    line = [self._enc(tuple((ai + t * di) % q for ai, di in zip(a, d)), q) for t in range(q)]
                    cost = sum(1 for e in line if e not in K)
                    cands.append((cost, line))
                    if cost == 0:
                        break
                cost, line = min(cands, key=lambda c: c[0])
                K.update(line)
            ok, obj, _ = self.verify(p, self._decode(K, q, n))
            if ok and (best is None or obj < len(best)):
                best = self._decode(K, q, n)
        return best

    def _decode(self, K, q, n):
        out = []
        for e in sorted(K):
            v = []
            for _ in range(n):
                v.append(e % q); e //= q
            out.append(v[::-1])
        return out


FAMILIES.update({f.name: f for f in (LinEqFree(), Kakeya())})
HEADROOM["open"] += ["lineq", "kakeya"]


# ----------------------------------------------------------------------------
# Two families chosen for the size of the gap between the best human construction and the proven bound
# (2026-09-13): progression-free sets in F_q^n for q >= 5 (the cap-set problem's siblings; the Ellenberg-Gijswijt
# bound is computed exactly), and mutually orthogonal Latin squares of non-prime-power order (N(10) is between 2
# and 9 since 1960; N(12) between 5 and 11).
# ----------------------------------------------------------------------------
def eg_bound(q, n):
    """Ellenberg-Gijswijt (2017): a 3-AP-free subset of F_q^n has size <= 3 * M, where M is the number of monomials
    in n variables with each exponent <= q - 1 and total degree <= (q - 1) n / 3.  Exact count by dynamic programming."""
    D = ((q - 1) * n) // 3
    ways = [1] + [0] * D
    for _ in range(n):
        new = [0] * (D + 1)
        for tot in range(D + 1):
            if ways[tot]:
                for e in range(min(q - 1, D - tot) + 1):
                    new[tot + e] += ways[tot]
        ways = new
    return 3 * sum(ways)


class ProgressionFreeQ(SetFamily):
    """Subset of F_q^n (q odd prime) with no three distinct points x, y, z with x + z = 2 y (a 3-term progression)."""
    name = "apfree_q"
    title = "Progression-Free-Fq"
    KNOWN = {(5, 5): 194, (5, 6): 649}          # q=5: 3-AP-free sets are exactly caps (every 3-subset of a line of F_5 is an AP).
    # (5,5): 194-point affine chart of Edel's 195-cap in PG(5,5), re-verified 2026-09-16; the cited 195 affine claim is unresolved.
    # (5,6): 649-point affine chart of Edel's 675-cap in PG(6,5), matching the bound quoted by Elsholtz-Pach (2020).
    # Both witnesses pass primary and independent checkers; see frontier_audits/2026-09-16/affine-chart-checks.json.
    KNOWN_CITED = set()                        # entries still lacking an independently checked object

    def law(self, p, obj):
        q, n = p["q"], p["n"]
        return {"name": f"apfree_q{q}_lambda", "value": obj ** (1 / n), "better": "higher", "lower": None,
                "upper": eg_bound(q, n) ** (1 / n),
                "note": f"|S|^(1/n) in F_{q}^n; Ellenberg-Gijswijt gives the exponent bound, constructions are far below it"}

    def params(self, rng):
        return dict(zip(("q", "n"), rng.choice([(5, 4), (5, 5), (7, 3), (7, 4)])))

    def statement(self, p):
        q, n = p["q"], p["n"]
        return (f"Find a subset S of F_{q}^{n} (vectors of length {n} with entries in 0..{q - 1}, arithmetic mod {q}) of "
                f"maximum possible size containing no three distinct vectors x, y, z with x + z = 2y (coordinate-wise "
                f"mod {q}) -- a 3-term-progression-free set. Output: a JSON list of the vectors, each written as a string "
                f"of {n} digits (at most 20000 vectors are accepted).")

    def ground(self, p):
        return range(p["q"] ** p["n"])

    def _vec(self, x, p):
        q, n = p["q"], p["n"]
        v = []
        for _ in range(n):
            v.append(x % q); x //= q
        return tuple(v[::-1])

    def _code(self, v, q):
        c = 0
        for a in v:
            c = c * q + a
        return c

    def can_add(self, p, st, x):
        q = p["q"]; inv2 = (q + 1) // 2
        S = st["S"]; vx = self._vec(x, p)
        for y in S:
            vy = self._vec(y, p)
            if self._code(tuple((2 * b - a) % q for a, b in zip(vx, vy)), q) in S:      # x, y, z = 2y - x
                return False
            if self._code(tuple((2 * a - b) % q for a, b in zip(vx, vy)), q) in S:      # y, x, z = 2x - y (x in the middle)
                return False
        return True

    def verify(self, p, ans):
        q, n = p["q"], p["n"]
        if not isinstance(ans, list) or any(not isinstance(w, str) or len(w) != n or any(c not in "0123456789"[:q] for c in w) for w in ans):
            return False, 0, f"answer must be a list of strings of {n} digits in 0..{q - 1}"
        vecs = [tuple(int(c) for c in w) for w in ans]
        if not vecs:
            return False, 0, "answer must be a non-empty list"
        if len(set(vecs)) != len(vecs):
            return False, 0, "vectors must be distinct"
        if len(vecs) > 20000:
            return False, 0, "too many vectors (limit 20000)"
        A = np.asarray(vecs, dtype=np.int64); pw = q ** np.arange(n - 1, -1, -1, dtype=np.int64)
        codes = A @ pw; S = set(codes.tolist()); m = len(vecs)
        step = max(1, 2_000_000 // max(1, m))
        for i0 in range(0, m, step):
            X = A[i0:i0 + step]
            Z = (2 * A[None, :, :] - X[:, None, :]) % q                    # z = 2y - x for x in block, all y
            zc = Z @ pw
            hit = np.vectorize(S.__contains__)(zc)
            ii, jj = np.nonzero(hit)
            for a, b in zip(ii.tolist(), jj.tolist()):
                x, y = i0 + a, b
                if x != y and int(zc[a, b]) != int(codes[x]):
                    return False, 0, "contains a 3-term progression"
        return True, m, ""

    def naive(self, p):                        # {0,1}^n: x + z = 2y forces x = y = z coordinate-wise for odd q
        from itertools import product
        return ["".join(str(c) for c in v) for v in product((0, 1), repeat=p["n"])]

    def upper(self, p):
        return eg_bound(p["q"], p["n"])

    def search(self, p, seconds, rng):
        q = p["q"]
        return ["".join(str(c) for c in self._vec(x, p)) for x in super().search(p, seconds, rng)]


class MOLS:
    """k mutually orthogonal Latin squares of order n (n not a prime power); maximise k."""
    name = "mols"
    title = "MOLS"
    sense = "max"
    KNOWN_BEST = {10: 2, 12: 5, 14: 4, 15: 4, 18: 5, 20: 4, 21: 5, 22: 3, 24: 7, 26: 4, 28: 5, 30: 4}   # Handbook table as
    # updated in Miller-Abel-Valkov-Fraser (Symmetry 2024, Table 1): N(14) >= 4 (Todorov 2012), N(18) >= 5 (Abel 2015); checked 2026-09-13

    def law(self, p, obj):
        n = p["n"]
        return {"name": "mols_ratio", "value": obj / (n - 1), "better": "higher", "lower": None, "upper": 1.0,
                "note": "k / (n - 1); a complete set (ratio 1) exists iff a projective plane of order n exists; "
                        "N(10) in [2, 9] since 1960"}

    def params(self, rng):
        return {"n": rng.choice([10, 12, 14, 15, 18, 20])}

    def statement(self, p):
        n = p["n"]
        return (f"Find as many mutually orthogonal Latin squares of order {n} as possible. A Latin square is an {n} x {n} "
                f"array over the symbols 0..{n - 1} with every symbol exactly once in each row and each column; two squares "
                f"L, M are orthogonal when the {n * n} pairs (L[i][j], M[i][j]) are all distinct. Output: a JSON list of "
                f"squares, each a list of {n} rows, each row a list of {n} integers.")

    def verify(self, p, ans):
        n = p["n"]
        if not isinstance(ans, list) or not ans:
            return False, 0, "answer must be a non-empty list of Latin squares"
        sq = []
        for t, L in enumerate(ans):
            if not (isinstance(L, list) and len(L) == n and all(isinstance(r, list) and len(r) == n for r in L)):
                return False, 0, f"square {t} must be {n} x {n}"
            if any(not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < n for c in r) for r in L):
                return False, 0, f"square {t}: entries must be integers in 0..{n - 1}"
            A = np.asarray(L, dtype=np.int64)
            if any(len(set(A[i, :].tolist())) != n for i in range(n)) or any(len(set(A[:, j].tolist())) != n for j in range(n)):
                return False, 0, f"square {t} is not Latin"
            sq.append(A)
        for a in range(len(sq)):
            for b in range(a + 1, len(sq)):
                if len(set((sq[a] * n + sq[b]).ravel().tolist())) != n * n:
                    return False, 0, f"squares {a} and {b} are not orthogonal"
        return True, len(sq), ""

    def objective(self, p, ans):
        return len(ans)

    def naive(self, p):                        # one square: the cyclic group table (k = 1)
        n = p["n"]
        return [[[(i + j) % n for j in range(n)] for i in range(n)]]

    def upper(self, p):
        """N(n) <= n - 1, with equality iff a projective plane of order n exists.  Tighter proven bounds: no plane of
        order 10 (Lam-Thiel-Swiercz 1989) gives N(10) <= 8; Bruck-Ryser excludes planes of order n = 1, 2 (mod 4) when
        n is not a sum of two squares (n = 14, 21, 22, 30 here), giving N(n) <= n - 2."""
        n = p["n"]
        if n == 10:
            return 8
        if n % 4 in (1, 2) and not any(a * a + b * b == n for a in range(int(n ** 0.5) + 1) for b in range(a, int(n ** 0.5) + 1)):
            return n - 2
        return n - 1

    def search(self, p, seconds, rng):
        """Product construction from prime-power factors (MacNeish): k = min over factors of (q^e - 1) squares."""
        n = p["n"]
        fac = []; m = n; d = 2
        while d * d <= m:
            e = 0
            while m % d == 0:
                m //= d; e += 1
            if e:
                fac.append(d ** e)
            d += 1
        if m > 1:
            fac.append(m)
        k = min(f - 1 for f in fac)
        if k < 1:
            return self.naive(p)
        def field_squares(pe):               # pe a prime power; here we only need prime factors (tables from Z_p)
            return [[[ (a * i + j) % pe for j in range(pe)] for i in range(pe)] for a in range(1, pe)]
        parts = []
        for f in fac:
            if all(f % d for d in range(2, int(f ** 0.5) + 1)):
                parts.append(field_squares(f)[:k])
            else:                             # proper prime power: use only the cyclic square (k limited to 1)
                parts.append([[[ (i + j) % f for j in range(f)] for i in range(f)]])
        k = min(len(pp) for pp in parts)
        out = []
        for t in range(k):
            sqs = [pp[t] for pp in parts]
            def mixed(idx):
                r = []; x = idx
                for f in reversed(fac):
                    r.append(x % f); x //= f
                return r[::-1]
            def unmix(digs):
                x = 0
                for dgt, f in zip(digs, fac):
                    x = x * f + dgt
                return x
            L = [[unmix([sqs[u][mixed(i)[u]][mixed(j)[u]] for u in range(len(fac))]) for j in range(n)] for i in range(n)]
            out.append(L)
        return out


FAMILIES.update({f.name: f for f in (ProgressionFreeQ(), MOLS())})

class Schur:
    """Sum-free k-colouring of {1..N}: no monochromatic x, y, x + y (x = y allowed); maximise N (the Schur number S(k))."""
    name = "schur"
    title = "Schur"
    sense = "max"
    # S(3) = 13, S(4) = 44 (exact), S(5) = 160 (Heule 2017, SAT); S(6) >= 536 (Fredricksen-Sweet 2000);
    # S(7) >= 1696 (Rowley 2021, arXiv:2107.03560); original ancillary colouring double-checked 2026-09-16.
    # S(8) >= 5362 (Bengone et al. 2026, arXiv:2607.15034, shifted S-templates: S(k+2) >= 10 S(k) + 2).  Table values, 2026-09-14.
    KNOWN_BEST = {3: 13, 4: 44, 5: 160, 6: 536, 7: 1696, 8: 5362}
    EXACT = {3: 13, 4: 44, 5: 160}
    MAX_N = 200000

    def law(self, p, obj):
        k = p["k"]
        return {"name": "schur_base", "value": obj ** (1.0 / k) if obj > 0 else None, "better": "higher",
                "lower": 10 ** 0.5, "upper": None, "note": "S(k)^{1/k}; S(k+2) >= 10 S(k) + 2 gives base >= sqrt(10); the upper bound e k! gives no finite base"}

    def params(self, rng):
        return {"k": rng.choice([5, 6, 7])}

    def statement(self, p):
        k = p["k"]
        return (f"Choose N as large as you can and colour the integers 1..N with {k} colours (0..{k - 1}) so that there are "
                f"no x, y with x <= y (x = y allowed) and x + y <= N such that x, y and x + y all have the same colour. "
                f"Output: a JSON list of N integers in 0..{k - 1}, the colours of 1, 2, ..., N in order. Objective: N. "
                f"The verifier accepts at most {self.MAX_N} entries.")

    def verify(self, p, ans):
        k = p["k"]
        if not isinstance(ans, list) or not ans:
            return False, 0, "answer must be a non-empty list of colours"
        if len(ans) > self.MAX_N:
            return False, 0, f"too many entries (limit {self.MAX_N})"
        if any(not isinstance(c, int) or isinstance(c, bool) or not 0 <= c < k for c in ans):
            return False, 0, f"colours must be integers in 0..{k - 1}"
        N = len(ans)
        classes = [[] for _ in range(k)]
        for i, c in enumerate(ans, 1):
            classes[c].append(i)
        for c, P in enumerate(classes):
            S = set(P)
            for a in range(len(P)):
                x = P[a]
                for b in range(a, len(P)):
                    y = P[b]
                    if x + y > N:
                        break
                    if x + y in S:
                        return False, 0, f"colour {c} contains {x}, {y} and {x + y}"
        return True, N, ""

    def objective(self, p, ans):
        return len(ans)

    def naive(self, p):
        """Schur's recursion from the 2-colouring 0 1 1 0 of 1..4: a k-colouring of 1..N gives a (k+1)-colouring of
        1..3N+1 (old colours on 1..N and on 2N+2..3N+1 shifted, the new colour on N+1..2N+1): N = 4, 13, 40, 121, 364, ..."""
        col = [0, 1, 1, 0]
        for _ in range(p["k"] - 2):
            N = len(col); new = max(col) + 1
            col = col + [new] * (N + 1) + col
        return col

    def upper(self, p):
        """S(k) <= R_k(3) - 2 <= floor(e k!) - 1 (Schur); exact for k <= 5; R_6(3) <= 1898 gives S(6) <= 1896 (loose)."""
        k = p["k"]
        if k in self.EXACT:
            return self.EXACT[k]
        if k == 6:
            return 1896
        return int(math.e * math.factorial(k)) - 1

    def search(self, p, seconds, rng):
        """Randomised greedy with restarts: colour 1, 2, ... in turn with a colour that creates no monochromatic x + y = i;
        stop when none exists; keep the longest colouring found within the budget (the naive recursion is the floor)."""
        k = p["k"]; best = self.naive(p); t0 = time.time()
        while time.time() - t0 < seconds:
            col = []; classes = [set() for _ in range(k)]
            i = 1
            while True:
                cands = [c for c in range(k) if not any((i - x) in classes[c] and (i - x) >= x for x in classes[c])]
                if not cands:
                    break
                c = min(cands, key=lambda c: (len(classes[c]) + rng.random() * 3))
                col.append(c); classes[c].add(i); i += 1
                if i > self.MAX_N:
                    break
            if len(col) > len(best):
                best = col
        return best


FAMILIES.update({f.name: f for f in (Schur(),)})

class Zarankiewicz:
    """n x n 0/1 matrix with no all-ones 4 x 4 submatrix (rows and columns need not be consecutive); maximise the number
    of ones (the Zarankiewicz number z(n; 4)).  Best constructions ~ n^{5/3}, proven bound O(n^{7/4}): exponent gap 1/12."""
    name = "zarank"
    title = "Zarankiewicz-K44"
    sense = "max"
    MAX_N = 400

    def law(self, p, obj):
        n = p["n"]
        return {"name": "zarank_exponent", "value": (math.log(obj) / math.log(n)) if obj > 1 else None, "better": "higher",
                "lower": 5 / 3, "upper": 7 / 4, "note": "log(ones)/log(n); constructions n^{5/3}, Kovari-Sos-Turan n^{7/4}"}

    def params(self, rng):
        return {"n": rng.choice([40, 60, 80])}

    def statement(self, p):
        n = p["n"]
        return (f"Construct an {n} x {n} 0/1 matrix with as many ones as possible such that no 4 rows and 4 columns "
                f"(not necessarily consecutive) meet in a 4 x 4 all-ones submatrix. Output: a JSON list of {n} strings, "
                f"each a string of {n} characters '0' or '1' (row by row). Objective: the number of ones.")

    def verify(self, p, ans):
        n = p["n"]
        if n > self.MAX_N:
            return False, 0, f"n > {self.MAX_N} is outside the verified range"
        if not isinstance(ans, list) or len(ans) != n or any(not isinstance(r, str) or len(r) != n or set(r) - set("01") for r in ans):
            return False, 0, f"answer must be a list of {n} strings of {n} characters 0/1"
        rows = [int(r[::-1], 2) for r in ans]
        ones = sum(bin(r).count("1") for r in rows)
        pc = lambda x: bin(x).count("1")
        for i in range(n):
            ri = rows[i]
            if pc(ri) < 4:
                continue
            partners = [j for j in range(i + 1, n) if pc(ri & rows[j]) >= 4]
            for a in range(len(partners)):
                j = partners[a]; cij = ri & rows[j]
                for b in range(a + 1, len(partners)):
                    k = partners[b]; cijk = cij & rows[k]
                    if pc(cijk) < 4:
                        continue
                    for c in range(b + 1, len(partners)):
                        if pc(cijk & rows[partners[c]]) >= 4:
                            return False, 0, f"rows {i}, {j}, {k}, {partners[c]} share 4 columns of ones"
        return True, ones, ""

    def objective(self, p, ans):
        return self.verify(p, ans)[1]

    def _projective_plane(self, p):
        """Point-line incidence matrix of PG(2, q), q the largest prime with q^2 + q + 1 <= n, padded with zeros: it has no
        2 x 2 all-ones submatrix, hence no 4 x 4; (q^2 + q + 1)(q + 1) ones."""
        n = p["n"]; q = 2
        for c in range(2, n):
            if c * c + c + 1 <= n and all(c % d for d in range(2, int(c ** 0.5) + 1)):
                q = c
        m = q * q + q + 1
        pts = [(x, y, 1) for x in range(q) for y in range(q)] + [(x, 1, 0) for x in range(q)] + [(1, 0, 0)]
        lines = pts[:]                                     # PG(2, q) is self-dual: lines = the same triples
        mat = []
        for a in range(n):
            row = ["0"] * n
            if a < m:
                for b in range(m):
                    if b < m and sum(u * v for u, v in zip(pts[a], lines[b])) % q == 0:
                        row[b] = "1"
            mat.append("".join(row))
        return mat

    def naive(self, p):
        # Preserve frozen references; newly generated references also include NG(q,3) constructions.
        from candidate_families import norm_graph_reference
        candidates = [self._projective_plane(p), norm_graph_reference(p["n"])]
        return max(candidates, key=lambda rows: sum(r.count("1") for r in rows))

    def upper(self, p):
        """Kovari-Sos-Turan: z(n, n; 4, 4) <= 3^{1/4} (n - 3) n^{3/4} + 3 n."""
        n = p["n"]
        return int(3 ** 0.25 * (n - 3) * n ** 0.75 + 3 * n)

    def search(self, p, seconds, rng):
        """Randomised greedy: start from the naive matrix, visit the zero cells in random order and set a one whenever the
        matrix stays K_{4,4}-free (checked incrementally for the touched row)."""
        n = p["n"]; t0 = time.time()
        rows = [int(r[::-1], 2) for r in self.naive(p)]
        pc = lambda x: bin(x).count("1")
        def ok_after(i):
            ri = rows[i]
            partners = [j for j in range(n) if j != i and pc(ri & rows[j]) >= 4]
            for a in range(len(partners)):
                cij = ri & rows[partners[a]]
                for b in range(a + 1, len(partners)):
                    cijk = cij & rows[partners[b]]
                    if pc(cijk) < 4:
                        continue
                    for c in range(b + 1, len(partners)):
                        if pc(cijk & rows[partners[c]]) >= 4:
                            return False
            return True
        cells = [(i, j) for i in range(n) for j in range(n)]
        rng.shuffle(cells)
        for i, j in cells:
            if time.time() - t0 > seconds:
                break
            if rows[i] >> j & 1:
                continue
            rows[i] |= 1 << j
            if not ok_after(i):
                rows[i] &= ~(1 << j)
        return ["".join("1" if rows[i] >> j & 1 else "0" for j in range(n)) for i in range(n)]


FAMILIES.update({f.name: f for f in (Zarankiewicz(),)})
HEADROOM.setdefault("candidate", []).append("zarank")   # v1.2 candidate (2026-09-14): table-free pilot

class CoveringDesign:
    """Covering design C(v, k, t): as few k-subsets (blocks) of {0..v-1} as possible such that every t-subset lies in at
    least one block; minimise the number of blocks.  Frontier and proven lower bound per (v, k, t) from the La Jolla
    Covering Repository (bench/data/covering_table.json); the best known sizes are search-found (simulated annealing,
    tabu, ...), the lower bounds are Schoenheim-type theorems."""
    name = "covering"
    title = "Covering"
    sense = "min"
    MAX_BLOCKS = 20000
    _table = None

    @classmethod
    def table(cls):
        if cls._table is None:
            import os, json as _json
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "covering_table.json")
            cls._table = _json.load(open(path))["table"] if os.path.exists(path) else {}
        return cls._table

    def entry(self, p):
        return self.table().get(f"{p['v']},{p['k']},{p['t']}")

    def law(self, p, obj):
        from math import comb
        v, k, t = p["v"], p["k"], p["t"]
        return {"name": "covering_excess", "value": obj * comb(k, t) / comb(v, t) if obj else None, "better": "lower",
                "lower": 1.0, "upper": None, "note": "blocks x C(k,t) / C(v,t): 1 would be a Steiner system"}

    def params(self, rng):
        return dict(zip(("v", "k", "t"), rng.choice([(16, 6, 3), (20, 6, 3), (15, 7, 4)])))

    def statement(self, p):
        v, k, t = p["v"], p["k"], p["t"]
        return (f"Find as few blocks as possible, each a {k}-subset of {{0, 1, ..., {v - 1}}}, such that every {t}-subset of "
                f"{{0, ..., {v - 1}}} is contained in at least one block (a ({v}, {k}, {t}) covering design). Output: a JSON "
                f"list of blocks, each a list of {k} distinct integers in 0..{v - 1}. Objective: the number of blocks "
                f"(smaller is better). The verifier accepts at most {self.MAX_BLOCKS} blocks.")

    def verify(self, p, ans):
        from itertools import combinations
        v, k, t = p["v"], p["k"], p["t"]
        if not isinstance(ans, list) or not ans:
            return False, 0, "answer must be a non-empty list of blocks"
        if len(ans) > self.MAX_BLOCKS:
            return False, 0, f"too many blocks (limit {self.MAX_BLOCKS})"
        blocks = []
        for i, b in enumerate(ans):
            if not (isinstance(b, list) and len(b) == k and all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x < v for x in b)) or len(set(b)) != k:
                return False, 0, f"block {i} must be {k} distinct integers in 0..{v - 1}"
            blocks.append(tuple(sorted(b)))
        covered = set()
        for b in blocks:
            covered.update(combinations(b, t))
        from math import comb
        if len(covered) != comb(v, t):
            missing = next(s for s in combinations(range(v), t) if s not in covered)
            return False, 0, f"the {t}-subset {list(missing)} is not covered"
        return True, len(blocks), ""

    def objective(self, p, ans):
        return len(ans)

    def _greedy(self, p, rng, seconds, cands=60):
        from itertools import combinations
        v, k, t = p["v"], p["k"], p["t"]
        tsets = list(combinations(range(v), t)); idx = {s: i for i, s in enumerate(tsets)}
        best = None; t0 = time.time()
        while True:
            unc = set(range(len(tsets))); unc_list = None; blocks = []
            while unc:
                cb, cg = None, -1
                pool = list(unc) if len(unc) <= 4000 else None
                for _ in range(cands):
                    seed = tsets[rng.choice(pool) if pool else next(iter(unc))]
                    blk = set(seed)
                    while len(blk) < k:
                        blk.add(rng.randrange(v))
                    gain = sum(1 for s in combinations(sorted(blk), t) if idx[s] in unc)
                    if gain > cg:
                        cb, cg = sorted(blk), gain
                blocks.append(cb)
                for s in combinations(cb, t):
                    unc.discard(idx[s])
            if best is None or len(blocks) < len(best):
                best = blocks
            if time.time() - t0 >= seconds:
                return best

    def naive(self, p):                       # one deterministic greedy pass (the textbook heuristic)
        import random as _random
        return self._greedy(p, _random.Random(0), 0.0)

    def upper(self, p):                       # a LOWER bound on the number of blocks (sense = min): the repository's proven bound
        e = self.entry(p)
        return e[1] if e else None

    def search(self, p, seconds, rng):
        return self._greedy(p, rng, seconds)


FAMILIES.update({f.name: f for f in (CoveringDesign(),)})
HEADROOM["open"] += ["covering"]     # version 1 (added 2026-09-14 after the pilot): construction-type, LJCR frontier at every (v, k, t)
SEARCH_TYPE.append("covering")        # no closed-form expert construction: the zero is the reference search (greedy)


HEADROOM["open"] += ["schur"]        # version 1 (added 2026-09-14 after the pilot): discovery-type, published S(k) for k <= 8

HEADROOM["open"] += ["apfree_q", "mols"]

# Author-approved publication selection (2026-09-15). Keep historical task IDs and the full old selection.
HEADROOM["legacy15"] = list(HEADROOM["open"])
HEADROOM["open"].remove("kakeya")
HEADROOM["bounded"].append("kakeya")

# Author-approved additions. C1 remains a separate frozen historical pilot.
from candidate_families import Shannon, Trifference
FAMILIES.update({f.name: f for f in (Shannon(), Trifference())})
HEADROOM["core12"] = list(HEADROOM["open"])
HEADROOM["open"].extend(["shannon", "trifference"])
SEARCH_UNCLASSIFIED = ["trifference"]  # Shannon paired 10/600 s product-code search audited 2026-09-20.

# ----------------------------------------------------------------------------
# Compact answer formats (2026-09-13).  Large objects may be given as a construction that the verifier expands
# to an explicit object before the usual check; the model still uses no tools, and nothing is trusted: the
# expanded object goes through the same verify().  Each family lists which forms it accepts.
# ----------------------------------------------------------------------------
EXPAND_CAP = 60000            # maximum number of elements an expansion may produce


def _multiset_perms(seq):
    """All distinct arrangements of a sequence (multiset permutations), generated lazily."""
    from collections import Counter
    cnt = Counter(seq); n = len(seq)
    def rec(prefix):
        if len(prefix) == n:
            yield tuple(prefix); return
        for v in sorted(cnt):
            if cnt[v]:
                cnt[v] -= 1; prefix.append(v)
                yield from rec(prefix)
                prefix.pop(); cnt[v] += 1
    yield from rec([])


def _orbit_vectors(gens, signs, perms):
    out = set()
    for v in gens:
        v = tuple(v)
        arrangements = _multiset_perms(v) if perms else [v]
        for w in arrangements:
            nz = [i for i, c in enumerate(w) if c != 0]
            if signs:
                for mask in range(1 << len(nz)):
                    u = list(w)
                    for t, i in enumerate(nz):
                        if mask >> t & 1:
                            u[i] = -u[i]
                    out.add(tuple(u))
                    if len(out) > EXPAND_CAP:
                        raise ValueError("orbit too large")
            else:
                out.add(w)
                if len(out) > EXPAND_CAP:
                    raise ValueError("orbit too large")
    return [list(u) for u in sorted(out)]


def _digit_set(spec, lo, hi):
    """Integers in [lo, hi] whose base-b digits (length L) all lie in `allowed`, optionally with a fixed digit-square sum."""
    b, allowed, L = int(spec["base"]), [int(x) for x in spec["allowed"]], int(spec["length"])
    k = spec.get("sum_squares")
    offset = int(spec.get("offset", 0))
    if b < 2 or L < 1 or L > 40 or any(not 0 <= a < b for a in allowed):
        raise ValueError("bad digit spec")
    out = []
    nodes = [0]
    def rec(pos, val, sq):
        nodes[0] += 1
        if len(out) > EXPAND_CAP or nodes[0] > 8 * EXPAND_CAP:
            raise ValueError("digit set too large (element or work cap)")
        if k is not None and sq > k:                      # digit squares only grow: prune
            return
        if pos == L:
            if k is None or sq == k:
                x = val + offset
                if lo <= x <= hi:
                    out.append(x)
            return
        for a in allowed:
            rec(pos + 1, val * b + a, sq + a * a)
    rec(0, 0, 0)
    return sorted(set(out))


def _cayley_edges(spec):
    """Cayley graph of Z_{n1} x ... x Z_{nk} with the given generators (inverses added)."""
    mods = [int(m) for m in spec["moduli"]]
    gens = [tuple(int(g) % m for g, m in zip(gv, mods)) for gv in spec["generators"]]
    if not mods or any(m < 1 for m in mods) or any(len(g) != len(mods) for g in gens):
        raise ValueError("bad cayley spec")
    V = 1
    for m in mods:
        V *= m
    if V > 4000:
        raise ValueError("too many vertices")
    def idx(t):
        v = 0
        for c, m in zip(t, mods):
            v = v * m + (c % m)
        return v
    def add(t, g):
        return tuple((a + b) % m for a, b, m in zip(t, g, mods))
    S = set(gens) | {tuple((-c) % m for c, m in zip(g, mods)) for g in gens}
    S.discard(tuple(0 for _ in mods))
    edges = set()
    from itertools import product
    for t in product(*[range(m) for m in mods]):
        u = idx(t)
        for g in S:
            v = idx(add(t, g))
            if u != v:
                edges.add((min(u, v), max(u, v)))
    return [list(e) for e in sorted(edges)]


def expand_answer(fam, p, ans):
    """Return an explicit answer.  Compact forms are dicts with one recognised key; anything else passes through."""
    if not isinstance(ans, dict):
        return ans
    name = fam.name
    try:
        if name == "kissing" and "quadratic_vectors" in ans:
            return ans  # exact coefficients are checked without floating-point expansion
        if name in ("shannon", "trifference"):
            return fam.expand(p, ans)
        if "orbit" in ans and name in ("kissing", "kissing_theta"):
            gens = ans["orbit"]
            if not isinstance(gens, list) or any(not (isinstance(v, list) and len(v) == p["d"]) for v in gens):
                return ans
            if name == "kissing" and p.get("representation") == "quadratic":
                if (set(ans) - {"orbit", "signs", "perms"}
                        or any(type(ans[k]) is not bool for k in ("signs", "perms") if k in ans)
                        or any(type(c) is not int or not -1000 <= c <= 1000 for v in gens for c in v)):
                    return ans
            return _orbit_vectors([[int(c) for c in v] for v in gens], bool(ans.get("signs", True)), bool(ans.get("perms", True)))
        if "product" in ans and name == "capset":
            parts = ans["product"]
            if not isinstance(parts, list) or not parts:
                return ans
            out = [""]
            for part in parts:
                if not isinstance(part, list) or any(not isinstance(w, str) for w in part):
                    return ans
                out = [a + b for a in out for b in part]
                if len(out) > EXPAND_CAP:
                    raise ValueError("product too large")
            return out
        if "digits" in ans and name in ("apfree", "lineq"):
            return _digit_set(ans["digits"], 1, p["n"])
        if "diff_set" in ans and name == "corners":
            n = p["n"]; D = ans["diff_set"]
            if isinstance(D, dict):
                D = _digit_set(D, -(n - 1), n - 1)
            D = set(int(x) for x in D)
            pts = [[x, y] for x in range(n) for y in range(n) if (x - y) in D]
            if len(pts) > EXPAND_CAP:
                raise ValueError("diff set too large")
            return pts
        if "cayley" in ans and name == "degdiam":
            return _cayley_edges(ans["cayley"])
    except (ValueError, KeyError, TypeError, OverflowError):
        return ans
    return ans


COMPACT = {
    "shannon": ("Certified form allowed: {\"factors\": [{\"words\": [digit strings], \"power\": r}, ...]}. "
                "Each factor lists an actual independent code, r is an integer 1..256 (default 1), and factor length "
                "times power must sum to d. Each factor has 1..4096 distinct words, with at most 16384 words "
                "across factors. Every factor is checked; the product cardinality is computed exactly without "
                "expanding the product. Nested certificates and claimed counts are not accepted. "
                "Compact form allowed: {\"product\": [C1, C2, ...]}, where each Ci is a nonempty list of equal-length "
                "digit strings, denotes all concatenations of one word from each factor. Factor lengths must sum to d. "
                "The complete product is expanded and verified, with the same word limit."),
    "trifference": ("Compact form allowed: {\"linear\": [g1, ..., gk]}, with 1 <= k <= 8 and each gi a ternary "
                   "string of the required length, denotes the set of all linear combinations of the rows over F_3. "
                   "The full set of distinct codewords is expanded and the three-string condition is checked. "
                   "Linearity alone does not guarantee that condition."),
    "kissing": ("Compact form allowed: {\"orbit\": [v1, v2, ...], \"signs\": true, \"perms\": true} lists generator "
                "vectors; the set is every coordinate permutation (\"perms\") and every sign change (\"signs\") of them."),
    "kissing_theta": ("Compact form allowed: {\"orbit\": [v1, v2, ...], \"signs\": true, \"perms\": true} lists generator "
                      "vectors; the set is every coordinate permutation (\"perms\") and every sign change (\"signs\") of them."),
    "capset": ("Compact form allowed: {\"product\": [S1, S2, ...]} where S_i is a list of digit strings in dimension d_i "
               "with d_1 + ... = d; the set is all concatenations."),
    "apfree": ("Compact form allowed: {\"digits\": {\"base\": b, \"allowed\": [digits], \"length\": L, \"sum_squares\": k "
               "(or null), \"offset\": o}}: all integers o + (L-digit base-b numbers with digits in the allowed set and, if "
               "given, digit-square sum k) that lie in {1..n}."),
    "lineq": ("Compact form allowed: {\"digits\": {\"base\": b, \"allowed\": [digits], \"length\": L, \"sum_squares\": k "
              "(or null), \"offset\": o}}: all integers o + (L-digit base-b numbers with digits in the allowed set and, if "
              "given, digit-square sum k) that lie in {1..n}."),
    "corners": ("Compact form allowed: {\"diff_set\": D} with D a list of integers or a digits spec {\"base\", \"allowed\", "
                "\"length\", \"sum_squares\", \"offset\"}: the set is all grid points (x, y) with x - y in D."),
    "degdiam": ("Compact form allowed: {\"cayley\": {\"moduli\": [n1, ...], \"generators\": [[g1..], ...]}}: the Cayley graph "
                "of Z_n1 x ... with those generators and their inverses."),
}

def instance(family, seed):
    fam = FAMILIES[family]
    p = fam.params(random.Random(f"{family}-{seed}"))
    return fam, p


def render(fam, p):
    head = ", ".join(f"{k}={v}" for k, v in p.items() if not isinstance(v, (list, dict)))
    return f"Problem ({fam.title}, {head}). {fam.statement(p)}"


def naive_answer(fam, p):
    return fam.naive_fmt(p) if hasattr(fam, "naive_fmt") else fam.naive(p)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen"); g.add_argument("--family", required=True); g.add_argument("--seed", type=int, default=0)
    v = sub.add_parser("verify"); v.add_argument("--family", required=True); v.add_argument("--seed", type=int, default=0)
    v.add_argument("--answer", required=True)
    d = sub.add_parser("demo"); d.add_argument("--time", type=float, default=3.0); d.add_argument("--seeds", type=int, default=2)
    d.add_argument("--families", nargs="*", default=list(FAMILIES))
    a = ap.parse_args()

    if a.cmd == "gen":
        fam, p = instance(a.family, a.seed)
        print(render(fam, p))
    elif a.cmd == "verify":
        fam, p = instance(a.family, a.seed)
        ans = json.load(open(a.answer))
        ok, obj, msg = fam.verify(p, ans)
        nv = fam.objective(p, naive_answer(fam, p)) if ok else None
        ub = fam.upper(p)
        print(json.dumps({"feasible": ok, "objective": obj, "message": msg, "naive": nv,
                          "bound": ub, "sense": fam.sense}, indent=1))
    else:
        print(f"{'family':12s} {'instance':22s} {'naive':>9s} {'search':>9s} {'bound':>7s}  gap   law (scale-free constant)")
        for name in a.families:
            fam = FAMILIES[name]
            for seed in range(a.seeds):
                fam, p = instance(name, seed)
                rng = random.Random(seed)
                t0 = now()
                nv = fam.objective(p, naive_answer(fam, p))
                ans = fam.search(p, a.time, rng)
                ok, sv, msg = fam.verify(p, ans)
                assert ok, (name, seed, msg)
                ub = fam.upper(p)
                if fam.sense == "max":
                    gap = sv / nv if nv else float("inf")
                else:
                    gap = nv / sv if sv else (1.0 if nv == 0 else float("inf"))
                L = fam.law(p, sv); Ln = fam.law(p, nv)
                iv = f"[{L['lower'] if L['lower'] is not None else '?'}, {L['upper'] if L['upper'] is not None else '?'}]"
                print(f"{name:12s} {json.dumps(p):22s} {nv:9.3f} {sv:9.3f} {str(ub) if ub is not None else '?':>7s}  {gap:4.2f}x  "
                      f"{L['name']}: naive {Ln['value']:.3f} -> search {L['value']:.3f}  open interval {iv}  ({now()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
