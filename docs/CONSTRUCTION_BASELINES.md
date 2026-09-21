# Construction baselines

The version-1 baselines combine established constructions and computational
search. This document describes the additional algebraic calibration applied to
five task variants. The diagnosis used model results already collected; the
construction algorithms use parameters and existing mathematical libraries, not
the formal model answers.

## Methods

- **Corners:** translate ternary digit sets with digits zero and one, and use
  weighted greedy progression-free difference sets with exponents 0, 1, 2 and 4
  and seeds 0-7. Lift a difference set D to the grid of pairs with x-y in D.
- **Spherical codes:** combine signed supports of weights 3, 4 and 5, binary
  sign vectors and coordinate axes. Use exact-angle greedy packing with seeds
  0-7; seed 0 uses lexicographic order. Compatibility is checked with integer
  dot products.
- **Linear-equation-free sets:** block all six roles in a forbidden triple and
  use ascending, descending and 16 fixed random orders.
- **Finite-field AP-free sets:** use 64 greedy orders and, in even dimensions,
  products of two-dimensional ingredients. Published q=5 references are retained.
- **Trifference:** check the existing reference pool and the rank-2, length-4
  projective code under the Reed-Solomon composition rule. Stronger formal model
  answers are not added to the reference pool for their own evaluation.

## Calibration and selection

The 17 calibration parameter settings in `construction_baselines.CALIBRATION`
are disjoint from the 20 formal settings. The methods were run first on the
calibration settings and then under the same schedule on the formal settings.
Only strict improvements over the preceding effective baseline were retained,
and every retained object passed both mathematical verifiers. Eight scoring
references improved; all models are evaluated against the same resulting values.

These algebraic baselines are separate from the timed 10/600-second searches.
The original search results and model responses remain unchanged. The
[data guide](DATA.md#construction-baselines) links the objects, calibration
measurements, before/after reference values and collection hashes.

## Mathematical basis

The difference-set lift follows the usual progression-free construction: a
corner in the grid would create a three-term progression in D. Cartesian
products preserve progression-freeness coordinatewise. For binary sign vectors,
the dot product equals the dimension minus twice the Hamming distance; other
signed supports use the same exact angle inequality. The trifference ingredient
uses the four projective points of PG(1,3), with its composition checked by the
certificate verifier.

For background on progression-free difference sets and corners, see
[MIT 18.225, Lecture 8](https://ocw.mit.edu/courses/18-225-graph-theory-and-additive-combinatorics-fall-2023/resources/lecture-8-szemeredi2019s-graph-regularity-lemma-iii-further-applications/).
