"""Exact code constructions: promoted Shannon/trifference families and the zarank candidate.

Sources and the experimental scope are recorded in ASI_FAMILY_CANDIDATES_2026-09-15.md.
Compact forms are checked by expansion or explicit composition theorems; no claimed cardinality is trusted.
"""
from functools import lru_cache
from itertools import combinations, product
import json
import math
from pathlib import Path
import time
from fractions import Fraction


def _words(ans, n, alphabet, limit):
    if not isinstance(ans, list) or not ans or len(ans) > limit:
        return False, f"answer must contain 1..{limit} words"
    if any(not isinstance(w, str) or len(w) != n or set(w) - alphabet for w in ans):
        return False, f"words must have length {n} over {''.join(sorted(alphabet))}"
    if len(set(ans)) != len(ans):
        return False, "words must be distinct"
    return True, ""


class Shannon:
    name = "shannon"
    title = "Odd-Cycle-Zero-Error-Code"
    sense = "max"
    MAX_WORDS = 4096
    MAX_DIM = 256
    MAX_FACTOR_WORDS = 16384

    def params(self, rng):
        return {"q": 7, "d": rng.choice([3, 4, 5, 6])}

    def statement(self, p):
        q, d = p["q"], p["d"]
        return (f"Find as many distinct words of length {d} over digits 0..{q-1} as possible. "
                f"For every two distinct words x,y, some coordinate i must satisfy "
                f"min(abs(x_i-y_i), {q}-abs(x_i-y_i)) >= 2. Symbols wrap around a cycle of length {q}. "
                f"This is an independent set in the {d}-fold strong power of C_{q}. "
                f"Objective: number of words. Literal lists and expanded products accept at most {self.MAX_WORDS} words. "
                "Certified factors may describe larger codes; their exact cardinality is computed from checked factors.")

    @staticmethod
    def _masks(words, q, d):
        masks = [[0] * q for _ in range(d)]
        for j, w in enumerate(words):
            for i, c in enumerate(w):
                masks[i][int(c)] |= 1 << j
        return masks

    @staticmethod
    def _conflicts(word, masks, q, full):
        hit = full
        for i, c in enumerate(word):
            c = int(c)
            hit &= masks[i][c] | masks[i][(c-1) % q] | masks[i][(c+1) % q]
            if not hit:
                break
        return hit

    def verify(self, p, ans):
        q, d = p["q"], p["d"]
        if type(q) is not int or type(d) is not int or q not in (5, 7, 9) or not 1 <= d <= self.MAX_DIM:
            return False, 0, "unsupported q or dimension"
        if isinstance(ans, dict):
            try:
                parts = self.factor_parts(p, ans)
            except (ValueError, TypeError, KeyError):
                return False, 0, "malformed factor certificate"
            count = 1
            for words, power in parts:
                ok, size, msg = self.verify({"q": q, "d": len(words[0])}, words)
                if not ok:
                    return False, 0, "invalid factor: " + msg
                count *= size ** power
            return True, count, ""
        ok, msg = _words(ans, d, set(map(str, range(q))), self.MAX_WORDS)
        if not ok:
            return False, 0, msg
        masks = self._masks(ans, q, d)
        full = (1 << len(ans)) - 1
        for j, word in enumerate(ans):
            if self._conflicts(word, masks, q, full ^ (1 << j)):
                return False, 0, f"word {j} has a confusable partner"
        return True, len(ans), ""

    def expand(self, p, ans):
        if not isinstance(ans, dict) or set(ans) != {"product"}:
            return ans
        parts = ans["product"]
        if not isinstance(parts, list) or not 1 <= len(parts) <= p["d"]:
            raise ValueError("invalid product factors")
        out = [""]
        length = 0
        for part in parts:
            if not isinstance(part, list) or not part or not isinstance(part[0], str):
                raise ValueError("empty or malformed factor")
            n = len(part[0])
            ok, _ = _words(part, n, set(map(str, range(p["q"]))), self.MAX_WORDS)
            length += n
            if not ok or n == 0 or length > p["d"] or len(out) * len(part) > self.MAX_WORDS:
                raise ValueError("invalid or oversized product")
            out = [a + b for a in out for b in part]
        if length != p["d"]:
            raise ValueError("factor dimensions do not sum to d")
        return out

    @classmethod
    def factor_parts(cls, p, ans):
        # The grammar has no claimed size, nested certificates, external files or executable code.
        if set(ans) != {"factors"} or not isinstance(ans["factors"], list) or not 1 <= len(ans["factors"]) <= cls.MAX_DIM:
            raise ValueError("expected a nonempty list of factors")
        parts, dimension, work = [], 0, 0
        for factor in ans["factors"]:
            if not isinstance(factor, dict) or set(factor) not in ({"words"}, {"words", "power"}):
                raise ValueError("factor must have words and optional power")
            words, power = factor["words"], factor.get("power", 1)
            if type(power) is not int or not 1 <= power <= cls.MAX_DIM:
                raise ValueError("invalid power")
            if not isinstance(words, list) or not words or not isinstance(words[0], str):
                raise ValueError("invalid factor words")
            d = len(words[0])
            if d == 0 or not _words(words, d, set(map(str, range(p["q"]))), cls.MAX_WORDS)[0]:
                raise ValueError("invalid factor words")
            dimension += d * power
            work += len(words)
            if dimension > p["d"] or work > cls.MAX_FACTOR_WORDS:
                raise ValueError("certificate exceeds budget")
            parts.append((words, power))
        if dimension != p["d"]:
            raise ValueError("factor dimensions do not sum to d")
        return parts

    @staticmethod
    def bases(q):
        bases = {1: list(map(str, range(0, q-1, 2)))}
        if q == 7:
            data = json.loads((Path(__file__).parent / "data/shannon_c7_base.json").read_text())
            bases.update({int(k): v for k, v in data["bases"].items()})
        elif q == 5:
            bases[2] = [f"{i}{2*i % 5}" for i in range(5)]
        elif q == 9:
            # If the first two differences are in {-1,0,1}, 2*dx+4*dy is
            # never in {-1,0,1} modulo 9 unless dx=dy=0. Checked as 81 words.
            bases[3] = [f"{i}{j}{(2*i+4*j)%9}" for i in range(9) for j in range(9)]
        return bases

    def naive(self, p):
        q, d = p["q"], p["d"]
        bases = self.bases(q)
        sizes, choices = [1], [[]]
        for n in range(1, d+1):
            k = max((k for k in bases if k <= n), key=lambda k: sizes[n-k]*len(bases[k]))
            sizes.append(sizes[n-k]*len(bases[k])); choices.append(choices[n-k]+[k])
        if sizes[d] <= self.MAX_WORDS:
            out = [""]
            for k in choices[d]: out = [a+b for a in out for b in bases[k]]
            return out
        return {"factors": [{"words": bases[k], "power": choices[d].count(k)} for k in sorted(set(choices[d]))]}

    def objective(self, p, ans):
        return self.verify(p, ans)[1]

    @staticmethod
    def theta_upper(q):
        # Rational upper brackets for cos(pi/q). Their exact polynomial signs and
        # monotonic root intervals are checked in test_code_promotion.py.
        c = Fraction({5:809016994374948, 7:900968867902420, 9:939692620785909}[q], 10**15)
        return q*c/(1+c)

    def upper(self, p):
        # Lovasz theta is multiplicative for strong products and bounds independence.
        b = self.theta_upper(p["q"]) ** p["d"]
        return b.numerator // b.denominator

    def law(self, p, obj):
        return {"name": "shannon_base", "value": obj ** (1/p["d"]), "better": "higher",
                "lower": None, "upper": float(self.theta_upper(p["q"])),
                "note": "M^(1/d); rigorous rational upper bound on Lovasz theta"}

    def search(self, p, seconds, rng):
        start = time.monotonic()
        best = self.naive(p)
        q, d = p["q"], p["d"]
        if isinstance(best, dict):
            # Search every seed gadget, then optimise the integer partition of d.
            # This measures gains that propagate through products, not a frozen template.
            bases = self.bases(q)
            candidates = dict(bases)
            for dim in sorted(bases):
                remaining = max(0, seconds-(time.monotonic()-start))
                candidate = self.search({"q":q,"d":dim}, remaining/(len(bases)-sorted(bases).index(dim)), rng)
                if len(candidate) > len(candidates[dim]): candidates[dim] = candidate
            sizes, choices = [1], [[]]
            for n in range(1,d+1):
                k = max((k for k in candidates if k<=n),key=lambda k:sizes[n-k]*len(candidates[k]))
                sizes.append(sizes[n-k]*len(candidates[k])); choices.append(choices[n-k]+[k])
            return {"factors":[{"words":candidates[k],"power":choices[d].count(k)} for k in sorted(set(choices[d]))]}
        while time.monotonic() - start < seconds:
            cur = list(best)
            drop = max(1, len(cur)//30)
            remove = set(rng.sample(range(len(cur)), min(drop, len(cur))))
            cur = [w for i, w in enumerate(cur) if i not in remove]
            masks = self._masks(cur, q, d)
            for _ in range(max(500, 20*len(best))):
                if time.monotonic() - start >= seconds or len(cur) >= self.MAX_WORDS:
                    break
                word = "".join(str(rng.randrange(q)) for _ in range(d))
                if not self._conflicts(word, masks, q, (1 << len(cur))-1):
                    bit = 1 << len(cur)
                    cur.append(word)
                    for i, c in enumerate(word):
                        masks[i][int(c)] |= bit
            if len(cur) > len(best):
                best = cur
        return best


@lru_cache(maxsize=6)
def _projective_code(k):
    """Evaluation on one representative of every point of PG(k-1,3)."""
    vectors = list(product(range(3), repeat=k))
    columns = [v for v in vectors[1:] if next(x for x in v if x) == 1]
    code = [tuple(sum(a*b for a,b in zip(v,c)) % 3 for c in columns) for v in vectors]
    return columns, code


@lru_cache(maxsize=6)
def _linear_constraints(k):
    """Translate a codeword triple to (0,u,v), then retain its separating column mask."""
    columns, code = _projective_code(k)
    constraints = set()
    for u, v in combinations(code[1:], 2):
        mask = sum(1 << i for i, (a,b) in enumerate(zip(u,v)) if a*b == 2)
        constraints.add(mask)
    return columns, code, tuple(sorted(constraints))


def _is_linear(words):
    """Rank of every submitted vector, then cardinality = 3^rank certifies a full subspace."""
    n = len(words[0]); basis = {}
    for word in words:
        row = list(map(int,word))
        for col in sorted(basis):
            a = row[col]
            if a: row = [(x-a*y)%3 for x,y in zip(row,basis[col])]
        pivot = next((i for i,x in enumerate(row) if x),None)
        if pivot is not None:
            a=row[pivot]; basis[pivot]=[(x*a)%3 for x in row]
            if 3**len(basis)>len(words): return False
    return len(words)==3**len(basis)


def _is_linear_second(words):
    """Independently build the additive span and compare its actual elements with the input."""
    universe={tuple(map(int,w)) for w in words}; span={(0,)*len(words[0])}
    if not span<=universe: return False
    for vector in sorted(universe):
        if vector in span: continue
        if len(span)*3>len(universe): return False
        span={tuple((a+t*b)%3 for a,b in zip(v,vector)) for v in span for t in (0,1,2)}
        if not span<=universe: return False
    return span==universe


class Trifference:
    name = "trifference"
    title = "Ternary-Trifference-Code"
    sense = "max"
    MAX_WORDS = 6561
    MAX_ROWS = 8

    def params(self, rng):
        return {"n": rng.choice([12, 18, 24]), "m": 1}

    def statement(self, p):
        statement = (f"Find as many distinct strings of length {p['n']} over digits 0,1,2 as possible. "
                f"For every THREE distinct strings x,y,z, at least {p['m']} coordinates i must satisfy "
                f"{{x_i,y_i,z_i}}={{0,1,2}}. Objective: number of strings. "
                f"At most {self.MAX_WORDS} strings are accepted.")

        if p.get("representation") == "certified":
            statement = statement.replace(f"At most {self.MAX_WORDS} strings are accepted.",
                f"Literal lists accept at most {self.MAX_WORDS} strings. Certified linear and Reed-Solomon "
                "concatenation forms can describe larger sets, whose cardinality is computed exactly.")
        return statement

    def compact_hint(self, p):
        from trifference_certificates import HINT
        return HINT if p.get("representation") == "certified" else None

    def verify(self, p, ans):
        n, m = p["n"], p["m"]
        if p.get("representation") == "certified" and isinstance(ans, dict):
            from trifference_certificates import verify
            return verify(p, ans, lambda ip, ia: self.verify(ip, self.expand(ip, ia)))
        if type(n) is not int or type(m) is not int or not 1 <= m <= n <= (1024 if p.get("representation") == "certified" else 128):
            return False, 0, "unsupported length or separation multiplicity"
        ok, msg = _words(ans, n, set("012"), self.MAX_WORDS)
        if not ok:
            return False, 0, msg
        masks = [tuple(sum(1 << j for j,c in enumerate(w) if c == a) for a in "012") for w in ans]
        if _is_linear(ans):
            nonzero = [v for v in masks if v[1] | v[2]]
            for i, (_, a1, a2) in enumerate(nonzero):
                for _, b1, b2 in nonzero[i+1:]:
                    if ((a1 & b2) | (a2 & b1)).bit_count() < m:
                        return False, 0, "linear span has a translated triple with too few separating coordinates"
            return True, len(ans), ""
        for i in range(len(ans)):
            a0,a1,a2 = masks[i]
            for j in range(i+1, len(ans)):
                b0,b1,b2 = masks[j]
                need = ((a1 & b2) | (a2 & b1), (a0 & b2) | (a2 & b0), (a0 & b1) | (a1 & b0))
                for k in range(j+1, len(ans)):
                    c0,c1,c2 = masks[k]
                    count = ((need[0] & c0) | (need[1] & c1) | (need[2] & c2)).bit_count()
                    if count < m:
                        return False, 0, f"strings {i},{j},{k} separate in only {count} positions"
        return True, len(ans), ""

    def expand(self, p, ans):
        if not isinstance(ans, dict) or set(ans) != {"linear"}:
            return ans
        rows = ans["linear"]
        ok, _ = _words(rows, p["n"], set("012"), self.MAX_ROWS)
        if not ok:
            raise ValueError("linear must contain 1..8 ternary generator rows")
        out = {"0" * p["n"]}
        for row in rows:
            out = {"".join(str((int(a) + t*int(b)) % 3) for a,b in zip(word,row))
                   for word in out for t in range(3)}
            if len(out) > self.MAX_WORDS:
                raise ValueError("linear code exceeds word limit")
        return sorted(out)

    def naive(self, p):
        if p.get("representation") == "certified":
            from trifference_scaling import reference_certificate
            return reference_certificate(p)
        n,m = p["n"],p["m"]
        best = [a*n for a in "012"]
        for k in range(2,6):
            length = (3**k-1)//2
            if length > n:
                continue
            _, code = _projective_code(k)
            repeats = n//length
            if repeats * 3**(k-2) >= m:
                best = ["".join(map(str, w))*repeats + "0"*(n-length*repeats) for w in code]
        path = Path(__file__).parent / "data/trifference_references.json"
        if path.exists():
            for entry in json.loads(path.read_text())["codes"]:
                if entry["n"] <= n and entry["m"] >= m and entry["size"] > len(best):
                    candidate = self.expand({"n":entry["n"]}, {"linear":entry["rows"]})
                    best = [w + "0"*(n-entry["n"]) for w in candidate]
        return best

    def objective(self, p, ans):
        return self.verify(p, ans)[1] if isinstance(ans, dict) else len(ans)

    def upper(self, p):
        # Classical finite perfect-3-hash bound 2(3/2)^n; valid for every m >= 1.
        return min(3**p["n"], (2*3**p["n"])//2**p["n"])

    def law(self, p, obj):
        return {"name": "trifference_rate", "value": math.log2(obj)/p["n"], "better": "higher",
                "lower": None, "upper": math.log2(self.upper(p))/p["n"], "note": "log2(M)/n"}

    def search(self, p, seconds, rng):
        if p.get("representation") == "certified":
            return self.naive(p)  # Exhaustive finite reference-pool/outer-parameter optimisation; no local-search claim.
        start = time.monotonic()
        best = self.naive(p)
        n,m = p["n"],p["m"]
        if len(best) >= 3**5:
            return best  # all dimensions supported by this puncturing search are exhausted
        while time.monotonic() - start < seconds:
            # Search for puncturings of a projective evaluation code; the candidate itself is fully verified.
            for k in range(3,6):
                if 3**k <= len(best) or time.monotonic() - start >= seconds:
                    continue
                columns, code, constraints = _linear_constraints(k)
                selected = (1 << len(columns))-1
                order = list(range(len(columns))); rng.shuffle(order)
                for i in order:
                    proposed = selected ^ (1 << i)
                    if all((c & proposed).bit_count() >= m for c in constraints):
                        selected = proposed
                    if selected.bit_count() <= n or time.monotonic() - start >= seconds:
                        break
                indices = [i for i in range(len(columns)) if selected >> i & 1]
                if len(indices) <= n:
                    candidate = ["".join(str(w[i]) for i in indices) + "0"*(n-len(indices)) for w in code]
                    if self.verify(p, candidate)[0]:
                        best = candidate
            if len(best) == 3**5:
                break
        return best


@lru_cache(maxsize=3)
def _norm_matrix(q):
    """Loop-free NG(q,3): vertices (x+y sqrt(nu),a), Norm(A+B)=ab over F_q."""
    nu = next(v for v in range(2,q) if pow(v,(q-1)//2,q) == q-1)
    vertices = list(product(range(q),range(q),range(1,q)))
    return tuple("".join("1" if i != j and ((x+u)**2 - nu*(y+v)**2-a*b) % q == 0 else "0"
                         for j,(u,v,b) in enumerate(vertices)) for i,(x,y,a) in enumerate(vertices))


def norm_graph_reference(n):
    """Best deterministic induced submatrix/padding of q=3,5,7 norm graphs; reference only."""
    best = ["0"*n for _ in range(n)]
    best_size = 0
    for q in (3,5,7):
        matrix = _norm_matrix(q)
        N = len(matrix)
        count = min(n,N)
        for indices in (list(range(count)), [i*N//count for i in range(count)]):
            ans = ["".join(matrix[i][j] for j in indices) + "0"*(n-count) for i in indices]
            ans += ["0"*n for _ in range(n-count)]
            size = sum(r.count("1") for r in ans)
            if size > best_size:
                best, best_size = ans, size
    return best


def shannon_second(p, ans):
    """Independent pairwise distance check (primary uses symbol-index bitsets)."""
    q,d = p["q"],p["d"]
    if type(q) is not int or type(d) is not int or q not in (5,7,9) or not 1<=d<=256:
        return False,0
    if isinstance(ans, dict):
        # Independently parse the grammar, dimensions and multiplicities.
        if list(ans) != ["factors"] or not isinstance(ans["factors"],list) or not 1<=len(ans["factors"])<=256:
            return False,0
        total, size, work = 0, 1, 0
        for factor in ans["factors"]:
            if not isinstance(factor,dict) or set(factor)-{"words","power"} or "words" not in factor:
                return False,0
            words, exponent = factor["words"],factor.get("power",1)
            if type(exponent) is not int or not 1<=exponent<=256 or not isinstance(words,list) or not words or not isinstance(words[0],str) or not words[0]:
                return False,0
            length=len(words[0]); total+=length*exponent; work+=len(words)
            if total>d or work>16384: return False,0
            valid,count=shannon_second({"q":q,"d":length},words)
            if not valid: return False,0
            size*=count**exponent
        return (True,size) if total==d else (False,0)
    ok,_ = _words(ans,d,set(map(str,range(q))),Shannon.MAX_WORDS)
    if not ok:
        return False,0
    for u,v in combinations(ans,2):
        if all(min(abs(int(a)-int(b)),q-abs(int(a)-int(b))) < 2 for a,b in zip(u,v)):
            return False,0
    return True,len(ans)


def trifference_second(p, ans):
    """A triple separates exactly at the intersection of its three pairwise difference masks."""
    if p.get("representation") == "certified" and isinstance(ans, dict):
        from trifference_certificates import verify_second
        return verify_second(p, ans, lambda ip, ia: trifference_second(ip, Trifference().expand(ip, ia)))
    ok,_ = _words(ans,p["n"],set("012"),Trifference.MAX_WORDS)
    if not ok:
        return False,0
    if type(p["n"]) is not int or type(p["m"]) is not int or not 1<=p["m"]<=p["n"]<=(1024 if p.get("representation")=="certified" else 128):
        return False,0
    if _is_linear_second(ans):
        # Directly compute the three pairwise-difference intersections after translation.
        codes = [(sum((c=="1")<<i for i,c in enumerate(w)),sum((c=="2")<<i for i,c in enumerate(w))) for w in ans if set(w)!={"0"}]
        for i,(a,b) in enumerate(codes):
            for c,d in codes[i+1:]:
                if ((a|b)&(c|d)&((a^c)|(b^d))).bit_count()<p["m"]:
                    return False,0
        return True,len(ans)
    diff = {}
    for i,j in combinations(range(len(ans)),2):
        diff[i,j] = sum(1 << c for c,(a,b) in enumerate(zip(ans[i],ans[j])) if a != b)
    for i,j,k in combinations(range(len(ans)),3):
        if (diff[i,j] & diff[i,k] & diff[j,k]).bit_count() < p["m"]:
            return False,0
    return True,len(ans)


def zarank_second(p, ans):
    """Column-first check; the primary verifier enumerates row intersections."""
    n = p["n"]
    if not isinstance(ans,list) or len(ans) != n or any(not isinstance(r,str) or len(r)!=n or set(r)-set("01") for r in ans):
        return False,0
    cols = [sum(1 << i for i in range(n) if ans[i][j] == "1") for j in range(n)]
    for a in range(n):
        candidates = [(b,cols[a] & cols[b]) for b in range(a+1,n) if (cols[a] & cols[b]).bit_count() >= 4]
        for j,(b,ab) in enumerate(candidates):
            for c,ac in candidates[j+1:]:
                abc = ab & ac
                if abc.bit_count() < 4:
                    continue
                if any((abc & cols[d]).bit_count() >= 4 for d in range(c+1,n)):
                    return False,0
    return True,sum(r.count("1") for r in ans)
