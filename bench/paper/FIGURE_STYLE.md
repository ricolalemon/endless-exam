# Figure style

The manuscript, tables and construction diagrams use the
**ink and ochre** theme. Statistical plots use distinct model colours within
the same typography, line widths, grids and legend layout. `visual_theme.py`
holds both palettes and generates `visual_theme.tex` for LaTeX; the main
scientific figures share `plot_style.py`.

## Page palette

Use white backgrounds, dark ink for text and constructions, warm-grey rules and
grid lines, and ochre (`#AF8538`) for measured progress and result highlights.
Task and construction boxes have white interiors, pale warm-grey title strips
and thin borders. Result boxes use a light ochre strip. The benchmark comparison
uses black checks, grey crosses and an ochre-tinted Endless Exam row. Links and
family headings use dark ink. Colour names in captions follow the rendered key.

The introductory diagram shows five points of an AP-free set over five symbols.
Its verification and score use the defining mathematical property and the
six-point optimum, both checked by the figure script.

## Physical size and typography

- Export at **5.5 inches / 396 PDF points**, exactly the ICLR text width.
- Include each figure at `\linewidth`; do not apply a second fractional shrink.
- Use DejaVu Sans, including a consistent math-text configuration.
- Axis labels and panel titles: 8.2 pt; ticks: 7.2 pt; legends: 7 pt;
  compact annotations: 6.6 pt. Mathematical superscripts retain normal scaling.
- Export the fixed canvas without `bbox_inches="tight"`; the save helper rejects
  labels outside that canvas. Figure heights remain appropriate to their content.

## Model identity

The canonical configuration palette is `visual_theme.MODEL_COLORS`, exposed as
`publication_data.COLORS`; markers and line styles are in `plot_style`.
Qwen3.5 uses green shades and three triangle markers; Qwen3.8 uses purple squares;
Luna uses orange circles; DeepSeek uses grey plus markers; Fable uses berry
hexagons; Astra uses blue diamonds. These hues distinguish the model series
when twelve configurations appear together. Aggregate-metric charts continue
to use ochre and dark ink, with different markers or line patterns.
Labels use the complete version names from
`publication_data.MODEL_NAMES` and retain the effort level. Historical tier/effort
plots use the same names and colors. Claude Opus 5 has its
own brown color and star marker. Medium/high variants share a model marker, with
shade and line style distinguishing configurations. Effort curves use the model
identity while the horizontal axis encodes effort.

Use GPT-6 Astra, GPT-5.6 Luna, Claude Fable 5.1 and DeepSeek V4.1 Flash. Qwen labels
include the version and parameter count; the text specifies FP8 for 27B weights.
Keep versions visible in every standalone table and figure legend. Split table
headers over two lines when needed, rather than dropping the version.

## Reference lines

- Published frontier or construction reference: dark dashed line.
- Proven bound: dark dotted line.
- Expert/search or fixed-block construction: grey dash-dot line.

Reference curves sit behind model points. The overview's interval bars and bound
endpoints retain their specific interval encoding; uncertainty bars retain the
original statistical meaning. Colors for aggregate metrics (rather than model
identity) are separately named in `plot_style.METRICS`.

## Layout and legends

Legends sit below the plots; panel titles and axis wording use the same font
hierarchy. Dense family panels have two-line titles. The historical tier curve
is full width and moves family counts into legend brackets in A1/A2/A3 order,
keeping the points free of overlapping annotations. A dash means unmeasured.

Numerical values come from saved evaluation records and reference snapshots.
Styling changes preserve the scoring and averaging rules.
Large standalone previews retain larger presentation typography, while using the
same configuration identities and reference-line meanings.

## Appendix presentation

`appendix_style.tex` gives tasks, construction explanations and measured results
the shared white, warm-grey and ochre treatment. `appendix_redesign.py` produces
fourteen small mathematical illustrations and four worked-case diagrams. Their
sizes match the catalogue or case layouts; the large statistical plots retain
the shared physical width and typography. The combined ladder is also presented
in three readable groups using the same data. The appendix is assembled in
[`appendix/appendix.tex`](appendix/appendix.tex).
