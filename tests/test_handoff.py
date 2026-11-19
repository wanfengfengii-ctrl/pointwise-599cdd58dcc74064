from fractions import Fraction
import json
import sqlite3
import unittest

from evidence.packet_format import decode_packet, encode_packet
from review.decision import decide
from review.intake import admit
from tests.support import Workflow, result, row, sample, scenario, sign_rows


class TestHandoff(unittest.TestCase):
    def setUp(self):
        self.flow = Workflow(self)
        self.trial = self.flow.register()

    def _decide(self, left, right, limit):
        return decide(self.flow.accepted, self.flow.archive, left, right, limit)

    def test_full_rank_offline(self):
        readings = lambda u, v: (u + v, u, v)
        west = self.flow.prepare(self.trial, 'west', sign_rows('w', readings), ('V', 'U'))
        east = self.flow.prepare(self.trial, 'east', sign_rows('e', readings))
        self.flow.stop_sources()
        self.flow.reopen_center()
        report = self._decide(west, east, 0)
        self.assertEqual(result(report), (0, 0, True))
        self.assertEqual(tuple(parent.accepted_id for parent in report.draft.parents), (east, west))
        self.assertEqual(self.flow.archive_counts(), (1, 1))

    def test_shipped_evidence(self):
        east_revision, _ = self.flow.morning(self.trial)
        with self.assertRaises(KeyError):
            self.flow.issue('east', 'unknown-revision')
        self.assertEqual(
            self.flow.station_databases['east'].execute('SELECT count(*) FROM station_packets').fetchone()[0], 0
        )
        issued = self.flow.issue('east', east_revision)
        self.flow.stop_sources()
        self.flow.open_sources()
        shipped = self.flow.catalogs['east'].get(issued.envelope.issue_id)
        self.assertEqual(shipped, issued)
        wire = encode_packet(shipped)
        self.assertEqual(decode_packet(wire), issued)
        body = json.loads(wire)['body']
        self.assertEqual(set(body), {'channels', 'means', 'covariance'})
        self.assertNotIn('e-01', wire)
        accepted_id = self.flow.admit(shipped)
        self.flow.stop_sources()
        with self.assertRaises(sqlite3.ProgrammingError):
            self.flow.sources['east'].get_revision(east_revision)
        received = self.flow.accepted.get(accepted_id)
        self.assertEqual(received.packet, shipped)
        self.assertEqual(received.packet.envelope.revision_id, east_revision)

    def test_asymmetric_named_coordinates(self):
        readings = lambda u, v: (2 * u + v, u, v)
        east_revision = self.flow.freeze(self.trial, 'east', sign_rows('e', readings))
        west_revision = self.flow.freeze(self.trial, 'west', sign_rows('w', readings))
        east_packet = self.flow.issue('east', east_revision)
        west_packet = self.flow.issue('west', west_revision, ('V', 'U'))
        self.assertEqual(west_packet.moments.coordinates.channels, ('main', 'V', 'U'))
        self.assertEqual(west_packet.moments.covariance[0], (5, 1, 2))
        west = self.flow.admit(west_packet)
        east = self.flow.admit(east_packet)
        self.flow.stop_sources()
        report = self._decide(east, west, 0)
        self.assertEqual(result(report), (0, 0, True))
        self.assertEqual(report.draft.parents[1].issue_id, west_packet.envelope.issue_id)

    def test_zero_reference_rank(self):
        east = self.flow.prepare(self.trial, 'east', [row('e0', -1, 7, 9), row('e1', 1, 7, 9)])
        west = self.flow.prepare(self.trial, 'west', [row('w0', -2, 2, -3), row('w1', 2, 2, -3)])
        flat_east = self.flow.prepare(self.trial, 'east', [row('e2', 4, 7, 9)])
        flat_west = self.flow.prepare(self.trial, 'west', [row('w2', 9, 2, -3)])
        self.flow.stop_sources()
        self.assertEqual(result(self._decide(east, west, 9)), (5, 16, True))
        self.assertEqual(result(self._decide(east, west, 8)), (5, 16, False))
        self.assertEqual(result(self._decide(flat_east, flat_west, 0)), (0, 0, True))

    def test_dependent_reference_with_zero_residuals(self):
        cases = [
            (lambda u, p: (u, u, u), ('U', 'V')),
            (lambda u, p: (u, u, -u), ('V', 'U')),
            (lambda u, p: (u, 0, u), ('V', 'U')),
        ]
        selections = [
            (self.flow.prepare(self.trial, 'east', sign_rows('e', readings)),
             self.flow.prepare(self.trial, 'west', sign_rows('w', readings), order))
            for readings, order in cases
        ]
        self.flow.stop_sources()
        for index, (east, west) in enumerate(selections):
            with self.subTest(case=index):
                self.assertEqual(result(self._decide(east, west, 0)), (0, 0, True))

    def test_invalid_selection(self):
        rows = sample('morning')
        east = self.flow.prepare(self.trial, 'east', rows['east'])
        west = self.flow.prepare(self.trial, 'west', rows['west'])
        another_east = self.flow.prepare(self.trial, 'east', rows['east'])
        other_trial = self.flow.register(trial_id='other-trial')
        other_west = self.flow.prepare(other_trial, 'west', rows['west'])
        self.flow.stop_sources()
        with self.assertRaises(KeyError):
            self._decide(east, 'missing-packet', 4)
        with self.assertRaisesRegex(ValueError, 'complementary'):
            self._decide(east, another_east, 4)
        with self.assertRaisesRegex(ValueError, 'different trials'):
            self._decide(east, other_west, 4)
        for limit in (-1, True, 4.0, 'NaN', '1/0', None):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self._decide(east, west, limit)
        self.assertEqual(self.flow.archive_counts(), (0, 0))

    def test_packet_conflict(self):
        revision, _ = self.flow.morning(self.trial)
        issued = self.flow.issue('east', revision)
        original_wire = encode_packet(issued)
        accepted_id = self.flow.admit(issued)
        self.assertEqual(admit(self.flow.registry, self.flow.accepted, original_wire), accepted_id)
        modified = json.loads(original_wire)
        modified['body']['means'][0] = '1'
        with self.assertRaisesRegex(ValueError, 'conflicting packet'):
            admit(self.flow.registry, self.flow.accepted, json.dumps(modified))
        self.flow.stop_sources()
        self.flow.reopen_center()
        self.assertEqual(self.flow.accepted_count(), 1)
        old = self.flow.accepted.get(accepted_id)
        self.assertEqual(encode_packet(old.packet), original_wire)

    def test_replay_equivalent_packet(self):
        revision = self.flow.freeze(self.trial, 'east', sign_rows('e', lambda u, v: (2 * u + v, u, v)))
        issued = self.flow.issue('east', revision)
        original_wire = encode_packet(issued)
        accepted_id = self.flow.admit(issued)
        payload = json.loads(original_wire)
        indices = (0, 2, 1)
        body = payload['body']
        body['channels'] = [body['channels'][index] for index in indices]
        body['means'] = [body['means'][index] for index in indices]
        matrix = body['covariance']
        body['covariance'] = [[matrix[i][j] for j in indices] for i in indices]
        self.assertEqual(admit(self.flow.registry, self.flow.accepted, json.dumps(payload, indent=2)), accepted_id)
        self.assertEqual(encode_packet(self.flow.accepted.get(accepted_id).packet), original_wire)
        self.assertEqual(self.flow.accepted_count(), 1)

    def test_invalid_packet_body_and_envelope(self):
        east, _ = self.flow.morning(self.trial)
        wire = encode_packet(self.flow.issue('east', east))
        variants = []
        for key, invalid in (
            ('channels', ['main', 'U', 'U']), ('means', ['0', '0']),
            ('covariance', [['2', '1', '1'], ['0', '1', '1'], ['1', '1', '1']]),
            ('covariance', [['2', '1', '1'], ['1', '1/0', '1'], ['1', '1', '1']]),
            ('channels', ['main', 'U', 'unknown']),
        ):
            data = json.loads(wire)
            data['body'][key] = invalid
            variants.append(json.dumps(data))
        for key, invalid in (('version', True), ('version', 2), ('bench_id', 'external'), ('issue_id', '')):
            data = json.loads(wire)
            data[key] = invalid
            variants.append(json.dumps(data))
        variants.append(wire.replace('"version":1', '"version":1,"version":1'))
        for index, variant in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(ValueError):
                admit(self.flow.registry, self.flow.accepted, variant)
        self.assertEqual(self.flow.accepted_count(), 0)

    def test_conflicting_reference_pairs(self):
        east = self.flow.prepare(self.trial, 'east', sign_rows('e', lambda u, p: (p, u, u)))
        west = self.flow.prepare(self.trial, 'west', sign_rows('w', lambda u, p: (p, u, -u)), ('V', 'U'))
        self.flow.stop_sources()
        before = self.flow.archive_counts()
        with self.assertRaisesRegex(ValueError, 'conflicting reference covariance'):
            self._decide(east, west, 4)
        self.assertEqual(self.flow.archive_counts(), before)

    def test_infeasible_local_evidence(self):
        east_revision, west_revision = self.flow.morning(self.trial)
        east = self.flow.admit(self.flow.issue('east', east_revision))
        wire = encode_packet(self.flow.issue('west', west_revision))
        selections = []
        for name, matrix, error in (
            ('wrong-kernel', [[2, 1, 0], [1, 1, 1], [0, 1, 1]], 'outside the reference space'),
            ('negative-residual', [[0, 1, 1], [1, 1, 1], [1, 1, 1]], 'negative residual'),
        ):
            data = json.loads(wire)
            data['issue_id'] = name
            data['body']['covariance'] = matrix
            selections.append((admit(self.flow.registry, self.flow.accepted, json.dumps(data)), error))
        indefinite = [[2, 0, 0], [0, 1, 2], [0, 2, 1]]
        invalid_pair = []
        for bench in ('east', 'west'):
            data = json.loads(wire)
            data['issue_id'] = f'indefinite-{bench}'
            data['bench_id'] = bench
            data['revision_id'] = east_revision if bench == 'east' else west_revision
            data['body']['covariance'] = indefinite
            invalid_pair.append(admit(self.flow.registry, self.flow.accepted, json.dumps(data)))
        self.flow.stop_sources()
        for west, reason in selections:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self._decide(east, west, 4)
        with self.assertRaisesRegex(ValueError, 'positive semidefinite'):
            self._decide(*invalid_pair, 4)
        self.assertEqual(self.flow.archive_counts(), (0, 0))

    def test_dependent_reference_range(self):
        east_revision, west_revision = self.flow.morning(self.trial)
        left_packet = self.flow.issue('east', east_revision)
        right_packet = self.flow.issue('west', west_revision)
        left = self.flow.admit(left_packet)
        right = self.flow.admit(right_packet)
        self.flow.stop_sources()
        denied = self._decide(left, right, 3)
        boundary = self._decide(left, right, 4)
        self.assertEqual(result(denied), (2, 4, False))
        self.assertEqual(result(boundary), (2, 4, True))
        wire_body = json.loads(encode_packet(self.flow.accepted.get(left).packet))['body']
        joint = [['2', '1', '1'], ['1', '1', '1'], ['1', '1', '1']]
        self.assertEqual(wire_body, {'channels': ['main', 'U', 'V'], 'means': ['0', '0', '0'], 'covariance': joint})
        self.assertEqual(self.flow.accepted.get(right).packet.moments.covariance, ((2, 1, 1), (1, 1, 1), (1, 1, 1)))
        self.assertEqual(self.flow.archive_counts(), (2, 2))
        downstream = {'m': str(denied.draft.m), 'r': str(denied.draft.r),
                      'pass_at_3': denied.draft.passed, 'pass_at_4': boundary.draft.passed}
        scenario(
            'v6', {'sample': 'samples/morning.json', 'limits': [3, 4]},
            {'covariance': joint}, {'covariance': wire_body['covariance']},
            {'m': '2', 'r': '4', 'pass_at_3': False, 'pass_at_4': True}, downstream,
            ['evidence/moments.py', 'evidence/issue.py', 'review/bounds.py', 'review/decision.py'],
            'With the shared U canceled, equal residual signs give variance 0 and opposite signs give 4.',
        )

    def test_same_marginals_and_row_order(self):
        base = sign_rows('a', lambda u, p, q: (u + p, u, u), factors=3)
        changed = sign_rows('a', lambda u, p, q: (p + q, u, u), factors=3)
        west_rows = sign_rows('b', lambda u, q: (u + q, u, u))
        left_revision = self.flow.freeze(self.trial, 'east', base)
        change_revision = self.flow.freeze(self.trial, 'east', changed)
        first = self.flow.issue('east', left_revision)
        second = self.flow.issue('east', change_revision)
        self.assertEqual(first.moments.means, second.moments.means)
        self.assertEqual(tuple(first.moments.covariance[i][i] for i in range(3)), (2, 1, 1))
        self.assertEqual(tuple(second.moments.covariance[i][i] for i in range(3)), (2, 1, 1))
        self.assertEqual(first.moments.covariance[0][1:], (1, 1))
        self.assertEqual(second.moments.covariance[0][1:], (0, 0))
        east, corrected = self.flow.admit(first), self.flow.admit(second)
        west = self.flow.prepare(self.trial, 'west', west_rows)
        backwards_east = self.flow.prepare(self.trial, 'east', base[::-1])
        backwards_corrected = self.flow.prepare(self.trial, 'east', changed[::-1])
        backwards_west = self.flow.prepare(self.trial, 'west', west_rows[::-1], ('V', 'U'))
        self.flow.stop_sources()
        self.assertEqual(result(self._decide(east, west, 4)), (2, 4, True))
        self.assertEqual(result(self._decide(backwards_east, backwards_west, 4)), (2, 4, True))
        low = Fraction('6.82842712474619')
        high = Fraction('6.82842712474620')
        self.assertEqual(result(self._decide(corrected, west, low)), (4, 8, False))
        self.assertEqual(result(self._decide(backwards_corrected, backwards_west, low)), (4, 8, False))
        self.assertEqual(result(self._decide(corrected, west, high)), (4, 8, True))
