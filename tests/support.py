from itertools import product
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.storage import ArchiveStore
from database import open_database
from evidence.catalog import PacketCatalog
from evidence.issue import issue
from evidence.packet_format import encode_packet
from review.accepted_store import AcceptedStore
from review.intake import admit
from station.intake import freeze
from station.sourcebook import SourceBook
from trial.protocols import register
from trial.registry import TrialRegistry


SAMPLES = Path(__file__).resolve().parents[1] / 'samples'


def sample(name):
    return json.loads((SAMPLES / f'{name}.json').read_text(encoding='utf-8'))


def row(run_id, main, u, v):
    return {'run_id': run_id, 'values': {'main': main, 'U': u, 'V': v}}


def sign_rows(prefix, readings, factors=2):
    return [
        row(f'{prefix}-{index}', *readings(*signs))
        for index, signs in enumerate(product((-1, 1), repeat=factors), start=1)
    ]


def result(report):
    return report.draft.m, report.draft.r, report.draft.passed


def scenario(case_id, inputs, expected, actual, downstream_expected, downstream_actual, paths, oracle):
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id,
        'input': inputs,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': paths,
        'oracle': oracle,
    }, ensure_ascii=False, sort_keys=True))


class Workflow:
    def __init__(self, test):
        self.test = test
        directory = TemporaryDirectory(prefix='hengjia-test-')
        test.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.open_sources()
        self.open_center()

    def _connect(self, name):
        database = open_database(self.root / f'{name}.sqlite')
        self.test.addCleanup(database.close)
        return database

    def open_sources(self):
        self.trial_db = self._connect('trials')
        self.registry = TrialRegistry(self.trial_db)
        self.registry.initialize()
        self.station_databases = {bench: self._connect(bench) for bench in ('east', 'west')}
        self.sources = {}
        self.catalogs = {}
        for bench, database in self.station_databases.items():
            self.sources[bench] = SourceBook(database)
            self.catalogs[bench] = PacketCatalog(database)
            self.sources[bench].initialize()
            self.catalogs[bench].initialize()

    def stop_sources(self):
        self.trial_db.close()
        for database in self.station_databases.values():
            database.close()

    def open_center(self):
        self.center_db = self._connect('center')
        self.accepted = AcceptedStore(self.center_db)
        self.archive = ArchiveStore(self.center_db)
        self.accepted.initialize()
        self.archive.initialize()

    def reopen_center(self):
        self.center_db.close()
        self.open_center()

    def register(self, **changes):
        spec = sample('trial')
        spec.update(changes)
        return register(self.registry, **spec)

    def freeze(self, trial_id, bench, rows, parent_id=None):
        return freeze(self.registry, self.sources[bench], trial_id, bench, rows, parent_id=parent_id)

    def issue(self, bench, revision_id, reference_order=None):
        return issue(self.sources[bench], self.catalogs[bench], revision_id, reference_order)

    def admit(self, packet):
        return admit(self.registry, self.accepted, encode_packet(packet))

    def prepare(self, trial_id, bench, rows, reference_order=None):
        revision = self.freeze(trial_id, bench, rows)
        return self.admit(self.issue(bench, revision, reference_order))

    def morning(self, trial_id):
        rows = sample('morning')
        return (
            self.freeze(trial_id, 'east', rows['east']),
            self.freeze(trial_id, 'west', rows['west']),
        )

    def archive_counts(self):
        report_count = self.center_db.execute('SELECT count(*) FROM archive_reports').fetchone()[0]
        receipt_count = self.center_db.execute('SELECT count(*) FROM archive_receipts').fetchone()[0]
        return report_count, receipt_count

    def revision_count(self, bench):
        return self.station_databases[bench].execute('SELECT count(*) FROM revisions').fetchone()[0]

    def accepted_count(self):
        return self.center_db.execute('SELECT count(*) FROM accepted_packets').fetchone()[0]
