from dataclasses import dataclass

from trial.roles import require_identifier


@dataclass(frozen=True)
class ChannelCoordinates:
    main: str
    references: tuple[str, str]

    def __post_init__(self):
        if not isinstance(self.references, tuple) or len(self.references) != 2:
            raise ValueError('coordinates need two references')
        names = tuple(require_identifier(name, 'channel identifier') for name in self.channels)
        if len(set(names)) != len(names):
            raise ValueError('coordinates must have distinct channel identifiers')

    @property
    def channels(self):
        return (self.main, *self.references)


def channel_permutation(source, target):
    if source.main != target.main or set(source.references) != set(target.references):
        raise ValueError('incompatible channel coordinates')
    return tuple(source.channels.index(name) for name in target.channels)


def reorder_vector(vector, permutation):
    return tuple(vector[index] for index in permutation)


def reorder_covariance(matrix, permutation):
    return tuple(reorder_vector(matrix[index], permutation) for index in permutation)
