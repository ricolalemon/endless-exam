"""A verified AP-free point-grid illustration and its reference-ratio calculation."""
import itertools
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import plot_style as S
from openceiling import FAMILIES
from crosscheck import apfree_q2


def check_optimum(q, n, reference):
    """Exclude h+1 points by exact search after fixing an affine frame.

    Here h+1 > q^(n-1), so every putative larger set spans the whole space
    and can be mapped to contain 0,e1,...,en. Arithmetic progressions are
    invariant under that affine map. All extensions of the frame are tested.
    """
    space = list(itertools.product(range(q), repeat=n))
    index = {p: i for i, p in enumerate(space)}
    target = reference + 1
    assert target > q ** (n-1)
    inv2 = pow(2, -1, q)
    forbidden = {}
    for a, b in itertools.combinations(range(len(space)), 2):
        x, y = space[a], space[b]
        thirds = {tuple((2*u-v) % q for u, v in zip(x, y)),
                  tuple((2*v-u) % q for u, v in zip(x, y)),
                  tuple((u+v)*inv2 % q for u, v in zip(x, y))}
        forbidden[a, b] = sum(1 << index[p] for p in thirds)
    def blocked(a, b):
        return forbidden[min(a, b), max(a, b)]
    chosen = [index[(0,) * n]] + [index[tuple(int(i == j) for i in range(n))] for j in range(n)]
    candidates = (1 << len(space))-1
    for v in chosen:
        candidates &= ~(1 << v)
    for a, b in itertools.combinations(chosen, 2):
        candidates &= ~blocked(a, b)
    nodes = 0
    def extend(selected, available):
        nonlocal nodes
        nodes += 1
        if len(selected) == target:
            return selected
        while len(selected) + available.bit_count() >= target:
            bit = available & -available
            v = bit.bit_length()-1
            available ^= bit
            remaining = available
            for w in selected:
                remaining &= ~blocked(v, w)
            found = extend(selected + [v], remaining)
            if found is not None:
                return found
        return None
    assert extend(chosen, candidates) is None
    return {'optimal_size': reference, 'excluded_size': target, 'search_nodes': nodes,
            'method': 'Exhaustive extension search after affine-frame normalisation.',
            'normalised_affine_frame': [list(space[v]) for v in chosen]}


def collect_example():
    q, n = 5, 2
    # Translate the six-point conic x^2 - 2y^2 = 1, then remove one point.
    reference_points = sorted(((x+2) % q, (y+2) % q) for x, y in itertools.product(range(q), repeat=2)
                              if (x*x - 2*y*y) % q == 1)
    points = [p for p in reference_points if p != (4, 0)]
    params = {'q': q, 'n': n}
    checks = {}
    for label, values in [('candidate', points), ('reference', reference_points)]:
        answer = [''.join(map(str, p)) for p in values]
        primary = FAMILIES['apfree_q'].verify(params, answer)
        independent = apfree_q2(params, answer)
        assert primary[:2] == independent == (True, len(values))
        checks[label] = {'primary': list(primary), 'independent': list(independent)}
    checks['optimal_reference'] = check_optimum(q, n, len(reference_points))
    return {'illustrative': True, 'family': 'apfree_q', 'params': params,
            'points': points, 'reference_points': reference_points, 'objective': len(points),
            'reference': len(reference_points), 'reference_type': 'small-instance optimum',
            'ratio': len(points)/len(reference_points), 'verification': checks}


def main():
    data = collect_example()
    q, n = data['params']['q'], data['params']['n']
    S.apply()
    fig = plt.figure(figsize=(S.WIDTH, 1.85))
    grid = fig.add_axes([.045, .28, .21, .48])
    check = fig.add_axes([.33, .20, .26, .55])
    score = fig.add_axes([.685, .20, .30, .55])
    for x, title in zip([.15, .46, .835], ['1  Construct', '2  Verify', '3  Score']):
        fig.text(x, .945, title, ha='center', va='top', fontsize=S.TITLE, weight='bold')
    fig.text(.15, .815, rf'AP-free set in $\mathbb{{F}}_{{{q}}}^{{{n}}}$', ha='center', fontsize=S.LABEL)
    space = list(itertools.product(range(q), repeat=2))
    grid.scatter(*zip(*space), s=14, color=S.T.NEUTRAL, zorder=1)
    grid.scatter(*zip(*data['points']), s=34, color=S.T.PRIMARY, zorder=3)
    grid.set(xlim=(-.4, q-.6), ylim=(-.4, q-.6), aspect='equal')
    grid.set_xticks(range(q)); grid.set_yticks(range(q)); grid.spines[:].set_visible(False)
    grid.tick_params(length=0, labelsize=S.TICK)
    fig.text(.15, .115, f"{data['objective']} selected points", ha='center', fontsize=S.TICK)
    check.axis('off'); score.axis('off')
    check.text(.5, .96, 'For any three distinct', ha='center', fontsize=S.TICK)
    check.text(.5, .78, r'selected points $x,y,z$', ha='center', fontsize=S.TICK)
    check.text(.5, .54, r'$x+z\ne 2y$', ha='center', fontsize=9.5)
    check.text(.5, .34, f'coordinate-wise, modulo {q}', ha='center', fontsize=6.1)
    check.text(.5, .04, f"Valid points: {data['objective']}", ha='center', fontsize=9.5)
    score.text(.5, .86, f"Reference: {data['reference']} points", ha='center', fontsize=S.LABEL)
    score.text(.5, .62, 'Relative quality', ha='center', fontsize=S.TICK)
    score.text(.5, .36, rf"$\frac{{{data['objective']}}}{{{data['reference']}}}\approx {data['ratio']:.3f}$",
               ha='center', va='center', fontsize=13, color=S.T.OCHRE)
    score.text(.5, .02, r'Invalid construction $\to 0$', ha='center', fontsize=S.NOTE)
    for x0, x1 in [(.269, .319), (.61, .665)]:
        fig.add_artist(FancyArrowPatch((x0, .50), (x1, .50), transform=fig.transFigure,
                       arrowstyle='-|>', mutation_scale=9, linewidth=.9, color=S.T.MUTED))
    S.save(fig, 'fig0_framework')
    (HERE/'tables/framework_example.json').write_text(json.dumps(data, indent=2)+'\n')


if __name__ == '__main__':
    main()
