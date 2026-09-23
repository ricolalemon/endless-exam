# The Endless Exam website

The project website presents the leaderboard and illustrated explanations of all
fourteen mathematical construction families.

Website: https://ricolalemon.github.io/endless-exam/

## Run locally

This is a static HTML/CSS/JavaScript site with no frontend dependencies or build step.
From the repository root:

```bash
python3 -m http.server 4173 --bind 127.0.0.1 --directory website/dist
```

Open http://127.0.0.1:4173/ in your browser. The animations follow scrolling and
finish while their figures remain in view. A still-illustration toggle and the
system reduced-motion preference are supported.

## Data and illustrations

The leaderboard ranks configurations with and without tools together, with tool
access shown explicitly. Score bars share a zero-based linear scale that expands
to fit the data. They have no fixed background rail or endpoint label; the thin
mark indicates reference parity at 100, and higher scores extend past it. Evaluation settings for
both tracks are available below the table.

An interactive scatterplot below the leaderboard uses the same data: overall
score against mean output tokens per instance. Desktop labels use the leaderboard's
full model names, with effort and tool access on a second line where needed. Label
placement measures the rendered text to avoid clipping and overlapping names.
Hover or focus a point for exact values in a nearby tooltip; on mobile, tap a
point. Move away, tap outside, scroll or press Escape to dismiss it. Filled circles denote no tools and
filled diamonds denote code + web. Asterisks retain incomplete-usage accounting;
input tokens and external tool computation are not represented on the x axis.

`dist/results.json` contains the displayed scores, validity and reported token
usage. Token means divide reported output by all 69 instances, include reasoning,
and include all model turns in tool-assisted trajectories. Inputs and earlier
failed or superseded submissions are excluded. A star marks incomplete usage;
these reported values are lower bounds. The download also retains the separate
published-frontier ratios and accounting definitions.

`dist/story-data.js` contains verified small constructions and their explanations.
These illustrate the rules and are separate from the model results. Each family
also describes the larger parameter settings used in the benchmark.

After editing the construction text, regenerate the page and check the examples:

```bash
python3 website/render_constructions.py
python3 website/render_constructions.py --check
python3 website/check_animations.py
node --check website/dist/animations.js
```

Mathematical checks use the repository's benchmark dependencies and Node. They
verify all fourteen examples, 120 geometric configurations, the matrix identity,
graph distances and code-separation conditions.

## Hosting

GitHub Pages publishes `website/dist` from `main` through `.github/workflows/pages.yml`.
Changes to the site trigger automatic deployment. Assets use relative URLs so that
styles, scripts, data and the PDF resolve beneath `/endless-exam/`.
