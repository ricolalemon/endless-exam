"""Publication checks: unique instances, fixed source identity and equal weights."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'paper'))
import publication_data as P
from openceiling import FAMILIES, frontier_ratio

class PublicationTests(unittest.TestCase):
    def test_gap_progress_uses_fixed_witness_references_and_proven_bounds(self):
        import math
        from tool_results import load_all
        snapshot = json.loads((P.ROOT/'bench/frontiers/v1-trifference.json').read_text())['entries']
        witnesses = json.loads((P.ROOT/'bench/data/reference_witnesses/verification.json').read_text())['records']
        references = {(r['family'], json.dumps(r['params'], sort_keys=True)): r['reference'] for r in witnesses}
        refs, rows = P.load_formal()
        summaries = P.summaries()
        systems = []
        for sid, summary in summaries.items():
            system = P.REGISTRY[sid]
            selected = rows[system[1], system[3]+'#A3']
            systems.append((summary, [(r['family'], r['params'], selected[k]['objective'], selected[k]['feasible'])
                                      for k, r in refs.items()]))
        for summary in load_all().values():
            systems.append((summary, [(r['family'], r['params'], r['objective'], r['valid']) for r in summary['cases']]))
        for summary, records in systems:
            gaps, targets = [], []
            for family, params, obj, valid in records:
                key = family, json.dumps(params, sort_keys=True)
                h = references[key]; entry = snapshot[family+'|'+key[1]]
                b = entry['anchor']
                direction = 1 if FAMILIES[family].sense == 'max' else -1
                denominator = direction * math.log(b/h)
                self.assertGreater(denominator, 0)
                value = max(0, direction*math.log(obj/h)/denominator) if valid and obj > 0 else 0
                if entry['anchor_kind'] in ('bound', 'trivial'):
                    gaps.append(value)
                else:
                    self.assertEqual((family, entry['anchor_kind']), ('labs', 'conjecture'))
                    targets.append(value)
            self.assertEqual((len(gaps), len(targets)), (64, 5))
            self.assertAlmostEqual(summary['headroom'], sum(gaps)/64)
            self.assertEqual(summary['headroom_instances'], 64)
            self.assertAlmostEqual(summary['target_progress']['mean'], sum(targets)/5)
            g = summary['gap_closed']
            self.assertEqual((g['published']['n'], g['construction']['n']), (30, 34))
            self.assertEqual(g['published']['mean'], 0)
            self.assertAlmostEqual(g['mean'], (30*g['published']['mean']+34*g['construction']['mean'])/64)

    def test_family_anchor_means_use_the_same_frozen_instances(self):
        from figs import scale_reference_values, tool_scale_values
        from tool_results import load
        groups, models = scale_reference_values(), tool_scale_values()
        snapshot = json.loads((P.ROOT / 'bench/frontiers/v1-trifference.json').read_text())['entries']
        formal = {(c['family'], json.dumps(c['params'], sort_keys=True)) for c in P.C.cases()}
        tool_rows = {(r['family'], json.dumps(r['params'], sort_keys=True)): r for r in load()['cases']}
        seen = set()
        for key, group in groups.items():
            self.assertEqual(group['n'], models['astra_tools']['groups'][key]['n'])
            self.assertEqual(group['n'], models['luna_tools']['groups'][key]['n'])
            expected = []
            for r in group['instances']:
                ident = r['family'], json.dumps(r['params'], sort_keys=True)
                self.assertNotIn(ident, seen); seen.add(ident)
                bound = snapshot[r['family'] + '|' + ident[1]]['anchor']
                reference = tool_rows[ident]['reference']
                value = bound / reference if FAMILIES[r['family']].sense == 'max' else reference / bound
                self.assertEqual(r['anchor_ratio'], value)
                expected.append(value)
            self.assertEqual(group['anchor_ratio'], sum(expected) / len(expected))
        self.assertEqual(seen, formal)
        self.assertEqual(len(groups), 16)
        self.assertEqual(sum(g['n'] for (f,k),g in groups.items() if k=='published'), 30)
        self.assertEqual(sum(g['n'] for (f,k),g in groups.items() if k=='construction'), 39)

    def test_anchor_normalization_precedes_averaging_and_display_clipping(self):
        from figs import scale_reference_values
        g = scale_reference_values()
        cap = (2070/1082 + 5619/2432 + 16857/5504) / 3
        self.assertAlmostEqual(g['capset','published']['anchor_ratio'], cap)
        self.assertAlmostEqual(g['matmul','published']['anchor_ratio'], (61/20 + 93/25 + 76/25) / 3)
        self.assertNotAlmostEqual(g['matmul','published']['anchor_ratio'], (61+93+76)/(20+25+25))
        self.assertAlmostEqual(g['schur','published']['anchor_ratio'], (1896/536 + 13699/1696 + 109600/5362) / 3)
        self.assertGreater(g['spherical_code','construction']['anchor_ratio'], 60)
        self.assertGreater(g['trifference','construction']['anchor_ratio'], 1e23)
        self.assertTrue(g['heilbronn','construction']['anchor_is_proven'])
        self.assertFalse(g['labs','construction']['anchor_is_proven'])

    def test_family_figure_splits_reference_groups_and_keeps_zeroes(self):
        from figs import tool_scale_values
        from tool_results import load_all
        plotted, tools = tool_scale_values(), load_all()
        for sid, series in plotted.items():
            groups = series['groups']
            self.assertEqual(len(groups), 16)
            for kind, panel, expected_n in [('published', 'p1', 30), ('construction', 'p2', 39)]:
                cells = [g for (family, reference), g in groups.items() if reference == kind]
                self.assertEqual(sum(g['n'] for g in cells), expected_n)
                self.assertAlmostEqual(sum(g['mean'] * g['n'] for g in cells) / expected_n, tools[sid][panel]['mean'])
            self.assertEqual(groups['spherical_code', 'published']['mean'], 1)
            self.assertGreater(groups['spherical_code', 'construction']['mean'], 1.5)
        luna = plotted['luna_tools']['groups']
        self.assertEqual(luna['trifference', 'construction'], {'n': 4, 'mean': .75})
        self.assertEqual(luna['lineq', 'construction']['n'], 5)
        self.assertAlmostEqual(luna['lineq', 'construction']['mean'], .5974841322483607)

    def test_luna_tools_keep_the_three_scored_zeroes(self):
        from tool_results import load
        tool = load('luna_tools')
        self.assertAlmostEqual(tool['overall']['score'], 119.35416818356748)
        self.assertAlmostEqual(tool['p1']['mean'], 0.9609113359497304)
        self.assertAlmostEqual(tool['p2']['mean'], 1.3724881017479396)
        self.assertEqual((tool['accepted'], tool['improved'], tool['tied'], tool['declined']), (66, 61, 5, 3))
        self.assertEqual((tool['p1']['above'], tool['p1']['equal'], tool['p2']['above']), (0, 23, 25))
        self.assertEqual({r['call_id'] for r in tool['cases'] if not r['valid']},
                         {'a3-lineq-0', 'a3-lineq-3', 't3-trifference-0'})
        source = json.loads((P.ROOT / tool['source']).read_text())
        missing, = [r for r in source['cases'] if r['submission'] is None]
        self.assertEqual((missing['call_id'], missing['objective'], missing['reference_ratio']), ('a3-lineq-3', 0, 0))
        self.assertEqual(missing['resource_result'], 'oom-kill')
        self.assertEqual(tool['usage']['outputTokens'], 866731)
        self.assertEqual(tool['usage']['reasoningOutputTokens'], 425435)
        self.assertEqual(tool['usage']['totalTokens'], tool['usage']['inputTokens'] + tool['usage']['outputTokens'])
        self.assertAlmostEqual(tool['without_tools_score'], P.summaries(['luna_high'])['luna_high']['overall']['score'])

    def test_two_tool_models_share_the_same_protocol_and_instances(self):
        from tool_results import load_all
        tools = load_all()
        self.assertEqual(set(tools), {'astra_tools', 'luna_tools'})
        astra, luna = tools['astra_tools'], tools['luna_tools']
        self.assertEqual(astra['protocol'], luna['protocol'])
        pairs = list(zip(astra['cases'], luna['cases']))
        self.assertEqual(len(pairs), 69)
        for a, l in pairs:
            self.assertEqual((a['instance_id'], a['params'], a['reference']), (l['instance_id'], l['params'], l['reference']))
        wins = [l for a, l in pairs if l['reference_ratio'] > a['reference_ratio'] + 1e-9]
        self.assertEqual(len(wins), 7)
        self.assertEqual({r['family_group'] for r in wins}, {'heilbronn'})

    def test_score_token_figure_contains_both_full_tool_runs(self):
        from fig_score_tokens import collect
        data = collect()
        self.assertEqual(len(data['systems']), 14)
        systems = {s['id']: s for s in data['systems']}
        self.assertEqual(systems['luna_tools']['reported_output_tokens'], 866731)
        self.assertEqual(systems['astra_tools']['reported_output_tokens'], 445123)
        self.assertFalse(systems['luna_tools']['is_lower_bound'])
        self.assertTrue(systems['luna_high']['is_lower_bound'])

    def test_tool_track_uses_same_instances_and_fixed_references(self):
        from tool_results import load
        tool = load()
        self.assertEqual(tool['overall']['n'], 69)
        self.assertEqual((tool['p1']['n'], tool['p2']['n']), (30, 39))
        self.assertEqual((tool['accepted'], tool['improved'], tool['tied']), (69, 62, 7))
        self.assertEqual((tool['p1']['above'], tool['p1']['equal'], tool['p2']['above']), (0, 29, 33))
        self.assertAlmostEqual(tool['overall']['score'], 100 * (30 * tool['p1']['mean'] + 39 * tool['p2']['mean']) / 69)
        self.assertAlmostEqual(100 * sum(r['without_tools_ratio'] for r in tool['cases']) / 69,
                               P.summaries(['astra_high'])['astra_high']['overall']['score'])
        self.assertEqual(len(P.ORDER), 12)

    def test_tool_usage_includes_reasoning_once_and_preserves_submission(self):
        from tool_results import load
        tool = load();usage = tool['usage']
        self.assertEqual(usage['totalTokens'], usage['inputTokens'] + usage['outputTokens'])
        self.assertEqual(usage['outputTokens'], 445123)
        self.assertEqual(usage['reasoningOutputTokens'], 181416)
        self.assertTrue(all(r['usage_complete'] for r in tool['cases']))
        tri = next(r for r in tool['cases'] if r['family'] == 'trifference' and r['params']['n'] == 64)
        self.assertEqual((tri['objective'], tri['reference_ratio']), (3**11, 9))

    def test_exact_formal_scope_and_cross_tier_source_mapping(self):
        refs, rows = P.load_formal()
        self.assertEqual(len(refs),69);self.assertEqual(len(rows),12)
        self.assertEqual(len({(f,json.dumps(r['params'],sort_keys=True)) for (f,s),r in refs.items()}),69)
        for rs in rows.values():
            self.assertEqual(len(rs),69)
            tri = [r for (f,s),r in rs.items() if f=='trifference']
            self.assertEqual({r['tier'] for r in tri},{'T1','T2','T3','T4'})
            self.assertTrue(all(r['params']['representation']=='certified' for r in tri))
        astra = rows['gpt-6-astra','codex-high@nocap#A3']
        for family in ['shannon','capset']:
            case=next(c for c in P.C.cases() if (c['tier'],c['family'],c['seed'])==('A3',family,0))
            path,config=P.C.source_path(P.REGISTRY['astra_high'],case)
            selected=[r for r in map(json.loads,path.read_text().splitlines()) if (r['family'],r['seed'])==(family,0)]
            self.assertEqual(len(selected),1)
            self.assertEqual(astra[family,0]['config'],config)
            self.assertEqual(astra[family,0]['content'],selected[0]['content'])
        self.assertNotIn(('claude-opus-5','headless-medium@128k#A3'),rows)
        for key,rs in rows.items():
            if key[0]=='gpt-5.6-luna':
                for r in rs.values():
                    expected = ('kissing13-quadratic-2026-09-17' if r['family']=='kissing' and
                                r['params'].get('representation')=='quadratic' else
                                'infrastructure-recovery-2026-09-17' if '.infra-recovery#' in r['config'] else
                                'luna-full-single-2026-09-15')
                    self.assertEqual(r.get('collection_id'), expected)

    def test_panel_means_use_one_response_per_instance(self):
        refs, rows = P.load_formal();summaries=P.summaries()
        for sid in P.ORDER:
            s=P.REGISTRY[sid];groups={True:{},False:{}}
            for key,r in rows[s[1],s[3]+'#A3'].items():
                ref=refs[key];value,kind=frontier_ratio(FAMILIES[key[0]],r['params'],ref['naive'],r['objective'],r['feasible'],ref['objective'])
                ident=(key[0],json.dumps(r['params'],sort_keys=True))
                groups[kind=='literature'].setdefault(ident,[]).append(value)
            for published,panel,n in [(True,'p1',30),(False,'p2',39)]:
                self.assertTrue(all(len(xs)==1 for xs in groups[published].values()))
                v=[sum(xs)/len(xs) for xs in groups[published].values()]
                self.assertEqual(len(v),n);self.assertAlmostEqual(sum(v)/n,summaries[sid][panel]['mean'])
            all_ratios=[sum(xs)/len(xs) for panel in groups.values() for xs in panel.values()]
            total=summaries[sid]['overall']
            self.assertEqual(total['n'],69)
            self.assertAlmostEqual(total['score'],100*sum(all_ratios)/69)
            self.assertEqual(total['ci'],tuple(100*x for x in P.ci(all_ratios)))

    def test_overall_score_keeps_failures_and_post_reference_improvements(self):
        total=P.overall_score([0,1,4])
        self.assertEqual(total['n'],3)
        self.assertAlmostEqual(total['score'],500/3)
        self.assertGreater(total['score'],100)
        self.assertEqual(P.overall_score([1,1,1])['score'],100)

    def test_matched_subset_score_uses_its_45_distinct_instances(self):
        cases=[c for c in P.C.cases() if P.C.get_row(P.REGISTRY['opus'],c) is not None]
        s=P.summaries(['opus'],cases)['opus']
        self.assertEqual(s['overall']['n'],45)
        self.assertAlmostEqual(s['overall']['score'],100*(15*s['p1']['mean']+30*s['p2']['mean'])/45)

    def test_budget_failures_remain_zero_and_codes_are_96(self):
        cases,rows=P.code_data();self.assertEqual(len(cases),8);self.assertEqual(len(rows),96)
        fable=[r for r in rows if r['system']=='fable' and r['family']=='shannon']
        self.assertEqual([r['ratio'] for r in fable],[0,0,0,1])
        self.assertEqual([r['finish_reason'] for r in fable[:2]],['length','length'])
        tri=[r for r in rows if r['system']=='astra_high' and r['family']=='trifference']
        self.assertEqual([r['ratio'] for r in tri],[3,1,1,1])

    def test_fable_high_is_a_separate_complete_configuration(self):
        values=P.summaries(['fable','fable_high'])
        self.assertAlmostEqual(values['fable']['overall']['score'],71.89512750577023)
        high=values['fable_high']
        self.assertEqual((high['calls'],high['accepted'],high['p1']['n'],high['p2']['n']),(69,36,30,39))
        self.assertAlmostEqual(high['overall']['score'],43.733216554432424)
        self.assertAlmostEqual(high['p1']['mean'],0.5398261924645702)
        self.assertAlmostEqual(high['p2']['mean'],0.3584906063749043)
        self.assertEqual(high['p1']['records'],0)
        cache={}
        rows=[P.C.get_row(P.REGISTRY['fable_high'],c,cache) for c in P.C.cases()]
        self.assertEqual(sum(r['finish_reason']=='length' for r in rows),32)
        self.assertEqual(sum(not r['feasible'] and r['finish_reason']=='stop' for r in rows),1)
        self.assertTrue(all(r['objective']==0 for r in rows if not r['feasible']))
        self.assertEqual(sum(r['usage']['output_tokens'] for r in rows),5388481)
        self.assertEqual(sum(not r['usage_complete'] for r in rows),1)
        self.assertTrue(all(r['config'].startswith('headless-high@128k.frozen69#') for r in rows))

    def test_verified_published_witnesses_score_parity(self):
        from openceiling import known_best
        audit = P.ROOT/'bench/frontier_audits/2026-09-16'
        for filename, params, previous in [
            ('capset_d11_5504.json', {'d':11}, 5488),
            ('schur7_1696.json', {'k':7}, 1680),
        ]:
            witness = json.loads((audit/filename).read_text())
            family = FAMILIES[witness['family']]
            objective = len(witness['answer'])
            self.assertEqual(known_best(family, params), objective)
            self.assertEqual(frontier_ratio(family, params, 1, objective, True, 1), (1.0, 'literature'))
            self.assertLess(frontier_ratio(family, params, 1, previous, True, 1)[0], 1)
            key = witness['family']+'|'+json.dumps(params, sort_keys=True)
            for snapshot in (P.ROOT/'bench/frontiers').glob('*.json'):
                entry = json.loads(snapshot.read_text())['entries'][key]
                self.assertEqual(entry['known_best'], objective, snapshot.name)

    def test_binary_breakthrough_is_applied_before_repeat_averaging(self):
        ref = {('capset', s): {'params': {'d': 2}, 'naive': 1, 'objective': 1} for s in (0, 1)}
        rows = {('test', 'config'): {('capset', s): {'params': {'d': 2}, 'objective': o, 'feasible': True}
                                    for s, o in ((0, 1.2), (1, .6))}}
        with patch.object(P, 'frontier_ratio', side_effect=lambda f,p,n,o,v,r: (o if v else 0, 'literature')):
            values = P.system_values(rows, ref, 'test', 'config', ['capset'],
                                     fn=P.binary_breakthrough, kind_filter='literature')
            self.assertEqual(values['capset'], [.5])
            self.assertEqual(P.binary_breakthrough(None, {}, 1, 1, True, 1)[0], 0)
            self.assertEqual(P.binary_breakthrough(None, {}, 1, 2, False, 1)[0], 0)
        self.assertTrue(all(0 <= s['p1']['binary_breakthrough_rate'] <= 1 for s in P.summaries().values()))

if __name__=='__main__':unittest.main()
