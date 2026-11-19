from dataclasses import dataclass
from fractions import Fraction

from review.accepted_store import AcceptedPacket
from trial.roles import BenchRole


@dataclass(frozen=True)
class ComparablePair:
    left: AcceptedPacket
    right: AcceptedPacket
    reference: tuple[tuple[Fraction, ...], ...]
    left_cross: tuple[Fraction, ...]
    right_cross: tuple[Fraction, ...]
    left_variance: Fraction
    right_variance: Fraction


def require_common_reference(left_matrix, right_matrix):
    left_block = tuple(row[1:] for row in left_matrix[1:])
    right_block = tuple(row[1:] for row in right_matrix[1:])
    if left_block != right_block:
        raise ValueError('conflicting reference covariance')
    return left_block


def align_accepted_pair(first, second):
    if first.packet.envelope.trial_id != second.packet.envelope.trial_id:
        raise ValueError('packets belong to different trials')
    if {first.role, second.role} != {BenchRole.LEFT, BenchRole.RIGHT}:
        raise ValueError('packets require complementary bench roles')
    left, right = (first, second) if first.role == BenchRole.LEFT else (second, first)
    target = left.coordinates
    left_matrix = left.packet.moments.in_order(target).covariance
    right_matrix = right.packet.moments.in_order(target).covariance
    reference = require_common_reference(left_matrix, right_matrix)
    return ComparablePair(
        left, right, reference, left_matrix[0][1:], right_matrix[0][1:],
        left_matrix[0][0], right_matrix[0][0],
    )
