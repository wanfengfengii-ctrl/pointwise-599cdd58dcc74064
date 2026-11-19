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


def solve_variance_range(pair: ComparablePair):
    return VarianceRange(pair.left_variance + pair.right_variance, Fraction(0))
