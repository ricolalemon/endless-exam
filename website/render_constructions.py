"""Render the accessible construction guide from its verified illustration data.

Run after editing story-data.js; --check validates that index.html is in sync.
"""
from pathlib import Path
import html
import json
import sys

root = Path(__file__).resolve().parent / "dist"
source = (root / "story-data.js").read_text()
data = json.loads(source.split("const data = ", 1)[1].split(";\nif", 1)[0])
page = root / "index.html"
original = page.read_text()
start = original.index('  <section class="motion-section wrap"')
end = original.index('  <section class="extra-section wrap"', start)
escape = html.escape

groups = {
    'Points and patterns': ('patterns', 'These problems forbid a particular pattern inside a set or colour class. A larger construction must include more points or integers without creating that pattern.'),
    'Geometry and distance': ('geometry', 'Geometric quality can be determined by a single limiting triangle or closest pair. In a graph, distance is measured by the number of edges along a path.'),
    'Designs and algorithms': ('designs', 'Covering designs and Latin squares organise combinations. Matrix multiplication asks for a collection of arithmetic identities that works for every input.'),
    'Sequences and codes': ('codes', 'The constraint changes from controlling correlations within one sequence to separating pairs or triples of words.'),
}
nav = ''.join(
    f'<li><a href="#family-{f["id"]}"><span>{i+1:02d}</span>{escape(f["title"])}</a></li>'
    for i, f in enumerate(data)
)
parts = []
previous_group = None
for f in data:
    if f['group'] != previous_group:
        if previous_group is not None:
            parts.append('</section>')
        group_id, introduction = groups[f['group']]
        parts.append(f'''<section class="family-group" aria-labelledby="group-{group_id}">
  <header class="family-group-heading"><h3 id="group-{group_id}">{escape(f['group'])}</h3><p>{escape(introduction)}</p></header>''')
        previous_group = f['group']

    # Small discrete examples need only two paragraphs; geometric and algorithmic
    # diagrams have more space for the limiting object or intermediate operations.
    if f['layout'] in ('compact', 'network', 'squares'):
        explanation = f'<p class="chapter-observation">{escape(f["example_text"])} {escape(f["scale_text"])}</p>'
    else:
        explanation = f'<p class="chapter-observation">{escape(f["example_text"])}</p><p class="chapter-scale">{escape(f["scale_text"])}</p>'

    parts.append(f'''<article class="family-chapter layout-{f['layout']}" id="family-{f['id']}" data-family="{f['id']}">
  <header class="chapter-heading"><h4>{escape(f['title'])}</h4></header>
  <div class="chapter-body">
    <figure class="chapter-figure" aria-label="{escape(f['instance'])}"><div class="chapter-picture"><canvas id="figure-{f['id']}" role="img" aria-label="{escape(f['title']+'. '+f['example_text'])}"></canvas></div><figcaption><span class="figure-measure"><strong data-value>—</strong> <span data-unit>illustration</span></span><span class="figure-legend">{escape(f['legend'])}</span><span class="sr-only" data-phase>{escape(f['description'])}</span></figcaption></figure>
    <div class="chapter-copy"><p class="chapter-task">{escape(f['task_text'])}</p>{explanation}</div>
  </div>
</article>''')
parts.append('</section>')
section = '''  <section class="motion-section wrap" id="constructions" aria-labelledby="motion-title">
    <div class="essay-intro"><div><h2 id="motion-title">The construction families</h2><p>These animations use small, verified examples to make the rules easy to see. The benchmark uses much larger instances—with higher dimensions, longer codes and larger grids—where finding high-quality constructions is substantially harder. These illustrations are separate from the model results above.</p></div><button id="story-motion" type="button" aria-pressed="false"><span aria-hidden="true">◒</span><span data-motion-label>Scroll animation</span></button></div>
    <details class="family-contents"><summary>Browse all 14 families</summary><nav aria-label="Construction family index"><ol>''' + nav + '''</ol></nav></details>
    <div class="family-essays">''' + ''.join(parts) + '''</div>
    <noscript><p>All family descriptions are available above. Enable JavaScript to see their animated constructions.</p></noscript>
  </section>
'''
rendered = original[:start] + section + original[end:]
if '--check' in sys.argv:
    if rendered != original:
        raise SystemExit('Construction sections need regeneration: python3 website/render_constructions.py')
    print('All 14 construction sections match story-data.js.')
else:
    page.write_text(rendered)
