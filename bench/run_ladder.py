#!/usr/bin/env python3
"""Track A of the Endless Exam (the open-ceiling benchmark): the model must list the object itself.
No tools, no code, no verifier access.  The reply is parsed, verified by the
family's programmatic checker, and scored against a fixed-budget reference.

    python3 bench/run_ladder.py run --model naive   --seeds 2 --ref-time 3    # pipeline dry run
    python3 bench/run_ladder.py run --model search  --seeds 2 --ref-time 3    # should score 1.0
    python3 bench/run_ladder.py run --model garbage --seeds 2 --ref-time 3    # should score 0
    python3 bench/run_ladder.py run --provider deepseek --model deepseek-v4-flash --config think-low --seeds 3
    python3 bench/run_ladder.py summarize

Score = objective / reference (reference / objective where minimising);
infeasible answers score 0.  A score above 1 beat the reference search.
"""
import argparse
import glob
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "bench"))
from openceiling import FAMILIES, render, naive_answer, closed_gap, expand_answer, COMPACT, verify_with_timeout  # noqa: E402

# Track-A instance sizes: small enough that listing the object is the task, not the obstacle.
SIZE_TIER = os.environ.get("BENCH_TIER", "A1")   # A1: sized for 2026 models' reliable output; A2: beyond the tables
def distinct(options):
    """v1.2 instance draw (2026-09-14): seeds enumerate a fixed shuffled order of the parameter list without replacement,
    cycling only when the list is exhausted (seed 0..len-1 are all distinct).  The v1.1 families keep their original
    with-replacement draw so that the reported rows stay reproducible; repeats there are averaged at scoring time."""
    order = list(options); random.Random(f"order-{options!r}").shuffle(order)
    def draw(r):
        i = getattr(r, "seed_index", None)
        return dict(order[i % len(order)]) if i is not None else dict(order[r.randrange(len(order))])
    return draw



