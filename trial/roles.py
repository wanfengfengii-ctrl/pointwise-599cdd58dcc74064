from dataclasses import dataclass
from enum import Enum


MAIN_CHANNEL = 'main'


def require_identifier(value, description):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f'invalid {description}')
    return value


class BenchRole(str, Enum):
    LEFT = 'left'
    RIGHT = 'right'


@dataclass(frozen=True)
class TrialRoles:
    left_bench: str
    right_bench: str
    references: tuple[str, str]

    def role_for(self, bench_id):
        if bench_id == self.left_bench:
            return BenchRole.LEFT
        if bench_id == self.right_bench:
            return BenchRole.RIGHT
        raise ValueError('bench is outside the trial')


def validate_roles(left_bench, right_bench, references):
    left_bench = require_identifier(left_bench, 'left bench')
    right_bench = require_identifier(right_bench, 'right bench')
    if left_bench == right_bench:
        raise ValueError('benches must be distinct')
    if not isinstance(references, (list, tuple)) or len(references) != 2:
        raise ValueError('exactly two references are required')
    names = tuple(require_identifier(name, 'reference') for name in references)
    if names[0] == names[1] or MAIN_CHANNEL in names:
        raise ValueError('reference identifiers must be distinct from each other and main')
    return TrialRoles(left_bench, right_bench, tuple(sorted(names)))
