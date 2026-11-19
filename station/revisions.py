from dataclasses import dataclass
from fractions import Fraction

from station.rows import RunRow
from trial.roles import MAIN_CHANNEL, require_identifier


@dataclass(frozen=True)
class FrozenRevision:
    revision_id: str
    trial_id: str
    bench_id: str
    parent_id: str | None
    channels: tuple[str, str, str]
    rows: tuple[RunRow, ...]


def validate_correction_parent(parent, trial_id, bench_id):
    if (parent.trial_id, parent.bench_id) != (trial_id, bench_id):
        raise ValueError('correction parent belongs to a different trial or bench')


def build_revision(revision_id, trial_id, bench_id, parent_id, channels, rows):
    require_identifier(revision_id, 'revision identifier')
    require_identifier(trial_id, 'trial identifier')
    require_identifier(bench_id, 'bench identifier')
    if parent_id is not None:
        require_identifier(parent_id, 'parent revision identifier')
    channels = tuple(require_identifier(name, 'channel') for name in channels)
    if len(channels) != 3 or channels[0] != MAIN_CHANNEL or len(set(channels)) != 3:
        raise ValueError('invalid frozen channels')
    rows = tuple(rows)
    if not rows:
        raise ValueError('the revision must contain a complete queue')
    seen = set()
    for row in rows:
        if not isinstance(row, RunRow) or len(row.values) != len(channels):
            raise ValueError('incomplete frozen run')
        if any(not isinstance(value, Fraction) for value in row.values):
            raise ValueError('frozen readings must be rational')
        run_id = require_identifier(row.run_id, 'run identifier')
        if run_id in seen:
            raise ValueError(f'duplicate run identifier: {run_id}')
        seen.add(run_id)
    return FrozenRevision(revision_id, trial_id, bench_id, parent_id, channels, rows)
