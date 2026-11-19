"""Run the morning and corrected handoffs using the delivered samples."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.storage import ArchiveStore
from database import open_database
from demo import run_correction, run_morning
from review.accepted_store import AcceptedStore
from review.decision import decide


def station_matrix(accepted, accepted_id):
    record = accepted.get(accepted_id)
    moments = record.packet.moments.in_order(record.coordinates)
    return tuple(tuple(str(value) for value in row) for row in moments.covariance)


def report_values(accepted, archive, east, west, limit):
    draft = decide(accepted, archive, west, east, limit).draft
    return str(draft.m), str(draft.r), draft.passed


def observe(root):
    with closing(open_database(root / 'center.sqlite')) as database:
        accepted, archive = AcceptedStore(database), ArchiveStore(database)
        accepted.initialize()
        archive.initialize()
        trial, revision, east, west = run_morning(root, accepted)
        original = report_values(accepted, archive, east, west, 3)
        boundary = report_values(accepted, archive, east, west, 4)
        corrected = run_correction(root, accepted, trial, revision)
        correction = report_values(accepted, archive, corrected, west, 5)
        return {
            '初版甲件': station_matrix(accepted, east),
            '勘误甲件': station_matrix(accepted, corrected),
            '初版上限3': original,
            '初版上限4': boundary,
            '勘误上限5': correction,
        }


def main():
    expected = {
        '初版甲件': (('2', '1', '1'), ('1', '1', '1'), ('1', '1', '1')),
        '勘误甲件': (('2', '0', '0'), ('0', '1', '1'), ('0', '1', '1')),
        '初版上限3': ('2', '4', False),
        '初版上限4': ('2', '4', True),
        '勘误上限5': ('4', '8', False),
    }
    with TemporaryDirectory(prefix='hengjia-incident-') as directory:
        actual = observe(Path(directory))
    for label, value in actual.items():
        if value != expected[label]:
            print(f'{label} 实际 {value!r}，预期 {expected[label]!r}')
    if actual != expected:
        print('VARIANCE_RANGE_WRONG')
        return 1
    print('初版区间 [0,4]，上限 3 拒绝放行、4 放行。勘误区间 [4−√8,4+√8]，上限 5 拒绝放行。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
