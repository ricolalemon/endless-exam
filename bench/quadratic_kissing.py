"""Exact kissing configurations over Z[sqrt(3)], for opted-in instances.

Coordinates are integer coefficient pairs [a,b], denoting a+b*sqrt(3).
Matrix arithmetic stays within int64 for d<=16 and |a|,|b|<=1000. The
sign comparisons that require squaring use Python integers, not int64 or
floating-point tolerances. No symbolic expressions are evaluated.
"""
import numpy as np

MAX_POINTS = 20000
COEFFICIENT_LIMIT = 1000


def sign(a, b):
    """Sign of a+b*sqrt(3), including cancellation beyond float precision."""
    a, b = int(a), int(b)
    if b == 0:
        return (a > 0) - (a < 0)
    if a == 0 or (a > 0) == (b > 0):
        return 1 if b > 0 else -1
    difference = a * a - 3 * b * b
    return ((difference > 0) - (difference < 0)) * (1 if a > 0 else -1)


def positive(a, b):
    """Exact array sign test; all ambiguous cases use arbitrary precision."""
    result = ((a >= 0) & (b >= 0)) & ((a != 0) | (b != 0))
    opposite = ((a > 0) & (b < 0)) | ((a < 0) & (b > 0))
    for i in np.flatnonzero(opposite):
        result[i] = sign(a[i], b[i]) > 0
    return result


def verify(params, answer):
    d = params.get('d')
    if params.get('representation') != 'quadratic':
        return False, 0, 'quadratic coordinates are not enabled for this instance'
    if type(d) is not int or not 1 <= d <= 16:
        return False, 0, 'dimension must be an integer from 1 to 16'
    if not isinstance(answer, dict) or set(answer) != {'quadratic_vectors'}:
        return False, 0, 'expected one quadratic_vectors object'
    spec = answer['quadratic_vectors']
    if not isinstance(spec, dict) or set(spec) != {'radicand', 'vectors'}:
        return False, 0, 'quadratic_vectors requires radicand and vectors'
    if type(spec['radicand']) is not int or spec['radicand'] != 3:
        return False, 0, 'the supported radicand is 3'
    vectors = spec['vectors']
    if not isinstance(vectors, list) or not 1 <= len(vectors) <= MAX_POINTS:
        return False, 0, f'expected 1..{MAX_POINTS} vectors'
    for vector in vectors:
        if not isinstance(vector, list) or len(vector) != d:
            return False, 0, f'each vector must contain {d} coefficient pairs'
        for pair in vector:
            if (not isinstance(pair, list) or len(pair) != 2
                    or any(type(c) is not int or abs(c) > COEFFICIENT_LIMIT for c in pair)):
                return False, 0, 'each coefficient pair must be two integers in [-1000,1000]'
    data = np.array(vectors, dtype=np.int64)
    a, b = data[:, :, 0], data[:, :, 1]
    if np.any(~np.any((a != 0) | (b != 0), axis=1)):
        return False, 0, 'the zero vector is not allowed'
    # The squared norm is na+nb*sqrt(3). Nonzero coefficient vectors have
    # positive norms because 1 and sqrt(3) are linearly independent over Q.
    na = (a * a + 3 * b * b).sum(axis=1)
    nb = 2 * (a * b).sum(axis=1)
    count = len(vectors)
    step = max(1, min(128, 300000 // count))
    for start in range(0, count, step):
        end = min(start + step, count)
        i, j = np.nonzero(np.arange(count)[None, :] > np.arange(start, end)[:, None])
        ga = (a[start:end] @ a.T + 3 * (b[start:end] @ b.T))[i, j]
        gb = (a[start:end] @ b.T + b[start:end] @ a.T)[i, j]
        global_i = i + start
        # A positive dot product violates 60 degrees precisely when
        # 4*dot^2 - norm_i^2*norm_j^2 is positive in Q(sqrt(3)).
        ha = (4 * (ga * ga + 3 * gb * gb)
              - na[global_i] * na[j] - 3 * nb[global_i] * nb[j])
        hb = 8 * ga * gb - na[global_i] * nb[j] - nb[global_i] * na[j]
        bad = positive(ga, gb) & positive(ha, hb)
        if np.any(bad):
            at = int(np.flatnonzero(bad)[0])
            return False, 0, f'vectors {global_i[at]} and {j[at]} are less than 60 degrees apart'
    return True, count, ''
