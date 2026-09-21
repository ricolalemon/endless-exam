"""Checks for cross-script CIs and effort comparisons over repeated parameter settings."""
from pathlib import Path
import json
import math
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import figs
from report import ci
from search_evidence import scoring_zero, log_gain, instance_mean, collect
import tempfile


class AnalysisTests(unittest.TestCase):
    def test_expert_floor_is_not_a_warm_start_claim(self):
        before = {"params": {"d": 10}, "naive": 1024, "search": 1140}
        after = dict(before, search=1202)
        self.assertGreater(log_gain("capset", before["search"], after["search"]), 0)
        self.assertEqual(scoring_zero("capset", before), 2240)
        self.assertEqual(log_gain("capset", scoring_zero("capset", before), scoring_zero("capset", after)), 0)
        with patch("search_evidence.textbook_zero", return_value=(703, "T")):
            before = {"params": {"q": 13, "n": 3}, "naive": 2197, "search": 1000}
            after = dict(before, search=988)
            self.assertGreater(log_gain("kakeya", 1000, 988), 0)
            self.assertEqual(scoring_zero("kakeya", before), 703)
            self.assertEqual(scoring_zero("kakeya", after), 703)

    def test_reference_repeats_and_missing_measurements(self):
        runs = [{"params": {"d": 10}, "gain": .05}, {"params": {"d": 10}, "gain": .05},
                {"params": {"d": 11}, "gain": .15}]
        self.assertAlmostEqual(instance_mean(runs, "gain"), .10)
        with tempfile.TemporaryDirectory() as directory:
            result = collect(ref_dir=directory, families=["schur"])["schur"]
        self.assertEqual(result["n_pairs"], 0)
        self.assertIsNone(result["raw_mean"])
        self.assertIsNone(result["zero_mean"])

    def test_ci_does_not_depend_on_plotting_order(self):
        values = [0, .3, .9, 1.2, .6, 0, 1, .8]
        self.assertEqual(ci(values), ci(list(reversed(values))))
        self.assertEqual(ci(values), ci(sorted(values)))

    def test_effort_uses_common_parameters_and_equal_instance_weight(self):
        def row(d, objective, feasible=True):
            return {"params": {"d": d}, "objective": objective, "feasible": feasible}
        ref = {("capset", s): dict(row(d, 1), naive=1) for s, d in [(0, 2), (1, 2), (2, 3), (4, 2), (5, 4)]}
        rows = {("test", "med#A2"): {("capset", 0): row(2, 1), ("capset", 1): row(2, 0, False), ("capset", 2): row(3, 1)},
                ("test", "high#A2"): {("capset", 4): row(2, 1), ("capset", 2): row(3, .5), ("capset", 5): row(4, 100)}}
        ladder = [("test", "test", [("medium", "med"), ("high", "high")], "black")]
        with patch.object(figs, "LADDER", ladder), patch.object(figs, "frontier_ratio", lambda f,p,n,o,v,r: (o, "literature")):
            series, = figs.effort_values(rows, ref, ["capset"], min_rows=1)
        self.assertEqual(series["n"], 2)
        self.assertEqual(series["points"]["medium"], {"hfr": .75, "valid": .75})
        self.assertEqual(series["points"]["high"], {"hfr": .75, "valid": 1})

    def test_search_comparison_includes_fourth_shannon_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            for family in ["shannon", "schur"]:
                for seed in range(4):
                    for seconds in [10, 600]:
                        record = {"params": {"index": seed}, "naive": 1,
                                  "search": 2 if seconds == 600 and seed == 3 else 1}
                        path = Path(directory) / f"A3-{family}-{seed}-t{seconds}.json"
                        path.write_text(json.dumps(record))
            with patch("search_evidence.textbook_zero", return_value=None):
                result = collect(ref_dir=directory, families=["shannon", "schur"])
        self.assertEqual(result['shannon']['n_instances'], 4)
        self.assertAlmostEqual(result['shannon']['raw_mean'], math.log(2) / 4)
        self.assertEqual(result['schur']['n_instances'], 3)
        self.assertEqual(result['schur']['raw_mean'], 0)


if __name__ == "__main__":
    unittest.main()
