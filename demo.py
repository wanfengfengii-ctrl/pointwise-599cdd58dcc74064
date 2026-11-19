from contextlib import ExitStack, closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.export import export_report
from archive.readback import read
from archive.storage import ArchiveStore
from database import open_database
from evidence.catalog import PacketCatalog
from evidence.issue import issue
from evidence.packet_format import encode_packet
from review.accepted_store import AcceptedStore
from review.decision import decide
from review.intake import admit
from station.intake import freeze
from station.sourcebook import SourceBook
from trial.protocols import register
from trial.registry import TrialRegistry


def load_sample(name):
    location = Path(__file__).with_name('samples') / f'{name}.json'
    return json.loads(location.read_text(encoding='utf-8'))


def open_registry(stack, root):
    database = stack.enter_context(closing(open_database(root / 'trials.sqlite')))
    registry = TrialRegistry(database)
    registry.initialize()
    return registry


def open_station(stack, root, bench):
    database = stack.enter_context(closing(open_database(root / f'{bench}.sqlite')))
    source, catalog = SourceBook(database), PacketCatalog(database)
    source.initialize()
    catalog.initialize()
    return source, catalog


def receive_revision(registry, accepted, catalog, packet):
    saved = catalog.get(packet.envelope.issue_id)
    return admit(registry, accepted, encode_packet(saved))


def run_morning(root, accepted):
    rows = load_sample('morning')
    with ExitStack() as stack:
        registry = open_registry(stack, root)
        trial_id = register(registry, **load_sample('trial'))
        revisions, selections = {}, {}
        for bench, reference_order in (('east', None), ('west', ('V', 'U'))):
            source, catalog = open_station(stack, root, bench)
            revision = freeze(registry, source, trial_id, bench, rows[bench])
            revisions[bench] = revision
            packet = issue(source, catalog, revision, reference_order=reference_order)
            selections[bench] = receive_revision(registry, accepted, catalog, packet)
    return trial_id, revisions['east'], selections['east'], selections['west']


def run_correction(root, accepted, trial_id, parent):
    with ExitStack() as stack:
        registry = open_registry(stack, root)
        source, catalog = open_station(stack, root, 'east')
        revision = freeze(
            registry, source, trial_id, 'east', load_sample('correction'), parent_id=parent
        )
        return receive_revision(registry, accepted, catalog, issue(source, catalog, revision))


def main():
    with TemporaryDirectory(prefix='hengjia-drift-') as directory:
        root = Path(directory)
        center = root / 'center.sqlite'
        with closing(open_database(center)) as database:
            accepted, archive = AcceptedStore(database), ArchiveStore(database)
            accepted.initialize()
            archive.initialize()
            trial_id, original_revision, east, west = run_morning(root, accepted)
            original = decide(accepted, archive, east, west, 3)
            boundary = decide(accepted, archive, east, west, 4)
            changed = run_correction(root, accepted, trial_id, original_revision)
            corrected = decide(accepted, archive, changed, west, 7)

        with closing(open_database(center)) as database:
            accepted, archive = AcceptedStore(database), ArchiveStore(database)
            accepted.initialize()
            archive.initialize()
            saved = read(archive, original.report_id)
            if saved != original or read(archive, corrected.report_id) != corrected:
                raise RuntimeError('重开后领取的报告与原定稿不一致')
            if accepted.get(saved.draft.parents[0].accepted_id).packet.envelope.revision_id != original_revision:
                raise RuntimeError('历史报告未绑定原修订')
            for label, report in (('初版', original), ('边界复核', boundary), ('勘误版', corrected)):
                handoff = json.loads(export_report(archive, report.report_id))
                shown = {key: handoff[key] for key in ('limit', 'range', 'passed')}
                print(label, json.dumps(shown, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
