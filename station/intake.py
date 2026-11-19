from uuid import uuid4

from station.revisions import build_revision, validate_correction_parent
from station.rows import normalize_queue
from trial.protocols import get_trial


def freeze(registry, source, trial_id, bench_id, rows, parent_id=None):
    spec = get_trial(registry, trial_id)
    spec.roles.role_for(bench_id)
    if parent_id is not None:
        parent = source.get_revision(parent_id)
        validate_correction_parent(parent, trial_id, bench_id)
    normalized = normalize_queue(spec, rows)
    revision = build_revision(
        uuid4().hex, trial_id, bench_id, parent_id, spec.expected_channels(), normalized
    )
    return source.save_revision(revision)
