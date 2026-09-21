"""Reference-to-bound progress, eligibility, and separately reported targets."""
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import openceiling as O


class GapClosedTests(unittest.TestCase):
    def score(self, sense, h, b, a, valid=True, kind="bound", target=False):
        family = SimpleNamespace(sense=sense, name="example")
        with patch.object(O, "effective_frontier", return_value=(h, True)), \
             patch.object(O, "anchor", return_value=(b, kind)), \
             patch.object(O, "textbook_zero", side_effect=AssertionError("must not use a separate baseline")):
            fn = O.conjectured_gap if target else O.closed_gap
            return fn(family, {}, 1, a, valid, 2)

    def test_reference_and_bound_endpoints_and_multiplicative_midpoint(self):
        for sense, h, b in [("max", 100, 400), ("min", 400, 100)]:
            self.assertEqual(self.score(sense, h, b, h), (0, "bound"))
            self.assertEqual(self.score(sense, h, b, b), (1, "bound"))
            self.assertAlmostEqual(self.score(sense, h, b, 200)[0], .5)

    def test_invalid_and_below_reference_answers_are_scored_zero(self):
        for a in (None, 0, -1, 50, 100):
            self.assertEqual(self.score("max", 100, 400, a)[0], 0)
        self.assertEqual(self.score("max", 100, 400, 300, False)[0], 0)
        self.assertEqual(self.score("min", 400, 100, 500)[0], 0)

    def test_eligibility_does_not_depend_on_the_answer(self):
        for h, b, kind in [(100, 100, "bound"), (100, 50, "bound"),
                           (100, None, None), (100, 400, "literature"),
                           (100, 400, "conjecture")]:
            for valid in (True, False):
                self.assertIsNone(self.score("max", h, b, 200, valid, kind)[0])
        self.assertEqual(self.score("max", 100, 400, 200, kind="trivial"), (.5, "trivial"))

    def test_conjecture_is_separate_and_is_not_clipped_at_one(self):
        self.assertEqual(self.score("max", 100, 400, 1600, kind="conjecture", target=True), (2, "conjecture"))
        self.assertIsNone(self.score("max", 100, 400, 200, target=True)[0])
        self.assertEqual(self.score("max", 100, 400, 1600), (2, "bound!"))

    def test_large_integer_sizes_and_change_of_units(self):
        self.assertAlmostEqual(self.score("max", 10**500, 10**900, 10**700)[0], .5)
        self.assertAlmostEqual(self.score("min", 10**900, 10**500, 10**700)[0], .5)
        for scale in (1e-6, 1, 1e6):
            self.assertAlmostEqual(self.score("max", 100*scale, 400*scale, 250*scale)[0], math.log(2.5)/math.log(4))


if __name__ == "__main__":
    unittest.main()
