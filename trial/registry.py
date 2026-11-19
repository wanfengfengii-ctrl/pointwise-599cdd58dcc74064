import json

from database import write_transaction
from trial.roles import require_identifier
from trial.specification import build_trial_spec


def _encode_spec(spec):
    return json.dumps({
        'condition': spec.condition,
        'left_bench': spec.roles.left_bench,
        'right_bench': spec.roles.right_bench,
        'references': spec.roles.references,
        'units': {
            name: {'unit': convention.unit, 'inputs': convention.inputs}
            for name, convention in spec.units
        },
    }, sort_keys=True, separators=(',', ':'))


class TrialRegistry:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS trials (
                trial_id TEXT PRIMARY KEY NOT NULL,
                specification TEXT NOT NULL
            )
        ''')

    def save(self, spec):
        payload = _encode_spec(spec)
        with write_transaction(self.connection):
            saved = self.connection.execute(
                'SELECT specification FROM trials WHERE trial_id = ?', (spec.trial_id,)
            ).fetchone()
            if saved is None:
                self.connection.execute(
                    'INSERT INTO trials (trial_id, specification) VALUES (?, ?)',
                    (spec.trial_id, payload),
                )
            elif saved[0] != payload:
                raise ValueError('conflicting trial registration')
        return spec.trial_id

    def get(self, trial_id):
        trial_id = require_identifier(trial_id, 'trial identifier')
        record = self.connection.execute(
            'SELECT specification FROM trials WHERE trial_id = ?', (trial_id,)
        ).fetchone()
        if record is None:
            raise KeyError(trial_id)
        return build_trial_spec(trial_id, **json.loads(record[0]))
