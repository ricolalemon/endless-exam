"""Known-frontier, exact-boundary and malformed-input regression checks."""
import copy
import json
from pathlib import Path
import random
import time
import unittest

import numpy as np

from crosscheck import kissing2
from openceiling import FAMILIES, expand_answer, verify_with_timeout
from quadratic_kissing import positive, sign
from run_ladder import extract_json, prompt_for

ROOT = Path(__file__).resolve().parents[1]
F = FAMILIES['kissing']


def quadratic(vectors):
    return {'quadratic_vectors': {'radicand': 3, 'vectors': vectors}}


class QuadraticKissingTests(unittest.TestCase):
    def assertVerdict(self, vectors, expected, dimension=2):
        answer = quadratic(vectors)
        params = {'d': dimension, 'representation': 'quadratic'}
        a = verify_with_timeout(F, params, answer)
        b = kissing2(params, expand_answer(F, params, answer))
        self.assertEqual(a[:2], b)
        self.assertEqual(a[0], expected, a)
        return a

    def test_published_1154_point_frontier(self):
        data = json.loads((ROOT/'bench/data/kissing13_quadratic.json').read_text())
        # Exercise the real JSON envelope, parser, timeout, and both checkers.
        answer = extract_json(json.dumps({'answer': data['answer']}))
        started = time.monotonic()
        self.assertEqual(verify_with_timeout(F, data['params'], answer), (True, 1154, ''))
        self.assertLess(time.monotonic()-started, 60)
        started = time.monotonic()
        self.assertEqual(kissing2(data['params'], answer), (True, 1154))
        self.assertLess(time.monotonic()-started, 60)
        self.assertFalse(F.verify({'d': 13}, answer)[0])

    def test_exact_sixty_degrees_and_both_sides(self):
        u = [[1, 0], [0, 0]]
        self.assertVerdict([u, [[1, 0], [0, 1]]], True)
        self.assertVerdict([u, [[1000, 0], [-1, 1000]]], False)
        self.assertVerdict([u, [[1000, 0], [1, 1000]]], True)

    def test_nonuniform_norms_and_antipodes(self):
        v = [[2, -1], [-3, 2]]
        self.assertVerdict([v, [[-4, 2], [6, -4]]], True)
        self.assertVerdict([v, [[4, -2], [-6, 4]]], False)
        self.assertVerdict([v, copy.deepcopy(v)], False)
        self.assertVerdict([[[0, 0], [0, 0]]], False)

    def test_pell_signs_beyond_float_precision(self):
        a, b = 2, 1
        while a <= 2**53:
            a, b = 2*a+3*b, a+2*b
        self.assertLess(a, 2**63)
        self.assertEqual(a*a-3*b*b, 1)
        self.assertEqual(sign(a, -b), 1)
        self.assertEqual(sign(-a, b), -1)
        self.assertEqual(sign(0, 0), 0)
        self.assertEqual(positive(np.array([a, -a, 0]), np.array([-b, b, 0])).tolist(),
                         [True, False, False])

    def test_schema_and_range_rejections(self):
        params = {'d': 2, 'representation': 'quadratic'}
        valid = quadratic([[[1, 0], [0, 0]]])
        cases = [None, {}, {'quadratic_vectors': []}, {'quadratic_vectors': None}]
        for radicand in [True, 3.0, '3', 0, 2, 4, 12, 10**100]:
            a = copy.deepcopy(valid);a['quadratic_vectors']['radicand'] = radicand;cases.append(a)
        for vector in [[], [[1, 0]], [[1, 0, 0], [0, 0]], [[True, 0], [0, 0]],
                       [[1.0, 0], [0, 0]], [['sqrt(3)', 0], [0, 0]],
                       [[1001, 0], [0, 0]], [[1, -(10**100)], [0, 0]]]:
            cases.append(quadratic([vector]))
        cases.extend([quadratic([]), quadratic([[[1, 0], [0, 0]]]*20001)])
        extra = copy.deepcopy(valid);extra['claimed_count'] = 1154;cases.append(extra)
        extra = copy.deepcopy(valid);extra['orbit'] = [[1, 0]];cases.append(extra)
        for answer in cases:
            with self.subTest(answer=str(answer)[:120]):
                self.assertFalse(verify_with_timeout(F, params, answer)[0])
                self.assertEqual(kissing2(params, answer), (False, 0))

    def test_random_mixed_norm_pairs_agree(self):
        rng = random.Random(20260917)
        for d in [1, 2, 5, 13, 16]:
            for _ in range(50):
                vectors = [[[rng.randint(-1000, 1000), rng.randint(-1000, 1000)]
                            for _ in range(d)] for _ in range(3)]
                p = {'d': d, 'representation': 'quadratic'};a = quadratic(vectors)
                self.assertEqual(F.verify(p, a)[:2], kissing2(p, a))

    def test_integer_and_orbit_compatibility(self):
        answer = {'orbit': [[1, 1]+[0]*11], 'signs': True, 'perms': True}
        for p in [{'d': 13}, {'d': 13, 'representation': 'quadratic'}]:
            expanded = expand_answer(F, p, answer)
            self.assertEqual(verify_with_timeout(F, p, answer), (True, 312, ''))
            self.assertEqual(kissing2(p, expanded), (True, 312))

    def test_opted_in_orbits_do_not_coerce_decimals_or_flags(self):
        p = {'d': 2, 'representation': 'quadratic'}
        for answer in [{'orbit': [[1.5, 0]]}, {'orbit': [[True, 0]]},
                       {'orbit': [[1, 0]], 'signs': 'false'},
                       {'orbit': [[1, 0]], 'perms': 1},
                       {'orbit': [[1001, 0]]}, {'orbit': [[1, 0]], 'claimed_count': 100}]:
            self.assertFalse(verify_with_timeout(F, p, answer)[0])
            self.assertEqual(kissing2(p, expand_answer(F, p, answer)), (False, 0))

    def test_prompt_explicitly_allows_exact_coordinates(self):
        old = prompt_for('kissing', F, {'d': 13}, 'p1')
        new = prompt_for('kissing', F, {'d': 13, 'representation': 'quadratic'}, 'p1')
        self.assertNotIn('quadratic_vectors', old)
        self.assertIn('quadratic_vectors', new)
        self.assertIn('a+b*sqrt(3)', new)
        self.assertIn('an integer-vector list or the exact quadratic_vectors object', new)
        self.assertNotIn('1154', new)  # no reference object or target count leaked into the prompt


if __name__ == '__main__':
    unittest.main()
