"""Missing infrastructure outcomes must never improve or depress a fixed-cohort score."""
import unittest
from evaluation_outcomes import scored_view, require_scored


class OutcomeTests(unittest.TestCase):
    def test_transport_is_missing_even_if_legacy_row_says_zero(self):
        original={'finish_reason':'transport_error','feasible':False,'objective':0,'reasoning_tokens':None}
        view=scored_view(original)
        self.assertFalse(view['scored'])
        self.assertIsNone(view['feasible'])
        self.assertIsNone(view['objective'])
        self.assertIsNone(view['reasoning_tokens'])
        self.assertEqual(original['objective'],0)
        with self.assertRaisesRegex(ValueError,'Unscored infrastructure failure'):require_scored(original)

    def test_invalid_completed_and_budget_exhaustion_still_score_zero(self):
        for finish in ['stop','length','timeout','tool_attempt_blocked']:
            row=scored_view({'finish_reason':finish,'feasible':False,'objective':0})
            self.assertTrue(row['scored'])
            self.assertEqual(require_scored(row)['objective'],0)

    def test_verifier_crash_is_missing_but_math_rejection_is_not(self):
        self.assertFalse(scored_view({'finish_reason':'stop','verify_msg':'verification_process_failed'})['scored'])
        self.assertTrue(scored_view({'finish_reason':'stop','verify_msg':'wrong length'})['scored'])


if __name__=='__main__':unittest.main()
