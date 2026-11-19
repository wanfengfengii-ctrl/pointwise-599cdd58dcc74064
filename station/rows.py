from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from trial.roles import require_identifier
from trial.units import normalize_reading


@dataclass(frozen=True)
class RunRow:
    run_id: str
    values: tuple[Fraction, ...]


def normalize_row(spec, raw_row):
    if not isinstance(raw_row, Mapping) or set(raw_row) != {'run_id', 'values'}:
        raise ValueError('each row needs run_id and values')
    run_id = require_identifier(raw_row['run_id'], 'run identifier')
    channels = spec.expected_channels()
    values = raw_row['values']
    if not isinstance(values, Mapping) or set(values) != set(channels):
        raise ValueError(f'incomplete channels in run {run_id}')
    normalized = []
    for channel in channels:
        try:
            normalized.append(normalize_reading(values[channel], spec.unit_for(channel)))
        except ValueError as error:
            raise ValueError(f'invalid reading in run {run_id}, channel {channel}: {error}') from error
    return RunRow(run_id, tuple(normalized))


def normalize_queue(spec, raw_rows):
    if not isinstance(raw_rows, (list, tuple)) or not raw_rows:
        raise ValueError('a nonempty complete run queue is required')
    rows = []
    seen = set()
    for raw_row in raw_rows:
        row = normalize_row(spec, raw_row)
        if row.run_id in seen:
            raise ValueError(f'duplicate run identifier: {row.run_id}')
        rows.append(row)
        seen.add(row.run_id)
    return tuple(rows)
