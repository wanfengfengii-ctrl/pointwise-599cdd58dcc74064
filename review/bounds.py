from dataclasses import dataclass
from fractions import Fraction

from review.compatibility import ComparablePair


@dataclass(frozen=True)
class VarianceRange:
    m: Fraction
    r: Fraction

    def upper_at_most(self, limit: Fraction):
        gap = limit - self.m
        return gap >= 0 and gap * gap >= self.r


def _require_positive_semidefinite(block):
    first, second = block[0][0], block[1][1]
    if min(first, second) < 0 or first * second < block[0][1] ** 2:
        raise ValueError('reference covariance must be positive semidefinite')


def _require_in_reference_space(block, cross):
    first = (block[0][0], block[0][1])
    second = (block[0][1], block[1][1])
    if first[0] * second[1] != first[1] * second[0]:
        return
    column = first if first != (0, 0) else second
    if column == (0, 0):
        if cross != (0, 0):
            raise ValueError('main-reference covariance outside the reference space')
    elif cross[0] * column[1] != cross[1] * column[0]:
        raise ValueError('main-reference covariance outside the reference space')


def _pseudo_quadratic(block, left, right):
    # Exact left^T block^+ right for a symmetric 2x2 reference block.
    first, offdiag, second = block[0][0], block[0][1], block[1][1]
    if (first, offdiag, second) == (0, 0, 0):
        return Fraction(0)
    determinant = first * second - offdiag * offdiag
    if determinant:
        adjugate = (
            second * left[0] * right[0]
            - offdiag * (left[0] * right[1] + left[1] * right[0])
            + first * left[1] * right[1]
        )
        return adjugate / determinant
    trace = first + second
    direct = (
        first * left[0] * right[0]
        + offdiag * (left[0] * right[1] + left[1] * right[0])
        + second * left[1] * right[1]
    )
    return direct / (trace * trace)


def _residual_variance(block, variance, cross):
    _require_in_reference_space(block, cross)
    residual = variance - _pseudo_quadratic(block, cross, cross)
    if residual < 0:
        raise ValueError('main channel has negative residual variance')
    return residual


def solve_variance_range(pair: ComparablePair):
    reference = pair.reference
    _require_positive_semidefinite(reference)
    left_residual = _residual_variance(reference, pair.left_variance, pair.left_cross)
    right_residual = _residual_variance(reference, pair.right_variance, pair.right_cross)
    shared = _pseudo_quadratic(reference, pair.left_cross, pair.right_cross)
    middle = pair.left_variance + pair.right_variance - 2 * shared
    return VarianceRange(middle, 4 * left_residual * right_residual)