TIERS = {
  "A1": {
    "apfree":    lambda r: {"k": r.choice([3, 3, 4]), "n": r.randint(40, 120)},
    "sidon":     lambda r: {"n": r.randint(50, 200)},
    "code":      lambda r: {"n": r.randint(8, 11), "d": r.choice([3, 4, 5])},
    "capset":    lambda r: {"d": r.randint(3, 4)},
    "no3inline": lambda r: {"n": r.randint(6, 12)},
    "labs":      lambda r: {"N": r.randint(13, 30)},
    "heilbronn": lambda r: {"n": r.randint(5, 8)},
    "mono3ap":   lambda r: {"n": r.randint(20, 60)},
    "ramsey":    lambda r: (lambda st: {"s": st[0], "t": st[1], "n": r.randint(FAMILIES["ramsey"].KNOWN_R[st] - 1, FAMILIES["ramsey"].KNOWN_R[st])})(r.choice([(3, 3), (3, 4), (3, 5), (4, 4)])),
    "vdw":       lambda r: (lambda k: {"k": k, "N": r.randint(FAMILIES["vdw"].KNOWN_W[k] - 2, FAMILIES["vdw"].KNOWN_W[k] + 1)})(r.choice([3, 4])),
    "golomb":    lambda r: {"m": r.randint(5, 9)},
    "costas":    lambda r: {"n": r.randint(6, 12)},
    "hadamard":  lambda r: {"n": r.choice([4, 8, 12])},
    "apfree_sub":    lambda r: (lambda n: {"k": 3, "n": n, "A": sorted(r.sample(range(1, n + 1), n // 2))})(r.randint(60, 160)),
    "sidon_mod":     lambda r: (lambda m: {"m": m, "F": sorted(r.sample(range(m), m // 4))})(r.randint(80, 250)),
    "code_pool":     lambda r: (lambda n, d: {"n": n, "d": d, "pool": [format(w, f"0{n}b") for w in sorted(r.sample(range(1 << n), (1 << n) // 4))]})(r.randint(8, 10), r.choice([3, 4])),
    "golomb_forbid": lambda r: (lambda m: {"m": m, "F": sorted(r.sample(range(1, 4 * m * m), m * m // 2))})(r.randint(5, 8)),
    "costas_fixed":  lambda r: (lambda n: (lambda perm, idx: {"n": n, "fixed": {str(i): perm[i] for i in idx}})(r.sample(range(n), n), sorted(r.sample(range(n), max(2, n // 4)))))(r.randint(7, 11)),
    "vdw_fixed":     lambda r: (lambda k: (lambda N: {"k": k, "N": N, "fixed": {str(i + 1): r.choice("01") for i in sorted(r.sample(range(N), int(0.3 * N)))}})(r.randint(int(FAMILIES["vdw"].KNOWN_W[k] * 0.8), FAMILIES["vdw"].KNOWN_W[k] - 1)))(r.choice([3, 4])),
    "kissing":   lambda r: {"d": r.choice([6, 7])},
    "corners":   lambda r: {"n": r.randint(10, 24)},
    "unitdist":  lambda r: {"n": r.randint(20, 60)},
    "kissing_theta":   lambda r: {"d": r.choice([6, 7, 8]), "cos100": r.randint(20, 48)},
    "heilbronn_shape": lambda r: {"n": r.randint(8, 12), "T": FAMILIES["heilbronn_shape"]._triangle(r)},
    "sortnet":   lambda r: {"n": r.randint(9, 13)},
    "matmul":    lambda r: dict(zip(("n", "m", "p"), r.choice([(2, 2, 3), (2, 3, 3), (3, 3, 3), (2, 2, 4)]))),
    "boolnl":    lambda r: {"n": r.choice([7, 9])},
    "degdiam":   lambda r: dict(zip(("d", "k"), r.choice([(3, 3), (4, 2), (5, 2), (4, 3), (3, 4), (6, 2)]))),
    "lineq":     lambda r: dict(zip(("a", "b"), r.choice([(1, 2), (1, 3), (2, 3), (1, 4), (3, 4)])), n=r.randint(60, 160)),
    "kakeya":    lambda r: dict(zip(("q", "n"), r.choice([(5, 3), (7, 3)]))),
    "apfree_q":  lambda r: dict(zip(("q", "n"), r.choice([(5, 3), (7, 2), (5, 4)]))),
    "mols":      lambda r: {"n": r.choice([10, 12])},
    "schur":     lambda r: {"k": r.choice([3, 4])},
    "zarank":    lambda r: {"n": r.choice([12, 16])},
    "covering":  lambda r: dict(zip(("v", "k", "t"), r.choice([(13, 4, 2), (12, 6, 3), (10, 5, 3)]))),
  },
  "A2": {   # beyond the exact tables; objects still a few hundred to ~1,000 symbols
    "apfree":    lambda r: {"k": r.choice([3, 3, 4]), "n": r.randint(400, 1000)},
    "sidon":     lambda r: {"n": r.randint(800, 2500)},
    "code":      lambda r: (lambda n: {"n": n, "d": r.choice([6, 8])})(r.randint(17, 18)),   # A(17,6), A(18,6), A(17,8), A(18,8): only bounds known
    "capset":    lambda r: {"d": r.choice([7, 7, 8])},                                      # d=6 is exact (112); d=7: 236..291 open
    "no3inline": lambda r: {"n": r.randint(18, 36)},
    "labs":      lambda r: {"N": r.randint(60, 100)},
    "heilbronn": lambda r: {"n": r.randint(12, 20)},
    "mono3ap":   lambda r: {"n": r.randint(150, 350)},
    "ramsey":    lambda r: (lambda st, R: {"s": st[0], "t": st[1], "n": r.randint(R - 2, R)})(*(lambda st: (st, (FAMILIES["ramsey"].KNOWN_R.get(st) or FAMILIES["ramsey"].LOWER_R[st])))(r.choice([(3, 8), (3, 9), (4, 5), (5, 5)]))),
    "vdw":       lambda r: (lambda k: {"k": k, "N": r.randint(int(FAMILIES["vdw"].KNOWN_W[k] * 0.9), FAMILIES["vdw"].KNOWN_W[k] - 1)})(r.choice([5, 6])),
    "golomb":    lambda r: {"m": r.randint(29, 40)},     # optimal rulers are tabulated through m=28
    "costas":    lambda r: {"n": r.randint(20, 33)},
    "hadamard":  lambda r: {"n": r.choice([20, 28, 36, 44])},
    "apfree_sub":    lambda r: (lambda n: {"k": 3, "n": n, "A": sorted(r.sample(range(1, n + 1), n // 2))})(r.randint(300, 800)),
    "sidon_mod":     lambda r: (lambda m: {"m": m, "F": sorted(r.sample(range(m), m // 4))})(r.randint(500, 1500)),
    "code_pool":     lambda r: (lambda n, d: {"n": n, "d": d, "pool": [format(w, f"0{n}b") for w in sorted(r.sample(range(1 << n), (1 << n) // 4))]})(r.randint(11, 12), r.choice([4, 5])),
    "golomb_forbid": lambda r: (lambda m: {"m": m, "F": sorted(r.sample(range(1, 4 * m * m), m * m // 2))})(r.randint(9, 14)),
    "costas_fixed":  lambda r: (lambda n: (lambda perm, idx: {"n": n, "fixed": {str(i): perm[i] for i in idx}})(r.sample(range(n), n), sorted(r.sample(range(n), max(2, n // 4)))))(r.randint(14, 22)),
    "vdw_fixed":     lambda r: (lambda k: (lambda N: {"k": k, "N": N, "fixed": {str(i + 1): r.choice("01") for i in sorted(r.sample(range(N), int(0.3 * N)))}})(r.randint(int(FAMILIES["vdw"].KNOWN_W[k] * 0.85), FAMILIES["vdw"].KNOWN_W[k] - 1)))(r.choice([5, 6])),
    "kissing":   lambda r: {"d": r.choice([9, 10, 11, 12])},        # 8 and 24 are exact; 9-12 open (306-363, 510-553, 592-868, 840-1355)
    "corners":   lambda r: {"n": r.randint(40, 80)},
    "unitdist":  lambda r: {"n": r.randint(100, 300)},
    "kissing_theta":   lambda r: {"d": r.choice([9, 10, 11, 12]), "cos100": r.randint(20, 48)},
    "heilbronn_shape": lambda r: {"n": r.randint(12, 20), "T": FAMILIES["heilbronn_shape"]._triangle(r)},
    "sortnet":   lambda r: {"n": r.randint(14, 20)},                                          # sizes open from n = 13
    "matmul":    lambda r: dict(zip(("n", "m", "p"), r.choice([(3, 3, 4), (3, 4, 4), (4, 4, 4), (3, 3, 5), (4, 4, 5), (5, 5, 5)]))),
    "boolnl":    lambda r: {"n": r.choice([11, 13])},
    "degdiam":   lambda r: dict(zip(("d", "k"), r.choice([(3, 5), (3, 6), (4, 4), (5, 3), (6, 3), (7, 3), (5, 4), (8, 2), (10, 2)]))),
    "lineq":     lambda r: dict(zip(("a", "b"), r.choice([(1, 2), (1, 3), (2, 3), (1, 4), (3, 4), (2, 5), (3, 5)])), n=r.randint(500, 1500)),
    "kakeya":    lambda r: dict(zip(("q", "n"), r.choice([(7, 3), (11, 3), (5, 4)]))),
    "apfree_q":  lambda r: dict(zip(("q", "n"), r.choice([(5, 4), (5, 5), (7, 3), (7, 4)]))),
    "mols":      lambda r: {"n": r.choice([10, 12, 14, 15])},
    "schur":     lambda r: {"k": r.choice([5, 6])},
    "zarank":    lambda r: {"n": r.choice([30, 40])},
    "covering":  lambda r: dict(zip(("v", "k", "t"), r.choice([(16, 6, 3), (20, 6, 3), (15, 7, 4)]))),
  },
}
TIERS["A3"] = {   # beyond the reach of explicit listing at the literature size unless a compact form is used;
                  # ln(bound/naive) >= 1.4 everywhere a proven bound exists (survey 2026-09-13)
    "apfree":    lambda r: {"k": 3, "n": r.randint(5000, 20000)},
    "capset":    lambda r: {"d": r.choice([9, 10, 11])},
    "labs":      lambda r: {"N": r.randint(150, 400)},
    "heilbronn": lambda r: {"n": r.randint(25, 50)},
    "kissing":   lambda r: {"d": r.choice([13, 14, 15])},
    "corners":   lambda r: {"n": r.randint(100, 200)},
    "unitdist":  lambda r: {"n": r.randint(500, 2000)},
    "kissing_theta":   lambda r: {"d": r.choice([12, 13, 14]), "cos100": r.randint(20, 48)},
    "heilbronn_shape": lambda r: {"n": r.randint(25, 40), "T": FAMILIES["heilbronn_shape"]._triangle(r)},
    "matmul":    lambda r: dict(zip(("n", "m", "p"), [(4, 4, 5), (4, 5, 5), (5, 5, 5)][r.randrange(3)])),
    "degdiam":   lambda r: dict(zip(("d", "k"), [(3, 7), (4, 5), (5, 4), (6, 3), (3, 6), (4, 4), (7, 3)][r.randrange(7)])),
    "sortnet":   lambda r: {"n": [20, 22][r.randrange(2)]},    # bounded control: 2^n verification, gap ~0.3
    "lineq":     lambda r: dict(zip(("a", "b"), [(1, 2), (2, 3), (1, 4), (3, 4), (2, 5), (3, 5), (1, 3)][r.randrange(7)]), n=r.randint(5000, 20000)),
    "kakeya":    lambda r: dict(zip(("q", "n"), [(13, 3), (7, 4), (11, 4)][r.randrange(3)])),
    "apfree_q":  lambda r: dict(zip(("q", "n"), [(5, 5), (5, 6), (7, 4)][r.randrange(3)])),
    "mols":      lambda r: {"n": [10, 12, 14, 15, 18, 20][r.randrange(6)]},
    "schur":     distinct([{"k": 6}, {"k": 7}, {"k": 8}]),
    "zarank":    distinct([{"n": 60}, {"n": 80}, {"n": 100}]),
    "covering":  distinct([{"v": 24, "k": 6, "t": 3}, {"v": 30, "k": 6, "t": 3}, {"v": 18, "k": 7, "t": 4}, {"v": 22, "k": 7, "t": 4}]),
}
# Scale ladder (2026-09-13): four fixed sizes per representative family, from inside the tables (L1) to beyond A3 (L4);
# seeds are repeats (the instance is fixed by the size).  Used for the size-quality curve at a fixed 128k budget.
for _lv, (_d, _k, _n) in {"L1": (6, 8, 300), "L2": (8, 10, 2000), "L3": (10, 13, 8000), "L4": (12, 16, 32000)}.items():
    TIERS[_lv] = {"capset": (lambda d: (lambda r: {"d": d}))(_d), "kissing": (lambda d: (lambda r: {"d": d}))(_k),
                  "apfree": (lambda n: (lambda r: {"k": 3, "n": n}))(_n),
                  "degdiam": (lambda k: (lambda r: {"d": 3, "k": k}))({"L1": 4, "L2": 6, "L3": 8, "L4": 10}[_lv]),
                  "schur": (lambda k: (lambda r: {"k": k}))({"L1": 5, "L2": 6, "L3": 7, "L4": 8}[_lv]),
                  "zarank": (lambda n: (lambda r: {"n": n}))({"L1": 25, "L2": 50, "L3": 100, "L4": 200}[_lv]),
                  "covering": (lambda v: (lambda r: {"v": v, "k": 6, "t": 3}))({"L1": 12, "L2": 16, "L3": 24, "L4": 30}[_lv])}
# Second degree-diameter series (2026-09-14): degree 4, diameters 4-7 (Comellas: 104, 364, 745, 1320) -- the same bottleneck
# under a different parameter structure; single attempt per size.
for _lv, _k in {"M1": 4, "M2": 5, "M3": 6, "M4": 7}.items():
    TIERS[_lv] = {"degdiam": (lambda k: (lambda r: {"d": 4, "k": k}))(_k)}
# C1: predeclared exploratory instances, outside every version-1 headline tier.
CANDIDATE_INSTANCES = {
    "shannon": [{"q": 7, "d": d} for d in (3,4,5,6)],
    "trifference": [{"n": 12, "m": 1}, {"n": 18, "m": 1}, {"n": 24, "m": 1}, {"n": 24, "m": 3}],
    "zarank": [{"n": n} for n in (18,50,100,294)],
}
def _candidate_draw(options):
    def draw(r):
        i = getattr(r, "seed_index", 0)
        if not 0 <= i < len(options):
            raise ValueError("code-family seeds must be 0..3; no implicit repeats")
        return dict(options[i])
    return draw
TIERS["C1"] = {name: _candidate_draw(options) for name, options in CANDIDATE_INSTANCES.items()}
# Version-1 code-family extension: four distinct A3 instances, frozen before calls.
CODE_INSTANCES = {
    "shannon": [{"q":7,"d":24},{"q":7,"d":40},{"q":9,"d":48},{"q":9,"d":64}],
    "trifference": [{"n":30,"m":1},{"n":36,"m":2},{"n":42,"m":3},{"n":56,"m":1}],
}
for _name, _options in CODE_INSTANCES.items():
    TIERS["A3"][_name] = _candidate_draw(_options)
TIERS["A1"].update({"shannon":distinct([{"q":7,"d":3},{"q":7,"d":4},{"q":9,"d":3}]),
                    "trifference":distinct([{"n":9,"m":1},{"n":12,"m":1},{"n":16,"m":1}])})
TIERS["A2"].update({"shannon":distinct([{"q":7,"d":8},{"q":7,"d":12},{"q":9,"d":12}]),
                    "trifference":distinct([{"n":18,"m":1},{"n":24,"m":1},{"n":30,"m":2}])})
# Trifference certificate scale calibration: fresh mathematical lengths, one call per level.
for _tier, _length in {"T1":64, "T2":96, "T3":144, "T4":192}.items():
    TIERS[_tier] = {"trifference": (lambda n: (lambda r: {"n":n,"m":1,"representation":"certified"}))(_length)}
A_RANGES = TIERS[SIZE_TIER]
FORMAT_HINT = {
    "shannon": "a JSON array of digit strings, each of the required length",
    "trifference": "a JSON array of strings over 0,1,2, each of the required length",
    "apfree": "a JSON array of integers in increasing order",
    "sidon": "a JSON array of integers in increasing order",
    "code": "a JSON array of strings of 0/1, all of the stated length",
    "capset": "a JSON array of strings of digits 0/1/2, all of the stated length",
    "no3inline": "a JSON array of [x, y] integer pairs",
    "heilbronn": "a JSON array of [x, y] integer pairs",
    "labs": "a JSON array of +1 / -1 values of the stated length",
    "mono3ap": "a single JSON string of 0/1 characters of the stated length",
    "ramsey": "a single JSON string of 0/1 characters, one per edge in the stated order",
    "vdw": "a single JSON string of 0/1 characters of the stated length",
    "golomb": "a JSON array of integers in increasing order, starting with 0",
    "costas": "a JSON array giving the permutation",
    "hadamard": "a JSON array of strings over +/-, one per row",
    "apfree_sub": "a JSON array of integers in increasing order (all taken from A)",
    "sidon_mod": "a JSON array of integers in increasing order (residues mod m, none in F)",
    "code_pool": "a JSON array of strings of 0/1, all taken from the pool P",
    "golomb_forbid": "a JSON array of integers in increasing order, starting with 0",
    "costas_fixed": "a JSON array giving the full permutation (fixed values respected)",
    "vdw_fixed": "a single JSON string of 0/1 characters of the stated length (fixed colours respected)",
    "kissing": "a JSON array of integer vectors, each a JSON array of d integers",
    "corners": "a JSON array of [x, y] integer pairs",
    "unitdist": "a JSON array of exactly n [x, y] integer pairs",
    "kissing_theta": "a JSON array of integer vectors, each a JSON array of d integers",
    "heilbronn_shape": "a JSON array of exactly n [x, y] integer pairs inside the triangle",
    "sortnet": "a JSON array of [i, j] comparator pairs in order (0 <= i < j < n)",
    "matmul": "a JSON array of r products, each [u, v, w] with u, v, w JSON arrays of integers of lengths n*m, m*p, n*p",
    "boolnl": "a JSON array of monomials (each a JSON array of variable indices), i.e. the algebraic normal form; a 0/1 truth-table string of length 2^n is also accepted",
    "degdiam": "a JSON array of [u, v] integer pairs (edges, u < v)",
    "lineq": "a JSON array of integers in increasing order",
    "kakeya": "a JSON array of vectors, each a JSON array of n integers in 0..q-1",
    "apfree_q": "a JSON array of strings of n digits in 0..q-1",
    "mols": "a JSON array of Latin squares, each a list of n rows of n integers in 0..n-1",
    "schur": "a JSON array of N integers in 0..k-1 (the colours of 1..N in order)",
    "zarank": "a JSON array of n strings of n characters '0'/'1' (the rows)",
    "covering": "a JSON array of blocks, each a list of k distinct integers in 0..v-1",
}
MAX_TOKENS = {"nothink": 6000, "plain": 6000, "think-low": 16000, "think-high": 24000, "think-max": 48000}
# Qwen3.8 via vLLM: thinking is controlled through chat_template_kwargs; sampling per the model card
# (thinking: T=1.0 top_p=0.95 top_k=20; non-thinking: T=0.7 top_p=0.8 top_k=20 presence=1.5).
QWEN_CONFIGS = {
    "nothink":    {"chat_template_kwargs": {"enable_thinking": False}, "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5},
    "plain":      {"chat_template_kwargs": {"enable_thinking": False}, "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5},
    "think-low":  {"chat_template_kwargs": {"reasoning_effort": "low"},    "temperature": 1.0, "top_p": 0.95, "top_k": 20},
    # sensitivity variant: official low effort but T=0.6 -- probes showed the mid-think <|im_end|> bail-out is stochastic
    "think-low-t06": {"chat_template_kwargs": {"reasoning_effort": "low"}, "temperature": 0.6, "top_p": 0.95, "top_k": 20},
    "think-med":  {"chat_template_kwargs": {"reasoning_effort": "medium"}, "temperature": 1.0, "top_p": 0.95, "top_k": 20},
    "think-high": {"chat_template_kwargs": {"reasoning_effort": "xhigh"},  "temperature": 1.0, "top_p": 0.95, "top_k": 20},
    "think-max":  {"chat_template_kwargs": {"reasoning_effort": "xhigh"},  "temperature": 1.0, "top_p": 0.95, "top_k": 20},
}
# Gemini 3.x Flash via the OpenAI-compatible layer: reasoning_effort maps to thinking_level; thoughts are
# returned only when include_thoughts is requested through extra_body.  Output is capped at 65,536 tokens.
GEMINI_CONFIGS = {
    # Gemini 3.8 Flash cannot switch thinking off: thinking_budget=0 still spends ~2k thinking tokens, and
    # thinking_level=minimal is rejected.  "nothink" therefore means the smallest available budget.
    "nothink":    {"thinking_budget": 0},
    "plain":      {"thinking_budget": 0},
    "think-low":  {"thinking_level": "low"},
    "think-med":  {"thinking_level": "medium"},
    "think-high": {"thinking_level": "high"},
    "think-max":  {"thinking_level": "high"},
    "think-low-t06": {"thinking_level": "low"},
}
GEMINI_MAX_OUTPUT = 16384      # 32k+ reservations are refused with 503 'high demand' on the free tier
# Qwen3.5 via vLLM: only enable_thinking; model-card sampling (thinking/general: T=1.0 top_p=0.95 top_k=20
# presence=1.5; non-thinking/general: T=0.7 top_p=0.8 top_k=20 presence=1.5).  All think-* map to the one mode.
QWEN35_CONFIGS = {
    "nothink":    {"chat_template_kwargs": {"enable_thinking": False}, "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5},
    "plain":      {"chat_template_kwargs": {"enable_thinking": False}, "temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5},
    "think-low":  {"chat_template_kwargs": {"enable_thinking": True},  "temperature": 1.0, "top_p": 0.95, "top_k": 20, "presence_penalty": 1.5},
    "think-med":  {"chat_template_kwargs": {"enable_thinking": True},  "temperature": 1.0, "top_p": 0.95, "top_k": 20, "presence_penalty": 1.5},
    "think-high": {"chat_template_kwargs": {"enable_thinking": True},  "temperature": 1.0, "top_p": 0.95, "top_k": 20, "presence_penalty": 1.5},
    "think-max":  {"chat_template_kwargs": {"enable_thinking": True},  "temperature": 1.0, "top_p": 0.95, "top_k": 20, "presence_penalty": 1.5},
    "think-low-t06": {"chat_template_kwargs": {"enable_thinking": True}, "temperature": 0.6, "top_p": 0.95, "top_k": 20},
}
# OpenRouter: unified `reasoning` object; effort levels map per provider; reasoning text comes back in
# message.reasoning.  Models without a thinking switch ignore the field.
OPENROUTER_CONFIGS = {
    "nothink":    {"reasoning": {"enabled": False}},
    "plain":      {"reasoning": {"enabled": False}},
    "think-low":  {"reasoning": {"effort": "low"}},
    "think-med":  {"reasoning": {"effort": "medium"}},
    "think-high": {"reasoning": {"effort": "high"}},
    "think-max":  {"reasoning": {"effort": "high"}},
    "think-low-t06": {"reasoning": {"effort": "low"}, "temperature": 0.6},
}
CONFIGS = {
    "nothink":    {"thinking": {"type": "disabled"}},
    "think-low":  {"thinking": {"type": "enabled"}, "reasoning_effort": "low"},
    "think-high": {"thinking": {"type": "enabled"}, "reasoning_effort": "high"},
    "think-max":  {"thinking": {"type": "enabled"}, "reasoning_effort": "max"},
    "think-med":  {"thinking": {"type": "enabled"}, "reasoning_effort": "high"},   # DeepSeek has no medium; alias
    "think-low-t06": {"thinking": {"type": "enabled"}, "reasoning_effort": "low"},  # (DeepSeek ignores temperature in thinking mode)
    "plain":      {},                       # for endpoints without a thinking switch
}
SYSTEM = ("You are solving an open-ended mathematical construction problem. The answer is checked "
          "mechanically. Reply with a single JSON object of the form {\"answer\": ...} and nothing else: "
          "no explanation, no reasoning, no code in the reply.")


def instance_a(family, seed):
    from result_selection import parameters_for
    fam = FAMILIES[family]
    r = random.Random(f"{SIZE_TIER}-{family}-{seed}"); r.seed_index = seed
    p = A_RANGES[family](r)
    p = parameters_for(SIZE_TIER, family, seed, p)
    return fam, p


PROTOCOL = "p1"        # p1: the original prompt.  p2 (2026-09-12): the budget is stated and the model is told to commit.
BUDGET_RULE = ("\n\nBudget rule: your reasoning is cut off at about {budget_k}k tokens and an unfinished reply scores zero. "
               "Reserve room for the answer: stop searching well before the limit and output the best VALID object you "
               "have at that point. A valid but improvable answer is far better than no answer.")


def prompt_for(family, fam, p, protocol=None, budget=None):
    answer_format = FORMAT_HINT[family]
    if family == "kissing" and p.get("representation") == "quadratic":
        answer_format = "an integer-vector list or the exact quadratic_vectors object described above"
    s = (f"{render(fam, p)}\n\nOutput format: a JSON object {{\"answer\": X}} where X is {answer_format}.\n"
         "An answer that violates the stated property, is malformed, contains duplicates, or is out of "
         "range scores zero. Among valid answers, a better objective scores higher. Give one answer.")
    if (protocol or PROTOCOL) == "p2":
        s += BUDGET_RULE.format(budget_k=(budget or 128000) // 1000)
    if (SIZE_TIER in ("A3", "C1") or SIZE_TIER.startswith("L") or family in ("shannon", "trifference")) and family in COMPACT:
        hint = getattr(fam, "compact_hint", lambda _: None)(p) or COMPACT[family]
        s += "\n" + hint
    return s


def reference(family, seed, budget):
    """Naive, search (fixed budget, fixed rng) and bound for an instance; cached on disk."""
    path = os.path.join(ROOT, "bench", "refs", f"{SIZE_TIER}-{family}-{seed}-t{int(budget)}.json")
    if os.path.exists(path):
        return json.load(open(path))
    fam, p = instance_a(family, seed)
    nv = fam.objective(p, naive_answer(fam, p))
    ans = fam.search(p, budget, random.Random(0))
    ok, sv, msg = fam.verify(p, ans)
    assert ok, msg
    ref = {"params": p, "naive": nv, "search": sv, "bound": fam.upper(p), "sense": fam.sense,
           "search_answer": ans, "budget_s": budget}
    json.dump(ref, open(path, "w"))
    return ref


def _unwrap(obj):
    return obj["answer"] if isinstance(obj, dict) and "answer" in obj else obj


def extract_json(text):
    blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    for c in [b.strip() for b in blocks[::-1]] + [text.strip()]:
        try:
            return _unwrap(json.loads(c))
        except (json.JSONDecodeError, TypeError):
            pass
        m = re.search(r"(\{.*\})", c, re.S)
        if m:
            try:
                return _unwrap(json.loads(m.group(1)))
            except json.JSONDecodeError:
                pass
        m = re.search(r"(\[.*\])", c, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m = re.search(r'("[01]{8,}")', c)
        if m:
            return json.loads(m.group(1))
    return None


class QuotaExhausted(Exception):
    pass


class HTTPFailure(Exception):
    pass


def call_model(provider, model, config, user, max_tokens, timeout, continue_slices=0):
    """One chat call.  With continue_slices > 0 (DeepSeek only) a reply cut off inside its reasoning is resumed
    through the beta chat-prefix-completion endpoint: the partial reasoning_content is sent back as an assistant
    prefix and the model keeps thinking from where it stopped (the same mechanism as Claude Code's thinking-block
    resumption).  Up to continue_slices extra slices of max_tokens each; usage is summed and 'slices' recorded."""
    reply = _call_once(provider, model, config, user, max_tokens, timeout)
    slices = 1
    while (continue_slices and slices <= continue_slices and provider == "deepseek"
           and reply["finish_reason"] == "length" and not (reply["content"] or "").strip() and reply["reasoning"]):
        more = _call_once(provider, model, config, user, max_tokens, timeout, resume_reasoning=reply["reasoning"])
        slices += 1
        u1, u2 = reply["usage"] or {}, more["usage"] or {}
        usage = dict(u2)
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[k] = (u1.get(k) or 0) + (u2.get(k) or 0)
        d1, d2 = u1.get("completion_tokens_details") or {}, u2.get("completion_tokens_details") or {}
        if d1 or d2:
            usage["completion_tokens_details"] = {"reasoning_tokens": (d1.get("reasoning_tokens") or 0) + (d2.get("reasoning_tokens") or 0)}
        reply = {"content": more["content"], "reasoning": (reply["reasoning"] or "") + (more["reasoning"] or ""),
                 "usage": usage, "system_fingerprint": more["system_fingerprint"], "response_model": more["response_model"],
                 "latency_s": round(reply["latency_s"] + more["latency_s"], 2), "finish_reason": more["finish_reason"]}
    if reply["usage"] is not None:
        reply["usage"] = dict(reply["usage"], slices=slices)
    return reply


def _call_once(provider, model, config, user, max_tokens, timeout, resume_reasoning=None):
    try:
        from providers import PROVIDERS, api_key           # standalone repo: bench/providers.py
    except ImportError:
        from gen.generate_pool import PROVIDERS, api_key   # noqa: E402  (key never enters a record)
    p = PROVIDERS[provider]
    body = {"model": model, "max_tokens": max_tokens or MAX_TOKENS.get(config, 8000),
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
    if provider == "qwen_local":
        body.update(QWEN_CONFIGS[config])
    elif provider == "qwen35_local":
        body.update(QWEN35_CONFIGS[config])
    elif provider == "openrouter":
        body.update(OPENROUTER_CONFIGS[config])
    elif provider == "gemini":
        tc = dict(GEMINI_CONFIGS[config], include_thoughts=True)
        body["extra_body"] = {"google": {"thinking_config": tc}}   # literal extra_body key, per the compat layer
        body["max_tokens"] = min(body["max_tokens"], GEMINI_MAX_OUTPUT)
        if config == "think-low-t06":
            body["temperature"] = 0.6
    else:
        body.update(CONFIGS[config])
        if config in ("nothink", "plain"):
            body["temperature"] = 0
    headers = {"Authorization": f"Bearer {api_key(provider)}", "Content-Type": "application/json"}
    headers.update(p.get("headers") or {})
    url = p["url"]
    if resume_reasoning is not None:                       # DeepSeek beta: continue the assistant's reasoning
        url = url.replace("api.deepseek.com/", "api.deepseek.com/beta/")
        body["messages"].append({"role": "assistant", "reasoning_content": resume_reasoning, "content": "", "prefix": True})
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    t0 = time.time()
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                r = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            if e.code == 400 and resume_reasoning is not None and "response_format" in body:
                body.pop("response_format")                 # the beta endpoint may not accept it with a prefix
                req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
                continue
            max_retries = 2 if provider == "gemini" else 5
            if e.code in (500, 502, 503) and attempt < max_retries:
                wait = (60, 180, 300, 300, 300)[attempt]
                print(f"    HTTP {e.code}; retry in {wait}s", flush=True)
                time.sleep(wait)
                continue
            if e.code == 429 and provider != "gemini" and attempt < max_retries:
                wait = min(300, 20 * (2 ** attempt))
                print(f"    HTTP 429; retry in {wait}s", flush=True)
                time.sleep(wait)
                continue
            if e.code == 429:
                raise QuotaExhausted(e.read().decode()[:300])
            raise HTTPFailure(f"HTTP {e.code}: {e.read().decode()[:300]}")
    msg = r["choices"][0]["message"]
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or msg.get("thoughts")
    usage = r.get("usage")
    if provider == "gemini":
        thoughts = re.findall(r"<thought>(.*?)</thought>", content, re.S)
        if thoughts:
            reasoning = "\n".join(thoughts)
            content = re.sub(r"<thought>.*?</thought>", "", content, flags=re.S).strip()
        if usage and "total_tokens" in usage:      # thinking tokens are only visible as total - prompt - completion
            think = usage["total_tokens"] - usage.get("prompt_tokens", 0) - usage.get("completion_tokens", 0)
            usage = dict(usage, completion_tokens_details={"reasoning_tokens": max(0, think), "note": "derived"})
    return {"content": content, "reasoning": reasoning,
            "usage": usage, "system_fingerprint": r.get("system_fingerprint"),
            "response_model": r.get("model"), "latency_s": round(time.time() - t0, 2),
            "finish_reason": r["choices"][0].get("finish_reason")}


def pseudo_model(name, family, fam, p, ref):
    """Offline stand-ins that exercise the pipeline end to end."""
    if name == "naive":
        ans = naive_answer(fam, p)
    elif name == "search":
        ans = ref["search_answer"]
    elif name == "garbage":
        ans = {"not": "an answer"}
    else:
        raise ValueError(name)
    return {"content": json.dumps({"answer": ans}), "reasoning": None, "usage": None,
            "system_fingerprint": None, "response_model": name, "latency_s": 0, "finish_reason": "stop"}


def score(fam, ref, feasible, obj):
    """Three views of one number, all anchored on frozen per-instance references.

    gain      -- position in the known band: 0 at the naive construction, 1 at the
                 fixed-budget search reference, >1 beyond it (the headline; infeasible = 0,
                 below-naive clipped to 0).
    log_ratio -- ln(obj / reference), multiplicative distance from the reference,
                 additive across instances, uncapped.
    vs_bound  -- obj / bound where a computable bound exists; an absolute anchor that
                 never moves, loose by an unknown factor.
    """
    if not feasible:
        return {"gain": 0.0, "log_ratio": None, "vs_bound": None}
    nv, r, b = ref["naive"], ref["search"], ref["bound"]
    if fam.sense == "max":
        band = r - nv
        gain = (obj - nv) / band if band > 0 else (1.0 if obj >= r else 0.0)
        lr = math.log(obj / r) if obj > 0 and r > 0 else None
        vb = obj / b if b else None
    else:
        band = nv - r
        gain = (nv - obj) / band if band > 0 else (1.0 if obj <= r else 0.0)
        lr = math.log(r / obj) if obj > 0 and r > 0 else None
        vb = b / obj if (b and obj) else None
    return {"gain": max(0.0, gain), "log_ratio": lr, "vs_bound": vb}


def cmd_run(a):
    global SIZE_TIER, A_RANGES
    if a.tier:
        SIZE_TIER = a.tier; A_RANGES = TIERS[a.tier]
    if not a.families:
        a.families = list(A_RANGES)
    os.makedirs(os.path.join(ROOT, "bench", "results"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "bench", "refs"), exist_ok=True)
    label = f"{a.config}@{a.tag}" if a.tag else a.config
    if a.continue_slices:
        label = f"{label}+cont"
    if a.protocol != "p1":
        label = f"{label}.{a.protocol}"
    if SIZE_TIER != "A1":
        label = f"{label}#{SIZE_TIER}"
    out = os.path.join(ROOT, "bench", "results", f"{a.model.replace('/', '_')}-{label}.jsonl")
    done = set()
    if os.path.exists(out):
        for line in open(out):
            r = json.loads(line)
            done.add((r["family"], r["seed"]))
    fh = open(out, "a")
    def already_done(family, seed):
        if not os.path.exists(out):
            return False
        for line in open(out):
            r = json.loads(line)
            if r["family"] == family and r["seed"] == seed:
                return True
        return False
    seeds = a.seed_list if a.seed_list else list(range(a.seeds))
    calls = 0
    for family in a.families:
        fam = FAMILIES[family]
        for seed in seeds:
            if (family, seed) in done or already_done(family, seed):
                continue
            if a.max_calls and calls >= a.max_calls:
                print(f"reached --max-calls {a.max_calls}; stopping for now", flush=True)
                fh.close()
                return
            calls += 1
            if a.min_interval and calls > 1:
                time.sleep(a.min_interval)
            fam, p = instance_a(family, seed)
            ref = reference(family, seed, a.ref_time)
            user = prompt_for(family, fam, p, a.protocol, a.max_tokens or MAX_TOKENS.get(a.config))
            try:
                if a.model in ("naive", "search", "garbage"):
                    reply = pseudo_model(a.model, family, fam, p, ref)
                else:
                    reply = call_model(a.provider, a.model, a.config, user, a.max_tokens, a.timeout, a.continue_slices)
                err = None
            except QuotaExhausted as e:
                print(f"quota exhausted ({str(e)[:120]}); stopping this run", flush=True)
                fh.close()
                return
            except (HTTPFailure, urllib.error.URLError, TimeoutError, OSError) as e:
                # transport-level failure: log it, do not persist a row, so the instance is retried next run
                print(f"{a.model:20s} {label:14s} {family:10s} seed={seed} TRANSPORT ERROR {str(e)[:160]}", flush=True)
                continue
            except Exception as e:                                   # noqa: BLE001
                reply, err = {"content": "", "reasoning": None, "usage": None, "system_fingerprint": None,
                              "response_model": None, "latency_s": None, "finish_reason": None}, repr(e)[:200]
            ans = extract_json(reply["content"]) if reply["content"] else None
            feasible, obj, msg = verify_with_timeout(fam, p, ans)
            if reply.get("finish_reason") == "length":            # strict protocol: a reply cut off at the budget scores 0
                feasible, obj, msg = False, 0, (msg + "; " if msg else "") + "cut off at the output budget: scored 0"
            rec = {"track": "A", "tier": SIZE_TIER, "family": family, "seed": seed, "params": p, "provider": a.provider,
                   "model": a.model, "config": label, "base_config": a.config, "max_tokens": a.max_tokens or MAX_TOKENS.get(a.config),
                   "feasible": feasible, "objective": obj,
                   **score(fam, ref, feasible, obj), "naive": ref["naive"], "reference": ref["search"],
                   "beats_reference": bool(feasible and ((obj > ref["search"]) if fam.sense == "max" else (obj < ref["search"]))),
                   "bound": ref["bound"], "sense": fam.sense, "verify_msg": msg, "error": err,
                   "law": (fam.law(p, obj) if feasible else None),
                   "answer_len": (len(ans) if isinstance(ans, (list, str)) else None),
                   "usage": reply["usage"], "system_fingerprint": reply["system_fingerprint"],
                   "response_model": reply["response_model"], "latency_s": reply["latency_s"],
                   "finish_reason": reply["finish_reason"], "reasoning_chars": len(reply["reasoning"] or ""),
                   "content_chars": len(reply["content"]), "request_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            if a.keep_text:
                rec["content"] = reply["content"]
                rec["reasoning"] = reply["reasoning"]
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(f"{a.model:20s} {label:14s} {family:10s} seed={seed} feasible={feasible!s:5s} "
                  f"obj={obj!s:>8s} ref={ref['search']!s:>8s} gain={rec['gain']:.2f} {msg or err or ''}", flush=True)
    fh.close()


COMMIT_SUFFIX = ("\n\nYour thinking time is over. Below are your own notes so far (they may be incomplete). "
                 "Using them, commit NOW to the best valid answer you can. Reply with the JSON object only.\n\n"
                 "<notes>\n{notes}\n</notes>")


def cmd_commit(a):
    """Second leg of the chess clock: for every record in the given results file that ran out of
    thinking budget without an answer, ask for the answer with thinking disabled and the notes in context."""
    src = os.path.join(ROOT, "bench", "results", a.file)
    rows = [json.loads(l) for l in open(src)]
    label = rows[0]["config"] + "+commit"
    out = os.path.join(ROOT, "bench", "results", f"{a.model.replace('/', '_')}-{label}.jsonl")
    done = set()
    if os.path.exists(out):
        done = {(r["family"], r["seed"]) for r in map(json.loads, open(out))}
    fh = open(out, "a")
    for r in rows:
        if (r["family"], r["seed"]) in done:
            continue
        family, seed = r["family"], r["seed"]
        fam, p = instance_a(family, seed)
        ref = reference(family, seed, a.ref_time)
        stalled = (r["finish_reason"] == "length" and not r["feasible"])
        if stalled and r.get("reasoning"):
            user = prompt_for(family, fam, p) + COMMIT_SUFFIX.format(notes=r["reasoning"][-a.notes_chars:])
            try:
                reply = call_model(a.provider, a.model, "nothink", user, 6000, a.timeout)
                err = None
            except Exception as e:                                   # noqa: BLE001
                reply, err = {"content": "", "reasoning": None, "usage": None, "system_fingerprint": None,
                              "response_model": None, "latency_s": None, "finish_reason": None}, repr(e)[:200]
            ans = extract_json(reply["content"]) if reply["content"] else None
            ans = expand_answer(fam, p, ans)
            feasible, obj, msg = (fam.verify(p, ans) if ans is not None else (False, 0, "no JSON answer found"))
            committed = True
        else:                                     # already answered (or nothing to commit from): carry over
            reply, err = {"content": r.get("content", ""), "reasoning": None, "usage": r.get("usage"),
                          "system_fingerprint": r.get("system_fingerprint"), "response_model": r.get("response_model"),
                          "latency_s": r.get("latency_s"), "finish_reason": r.get("finish_reason")}, r.get("error")
            feasible, obj, msg = r["feasible"], r["objective"], r["verify_msg"]
            ans = None
            committed = False
        rec = dict(r)
        rec.pop("content", None); rec.pop("reasoning", None)
        rec.update({"config": label, "feasible": feasible, "objective": obj, **score(fam, ref, feasible, obj),
                    "beats_reference": bool(feasible and ((obj > ref["search"]) if fam.sense == "max" else (obj < ref["search"]))),
                    "verify_msg": msg, "error": err, "law": (fam.law(p, obj) if feasible else None),
                    "committed": committed, "commit_usage": reply["usage"] if committed else None,
                    "answer_len": (len(ans) if isinstance(ans, (list, str)) else r.get("answer_len"))})
        if a.keep_text and committed:
            rec["commit_content"] = reply["content"]
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        print(f"{a.model:20s} {label:22s} {family:10s} seed={seed} committed={committed!s:5s} feasible={feasible!s:5s} "
              f"obj={obj!s:>8s} ref={ref['search']!s:>8s} gain={rec['gain']:.2f} {msg or err or ''}", flush=True)
    fh.close()


def cmd_summarize(a):
    rows = []
    for f in glob.glob(os.path.join(ROOT, "bench", "results", "*.jsonl")):
        rows += [json.loads(l) for l in open(f)]
    if a.tier:                                     # pseudo-model rows carry the tier too (search-nothink#A2 etc.)
        rows = [r for r in rows if r.get("tier", "A1") == a.tier]
    if a.configs:                                  # e.g. --configs nothink think-low@128k think-high@128k plain
        rows = [r for r in rows if r["config"] in a.configs or r["model"] in ("naive", "search", "garbage")]
    seen, uniq = set(), []
    for r in rows:                                 # duplicates can arise from parallel workers; first row wins
        k = (r["model"], r["config"], r["family"], r["seed"])
        if k not in seen:
            seen.add(k); uniq.append(r)
    rows = uniq
    if not rows:
        print("no results")
        return
    fams = sorted({r["family"] for r in rows})
    groups = {}
    for r in rows:
        groups.setdefault((r["model"], r["config"]), []).append(r)
    print(f"{'model':22s} {'config':10s} {'n':>3s} {'feas':>5s} {'gain':>5s} {'closed':>6s} {'>ref':>4s}  "
          + " ".join(f"{f[:7]:>7s}" for f in fams))
    # instances where the reference search did not beat the naive construction are calibration
    # instances ("does the model know the construction?"); they are reported separately and
    # excluded from the gain mean so that a memorised Welch or Sylvester cannot inflate it.
    def is_band(r):
        return r["reference"] != r["naive"]
    for (m, c), rs in sorted(groups.items()):
        feas = sum(r["feasible"] for r in rs) / len(rs)
        band = [r for r in rs if is_band(r)]
        gain = sum(r["gain"] for r in band) / len(band) if band else float("nan")
        beats = sum(r["beats_reference"] for r in rs)
        cg = [closed_gap(FAMILIES[r["family"]], r["params"], r["naive"], r["objective"], r["feasible"], r.get("reference"))[0] for r in rs]
        cg = [x for x in cg if x is not None]
        closed = sum(cg) / len(cg) if cg else float("nan")
        per = []
        for f in fams:
            fr = [r["gain"] for r in rs if r["family"] == f and is_band(r)]
            cal = [r for r in rs if r["family"] == f and not is_band(r)]
            if fr:
                per.append(f"{sum(fr)/len(fr):7.2f}")
            elif cal:
                per.append(f"{'cal ' + str(sum(x['feasible'] and x['objective'] == x['reference'] for x in cal)) + '/' + str(len(cal)):>7s}")
            else:
                per.append(f"{'-':>7s}")
        print(f"{m:22s} {c:10s} {len(rs):3d} {feas:5.0%} {gain:5.2f} {closed:6.2f} {beats:4d}  " + " ".join(per))
    print("  (cal a/b = calibration instances where a known construction is already optimal for the reference: a of b matched it)")
    # law view: the scale-free constant per family, against its open interval
    print("\nlaw view: mean scale-free constant per family (feasible answers only); open interval in brackets")
    keys = sorted({(r["family"], r["law"]["name"]) for r in rows if r["law"]})
    fmt = lambda v: "?" if v is None else f"{v:.3f}"
    heads = []
    for f, ln in keys:
        L = next(r["law"] for r in rows if r["family"] == f and r["law"] and r["law"]["name"] == ln)
        heads.append(f"{ln}[{fmt(L['lower'])},{fmt(L['upper'])}]{'^' if L['better'] == 'higher' else 'v'}")
    print(f"{'model':22s} {'config':10s}  " + "  ".join(heads))
    for (m, c), rs in sorted(groups.items()):
        cells = []
        for f, ln in keys:
            vals = [r["law"]["value"] for r in rs if r["family"] == f and r["law"] and r["law"]["name"] == ln]
            cells.append(f"{sum(vals)/len(vals):.3f}" if vals else "-")
        print(f"{m:22s} {c:10s}  " + "  ".join(f"{v:>{len(h)}s}" for v, h in zip(cells, heads)))
    # performance profile (Dolan-More): share of instances on which a model is within tau of the
    # best model on that instance; needs no optimum at all.
    by_inst = {}
    for r in rows:
        by_inst.setdefault((r["family"], r["seed"]), {})[(r["model"], r["config"])] = r
    taus = [1.0, 0.95, 0.9, 0.8, 0.5]
    print("\nperformance profile: fraction of instances within tau of the best model")
    print(f"{'model':22s} {'config':10s}  " + " ".join(f"tau={t:<4}" for t in taus))
    for key in sorted(groups):
        fr = []
        for inst, per in by_inst.items():
            if key not in per:
                continue
            r = per[key]
            vals = [q["objective"] for q in per.values() if q["feasible"]]
            if not vals:
                fr.append(0.0); continue
            best = max(vals) if r["sense"] == "max" else min(vals)
            ratio = (r["objective"] / best if r["sense"] == "max" else best / r["objective"]) if (r["feasible"] and best) else 0.0
            fr.append(ratio)
        print(f"{key[0]:22s} {key[1]:10s}  " + " ".join(f"{sum(x >= t for x in fr)/len(fr):8.0%}" for t in taus))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--provider", default="deepseek")
    r.add_argument("--model", required=True, help="model id, or one of naive/search/garbage for a dry run")
    r.add_argument("--config", default="nothink", choices=list(CONFIGS))
    r.add_argument("--families", nargs="*", default=None, help="default: every family of the selected tier")
    r.add_argument("--seeds", type=int, default=3)
    r.add_argument("--seed-list", type=int, nargs="*", default=[], help="run exactly these seeds (overrides --seeds)")
    r.add_argument("--ref-time", type=float, default=10.0, help="search budget (s) for the reference")
    r.add_argument("--max-tokens", type=int, default=0, help="0 = per-config default (MAX_TOKENS)")
    r.add_argument("--timeout", type=int, default=600)
    r.add_argument("--keep-text", action="store_true", help="store the reply and reasoning text in the record")
    r.add_argument("--tag", default="", help="label suffix for a budget variant, e.g. 32k -> config 'think-low@32k'")
    r.add_argument("--tier", default=None, help="size tier A1 or A2 (default: env BENCH_TIER or A1)")
    r.add_argument("--continue-slices", type=int, default=0, help="DeepSeek: resume a reasoning cut off at max_tokens up to N more times (label gains '+cont')")
    r.add_argument("--protocol", default="p1", choices=["p1", "p2"], help="p2 = prompt states the budget and asks the model to commit (label gains '.p2')")
    r.add_argument("--max-calls", type=int, default=0, help="stop after this many API calls (daily quotas); 0 = no cap")
    r.add_argument("--min-interval", type=float, default=0, help="seconds to wait between calls (RPM limits)")
    c = sub.add_parser("commit")
    c.add_argument("--file", required=True, help="results file (basename) whose stalled records get a commit call")
    c.add_argument("--provider", default="deepseek")
    c.add_argument("--model", required=True)
    c.add_argument("--ref-time", type=float, default=10.0)
    c.add_argument("--timeout", type=int, default=600)
    c.add_argument("--notes-chars", type=int, default=120000)
    c.add_argument("--keep-text", action="store_true")
    s = sub.add_parser("summarize")
    s.add_argument("--configs", nargs="*", default=[], help="restrict to these config labels (pseudo-models always shown)")
    s.add_argument("--tier", default=None, help="restrict to one size tier (A1 or A2)")
    a = ap.parse_args()
    {"run": cmd_run, "commit": cmd_commit, "summarize": cmd_summarize}[a.cmd](a)


if __name__ == "__main__":
    main()
