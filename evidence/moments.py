from dataclasses import dataclass
from fractions import Fraction

from evidence.coordinates import (
    ChannelCoordinates, channel_permutation, reorder_covariance, reorder_vector,
)


@dataclass(frozen=True)
class LocalMoments:
    coordinates: ChannelCoordinates
    means: tuple[Fraction, ...]
    covariance: tuple[tuple[Fraction, ...], ...]

    def in_order(self, coordinates):
        permutation = channel_permutation(self.coordinates, coordinates)
        return LocalMoments(
            coordinates,
            reorder_vector(self.means, permutation),
            reorder_covariance(self.covariance, permutation),
        )


def compute_population_moments(revision):
    channels = revision.channels
    coordinates = ChannelCoordinates(channels[0], channels[1:])
    count = len(revision.rows)
    if not count or any(len(row.values) != len(channels) for row in revision.rows):
        raise ValueError('moments require a nonempty complete revision')
    columns = tuple(zip(*(row.values for row in revision.rows), strict=True))
    means = tuple(sum(column, Fraction(0)) / count for column in columns)
    variances = tuple(
        sum(((value - mean) ** 2 for value in column), Fraction(0)) / count
        for column, mean in zip(columns, means, strict=True)
    )
    covariance = tuple(
        tuple(variance if row == column else Fraction(0) for column in range(len(channels)))
        for row, variance in enumerate(variances)
    )
    return LocalMoments(coordinates, means, covariance)
