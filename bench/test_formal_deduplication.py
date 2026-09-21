"""Formal deduplication fixes one common seed without selecting better answers."""
import unittest
from unittest.mock import patch
import formal_cohort as C


class FormalDeduplicationTests(unittest.TestCase):
    def test_selection_ignores_answer_quality_and_input_order(self):
        first={'family':'capset','params':{'d':2},'tier':'A3','seed':0,'objective':0,'feasible':False}
        better={**first,'seed':1,'objective':100,'feasible':True}
        other={**first,'params':{'d':3},'seed':4}
        for calls in [[first,better,other],[better,other,first]]:
            selected=C.distinct_cases(calls)
            self.assertEqual(len(selected),2)
            self.assertEqual(next(c for c in selected if c['params']=={'d':2}),first)

    def test_auxiliary_a3_views_cannot_restore_removed_repeats(self):
        cases=[{'family':'capset','params':{'d':2},'tier':'A3','seed':0}]
        ref={('capset',0):{},('capset',1):{},('kakeya',0):{}}
        rows={('model','config'):{('capset',0):{'objective':0},('capset',1):{'objective':100},('kakeya',0):{'objective':1}}}
        with patch.object(C,'cases',return_value=cases):
            selected_ref,selected_rows=C.formal_a3_view(ref,rows,keep_controls=('kakeya',))
        self.assertEqual(set(selected_ref),{('capset',0),('kakeya',0)})
        self.assertEqual(selected_rows['model','config'],{('capset',0):{'objective':0},('kakeya',0):{'objective':1}})


if __name__=='__main__':unittest.main()
