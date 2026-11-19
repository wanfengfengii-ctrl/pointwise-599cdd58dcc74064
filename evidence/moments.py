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
    centered = tuple(
        tuple(value - mean for value in column)
        for column, mean in zip(columns, means, strict=True)
    )
    covariance = tuple(
        tuple(
            sum((left * right for left, right in zip(centered[row], centered[column])),
                Fraction(0)) / count
            for column in range(len(channels))
        )
        for row in range(len(channels))
    )
    return LocalMoments(coordinates, means, covariance)
