import json

from database import write_transaction
from station.revisions import build_revision
from station.rows import RunRow
from trial.roles import require_identifier
from trial.units import parse_rational


class SourceBook:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS revisions (
                revision_id TEXT PRIMARY KEY NOT NULL,
                trial_id TEXT NOT NULL,
                bench_id TEXT NOT NULL,
                parent_id TEXT REFERENCES revisions(revision_id),
                channels TEXT NOT NULL,
                queue TEXT NOT NULL
            )
        ''')

    def save_revision(self, revision):
        queue = [[row.run_id, [str(value) for value in row.values]] for row in revision.rows]
        with write_transaction(self.connection):
            self.connection.execute('''
                INSERT INTO revisions (revision_id, trial_id, bench_id, parent_id, channels, queue)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                revision.revision_id, revision.trial_id, revision.bench_id, revision.parent_id,
                json.dumps(revision.channels), json.dumps(queue),
            ))
        return revision.revision_id

    def get_revision(self, revision_id):
        revision_id = require_identifier(revision_id, 'revision identifier')
        record = self.connection.execute('''
            SELECT trial_id, bench_id, parent_id, channels, queue
            FROM revisions WHERE revision_id = ?
        ''', (revision_id,)).fetchone()
        if record is None:
            raise KeyError(revision_id)
        trial_id, bench_id, parent_id, channels, payload = record
        rows = tuple(
            RunRow(run_id, tuple(parse_rational(value) for value in values))
            for run_id, values in json.loads(payload)
        )
        return build_revision(revision_id, trial_id, bench_id, parent_id, json.loads(channels), rows)
