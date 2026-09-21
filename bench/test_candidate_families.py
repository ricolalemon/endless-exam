"""Offline property checks for candidate pilots, including independent checks and malformed certificates."""
from itertools import combinations, product
import random
import unittest

from candidate_families import (Shannon, Trifference, shannon_second, trifference_second,
                                zarank_second, norm_graph_reference, _projective_code)
from openceiling import FAMILIES, HEADROOM, expand_answer, verify_with_timeout


class CandidateTests(unittest.TestCase):
    def test_promoted_codes_and_remaining_candidate(self):
        from family_catalog import CORE_GROUPS
        self.assertEqual(len(HEADROOM["open"]), 16)
        self.assertEqual(len(CORE_GROUPS), 14)
        self.assertEqual(len(HEADROOM["legacy15"]), 15)
        self.assertIn("shannon", HEADROOM["open"])
        self.assertIn("trifference", HEADROOM["open"])

    def test_shannon_known_codes_and_invalid_pairs(self):
        f = Shannon()
        for p,count in [({"q":5,"d":2},5),({"q":7,"d":3},31),({"q":7,"d":4},107),
                        ({"q":7,"d":5},367),({"q":7,"d":6},1101)]:
            a = f.naive(p)
            self.assertEqual(f.verify(p,a)[:2],(True,count))
            self.assertEqual(shannon_second(p,a),(True,count))
            self.assertLessEqual(count,f.upper(p))
        for a in [["00","60"],["00","00"],["00","71"],[],[False], ["000"]]:
            self.assertFalse(f.verify({"q":7,"d":2},a)[0])
        self.assertTrue(f.verify({"q":7,"d":2},["00","02"])[0])

    def test_shannon_exhaustive_small_subsets(self):
        f = Shannon();p={"q":5,"d":2}
        universe=["".join(w) for w in product("01234",repeat=2)]
        for a in combinations(universe,3):
            a=list(a)
            self.assertEqual(f.verify(p,a)[:2],shannon_second(p,a))

    def test_product_expansion_checks_size_before_allocating(self):
        f=Shannon();p={"q":7,"d":6}
        a={"product":[f.naive({"q":7,"d":5}),["0","2","4"]]}
        self.assertEqual(verify_with_timeout(f,p,a)[:2],(True,1101))
        bad=[{"product":[["0"]]*7},{"product":[["0","1"]]*6},
             {"product":[[str(i) for i in range(7)]]*6},{"product":[[]]},
             {"product":[[True]]},{"product":[["0"],["0"]]}]
        for a in bad:
            self.assertFalse(verify_with_timeout(f,p,a)[0])

    def test_trifference_small_exact_examples_and_invalid_product(self):
        f=Trifference()
        for a,p,expected in [(["0","1","2"],{"n":1,"m":1},True),
                              (["00","01","10"],{"n":2,"m":1},False),
                              (["00","11","22"],{"n":2,"m":2},True),
                              (["00","11","20"],{"n":2,"m":2},False)]:
            self.assertEqual(f.verify(p,a)[0],expected)
            self.assertEqual(f.verify(p,a)[:2],trifference_second(p,a))
        for a in [[],[True],["000","000"],["003"],{"size":100000}]:
            self.assertFalse(f.verify({"n":3,"m":1},a)[0])

    def test_trifference_exhaustive_triples(self):
        f=Trifference()
        universe=["".join(w) for w in product("012",repeat=3)]
        for a in combinations(universe,3):
            a=list(a)
            truth=sum(len({w[i] for w in a})==3 for i in range(3))
            for m in (1,2,3):
                expected=(truth>=m,3 if truth>=m else 0)
                p={"n":3,"m":m}
                self.assertEqual(f.verify(p,a)[:2],expected)
                self.assertEqual(trifference_second(p,a),expected)

    def test_linear_code_is_expanded_not_assumed_valid(self):
        f=Trifference();p={"n":4,"m":1}
        columns,code=_projective_code(2)
        generator=["".join(str(c[i]) for c in columns) for i in range(2)]
        self.assertEqual(verify_with_timeout(f,p,{"linear":generator})[:2],(True,9))
        self.assertFalse(verify_with_timeout(f,{"n":2,"m":1},{"linear":["10","01"]})[0])
        self.assertFalse(verify_with_timeout(f,p,{"linear":["0"*4]*6})[0])
        # Dependent generator rows count the actual span, not 3^number-of-rows.
        self.assertEqual(len(expand_answer(f,p,{"linear":["1111","2222"]})),3)

    def test_norm_construction_and_near_miss(self):
        f=FAMILIES["zarank"]
        for n in (18,50,100,294):
            a=f.naive({"n":n})
            self.assertTrue(f.verify({"n":n},a)[0])
            self.assertEqual(f.verify({"n":n},a)[:2],zarank_second({"n":n},a))
            self.assertGreaterEqual(sum(r.count("1") for r in a),sum(r.count("1") for r in f._projective_plane({"n":n})))
            bad=list(a)
            for i in range(4): bad[i]="1111"+bad[i][4:]
            self.assertFalse(f.verify({"n":n},bad)[0])
            self.assertFalse(zarank_second({"n":n},bad)[0])

    def test_matrix_checkers_against_brute_force(self):
        f=FAMILIES["zarank"];rng=random.Random(71);n=6
        for _ in range(100):
            rows=["".join("1" if rng.random()<.8 else "0" for _ in range(n)) for _ in range(n)]
            valid=not any(all(rows[i][j]=="1" for i in rr for j in cc)
                          for rr in combinations(range(n),4) for cc in combinations(range(n),4))
            expected=(valid,sum(r.count("1") for r in rows) if valid else 0)
            self.assertEqual(f.verify({"n":n},rows)[:2],expected)
            self.assertEqual(zarank_second({"n":n},rows),expected)


if __name__ == "__main__":
    unittest.main()
