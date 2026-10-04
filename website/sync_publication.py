"""Refresh the preview's leaderboard and paper from the publication artifacts."""
import json
import shutil
import hashlib
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent
REPO = SITE.parent
SOURCE = REPO / "bench/paper/tables/publication_data.json"
TOOLS = REPO / "bench/paper/tables/tool_publication_data.json"
TOKENS = REPO / "output/figures/score-vs-tokens/data.json"
ADDITIONS = [SITE / 'dist/evaluations/sonnet55-high.json']


def additional_results():
    """Derive later leaderboard entries from their downloadable case records."""
    rows, notes = [], []
    for path in ADDITIONS:
        data = json.loads(path.read_text())
        assert data['schema_version'] == 1 and data['benchmark_version'] == 'bench-v1.0'
        assert data['instances'] == 69 and data['first_scored_outcomes'] and not data['reference_changes']
        assert data['reference_snapshot_sha256'] == hashlib.sha256((REPO / 'bench/frontiers/v1-trifference.json').read_bytes()).hexdigest()
        assert data['formal_suite_sha256'] == hashlib.sha256((REPO / 'bench/data/formal_suite_v1.json').read_bytes()).hexdigest()
        entries = json.loads((REPO / 'bench/construction_references.json').read_text())['entries']
        assert data['construction_reference_entries_sha256'] == hashlib.sha256(json.dumps(
            entries, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        for run in data['runs']:
            cases = run['cases']
            assert len(cases) == len({c['case_id'] for c in cases}) == 69
            for case in cases:
                assert hashlib.sha256(case['response'].encode()).hexdigest() == case['response_sha256']
                assert hashlib.sha256(case['prompt'].encode()).hexdigest() == case['prompt_sha256']
                assert case['verification']['agree'] and case['usage_complete']
                expected = (case['objective'] / case['reference'] if case['sense'] == 'max'
                            else case['reference'] / case['objective']) if case['valid'] else 0
                assert abs(expected - case['relative_quality']) < 1e-12
            published = [c for c in cases if c['reference_type'] == 'published']
            assert len(published) == 30
            total = sum(c['output_tokens'] for c in cases)
            row = {'id': run['id'], 'model': data['display_model'], 'effort': data['effort'],
                   'track': run['track'], 'score': 100 * sum(c['relative_quality'] for c in cases) / 69,
                   'hfr': sum(c['relative_quality'] for c in published) / 30,
                   'valid': 100 * sum(c['valid'] for c in cases) / 69,
                   'output_tokens': total, 'mean_output_tokens': total / 69,
                   'token_usage_is_lower_bound': False, 'token_usage_known_instances': 69,
                   'token_usage_complete_instances': 69,
                   'evaluation_data': str(path.relative_to(SITE / 'dist')),
                   'completed_utc': run['completed_utc']}
            related = [n for n in data['notes'] if n['configuration_id'] == run['id']]
            if related:
                assert len(related) == 1
                row['evaluation_note_id'] = related[0]['id']
                row['evaluation_note'] = related[0]['short_text']
            rows.append(row)
        notes.extend({**n, 'evaluation_data': str(path.relative_to(SITE / 'dist'))} for n in data['notes'])
    return rows, notes


def refresh_asset_versions():
    """Keep edited static assets fresh in browser and hosting caches."""
    page = SITE / 'dist/index.html'
    text = page.read_text()
    for name in ('style.css', 'motion.css', 'app.js', 'score-tokens.js', 'story-data.js', 'animations.js',
                 'assets/construction-mark.svg', 'assets/favicon.svg'):
        version = hashlib.sha256((SITE / 'dist' / name).read_bytes()).hexdigest()[:10]
        text = re.sub(r'((?:src|href)=")' + re.escape(name) + r'(?:\?[^"\s]*)?"',
                      lambda m: m.group(1) + name + '?v=' + version + '"', text)
    page.write_text(text)


def sync_results():
    data = json.loads(SOURCE.read_text())
    token_data = json.loads(TOKENS.read_text())
    token_systems = {system['id']: system for system in token_data['systems']}
    # Reuse the paper's audited accounting, and reject a stale token snapshot.
    for name, digest in token_data['source_sha256'].items():
        assert hashlib.sha256((REPO / name).read_bytes()).hexdigest() == digest, name
    rows = []
    for key, system in data["systems"].items():
        model, effort = system["label"].rsplit(" ", 1)
        rows.append({
            "id": key, "model": model, "effort": effort, "track": "tool-free",
            "score": system["overall"]["score"],
            "hfr": system["p1"]["mean"], "valid": system["valid"] * 100,
        })
    tools = json.loads(TOOLS.read_text())
    for key, system in tools['systems'].items():
        model = system['label'].removesuffix(' high + tools')
        rows.append({'id': key, 'model': model, 'effort': system['effort'], 'track': 'tool-assisted',
                     'score': system['overall']['score'], 'hfr': system['p1']['mean'],
                     'valid': system['valid'] * 100})
    rows.sort(key=lambda row: -row["score"])
    assert {row['id'] for row in rows} == set(token_systems)
    for row in rows:
        usage = token_systems[row['id']]
        assert usage['instances'] == data['distinct_instances']
        assert abs(usage['overall_score'] - row['score']) < 1e-9
        row.update({
            'output_tokens': usage['reported_output_tokens'],
            'mean_output_tokens': usage['reported_output_tokens'] / usage['instances'],
            'token_usage_is_lower_bound': usage['is_lower_bound'],
            'token_usage_known_instances': usage['known_usage_instances'],
            'token_usage_complete_instances': usage['complete_usage_instances'],
        })
    additions, notes = additional_results()
    assert not ({r['id'] for r in rows} & {r['id'] for r in additions})
    rows.extend(additions)
    rows.sort(key=lambda row: -row['score'])
    output = {
        "instances": data["distinct_instances"], "families": data["families"],
        "published": data["published_instances"], "configurations": len(rows),
        "rows": rows,
        "sources": [str(path.relative_to(REPO)) for path in (SOURCE, TOOLS, TOKENS, *ADDITIONS)],
        "benchmark_version": "bench-v1.0", "evaluation_notes": notes,
        "token_accounting": {
            "definition": token_data['token_definition'],
            "mean_definition": "Reported total divided by all 69 evaluated instances; "
                               "incomplete usage remains a lower bound, not a known-only mean.",
        },
        "tracks": {
            "tool-free": {"label": "Without tools", "configurations": sum(r['track'] == 'tool-free' for r in rows),
                          "protocol": "One response per instance · 128k output tokens, including reasoning."},
            "tool-assisted": {"label": "Code + web", "configurations": sum(r['track'] == 'tool-assisted' for r in rows),
                              "protocol": "Per instance: 4 CPU threads · 16 GiB memory · 2 hours · no cumulative output-token cap."},
        },
    }
    (SITE / "dist/results.json").write_text(json.dumps(output, indent=2) + "\n")
    return len(rows)


def main():
    count = sync_results()
    shutil.copy2(REPO / "output/pdf/endless-exam-arxiv.pdf",
                 SITE / "dist/assets/endless-exam.pdf")
    shutil.copy2(REPO / "bench/paper/figs/fig0_framework.png",
                 SITE / "dist/assets/framework.png")
    refresh_asset_versions()
    print(f"Synced {count} configurations, the manuscript and framework figure.")


if __name__ == "__main__":
    main()
