from fractions import Fraction
import json
import sqlite3
import unittest

from archive.export import export_report
from archive.readback import read
from evidence.packet_format import encode_packet
from review.decision import decide
from station.intake import freeze
from tests.support import Workflow, result, row, sample, scenario
from trial.protocols import get_trial


class TestArchive(unittest.TestCase):
    def setUp(self):
        self.flow = Workflow(self)
        self.trial = self.flow.register()
        self.east_revision, self.west_revision = self.flow.morning(self.trial)
        self.east_packet = self.flow.issue('east', self.east_revision)
        self.west_packet = self.flow.issue('west', self.west_revision, ('V', 'U'))
        self.east = self.flow.admit(self.east_packet)
        self.west = self.flow.admit(self.west_packet)

    def _correct_east(self):
        return self.flow.freeze(self.trial, 'east', sample('correction'), parent_id=self.east_revision)

    def _decide(self, left, limit):
        return decide(self.flow.accepted, self.flow.archive, left, self.west, limit)

    def test_revision_lineage_and_issue_named_revision(self):
        corrected = self._correct_east()
        source = self.flow.sources['east']
        old = source.get_revision(self.east_revision)
        new = source.get_revision(corrected)
        self.assertIsNone(old.parent_id)
        self.assertEqual(new.parent_id, self.east_revision)
        self.assertEqual((new.trial_id, new.bench_id), (old.trial_id, old.bench_id))
        self.assertEqual((len(old.rows), len(new.rows)), (4, 8))
        before = self.flow.revision_count('east')
        with self.assertRaisesRegex(ValueError, 'different trial or bench'):
            freeze(self.flow.registry, source, self.trial, 'west', sample('correction'), parent_id=corrected)
        another_trial = self.flow.register(trial_id='other-trial')
        with self.assertRaisesRegex(ValueError, 'different trial or bench'):
            self.flow.freeze(another_trial, 'east', sample('correction'), parent_id=corrected)
        with self.assertRaises(KeyError):
            self.flow.freeze(self.trial, 'east', [row('e-extra', 0, 0, 0)], parent_id='missing')
        self.assertEqual(self.flow.revision_count('east'), before)
        old_reissue = self.flow.issue('east', self.east_revision)
        new_issue = self.flow.issue('east', corrected)
        self.assertEqual(old_reissue.envelope.revision_id, self.east_revision)
        self.assertEqual(old_reissue.moments, self.east_packet.moments)
        self.assertEqual(new_issue.envelope.revision_id, corrected)
        self.assertEqual(new_issue.moments.covariance[0], (2, 0, 0))
        self.assertNotEqual(new_issue.envelope.issue_id, old_reissue.envelope.issue_id)
        self.flow.stop_sources()

    def test_revision_keeps_old_report(self):
        self.flow.stop_sources()
        original = self._decide(self.east, 3)
        self.assertEqual(result(original), (2, 4, False))
        self.flow.open_sources()
        corrected_revision = self._correct_east()
        corrected_packet = self.flow.issue('east', corrected_revision)
        new_east = self.flow.admit(corrected_packet)
        self.flow.stop_sources()
        corrected = self._decide(new_east, 7)
        self.assertEqual(result(corrected), (4, 8, True))
        self.assertNotEqual(original.report_id, corrected.report_id)
        self.flow.reopen_center()
        archive = self.flow.archive
        old_saved = read(archive, original.report_id)
        new_saved = read(archive, corrected.report_id)
        self.assertEqual(old_saved, original)
        self.assertEqual(new_saved, corrected)
        self.assertEqual(old_saved.draft.parents[0].revision_id, self.east_revision)
        self.assertEqual(new_saved.draft.parents[0].revision_id, corrected_revision)
        self.assertEqual(old_saved.draft.parents[1], new_saved.draft.parents[1])
        accepted = self.flow.accepted.get(old_saved.draft.parents[0].accepted_id)
        self.assertEqual(encode_packet(accepted.packet), encode_packet(self.east_packet))
        old_export = json.loads(export_report(archive, old_saved.report_id))
        new_export = json.loads(export_report(archive, new_saved.report_id))
        self.assertEqual(old_export['range'], {'m': '2', 'r': '4'})
        self.assertEqual(new_export['range'], {'m': '4', 'r': '8'})
        self.assertEqual(old_export['limit'], '3')
        self.assertFalse(old_export['passed'])
        self.assertEqual(old_export['parents'][0]['issue_id'], self.east_packet.envelope.issue_id)
        self.assertEqual(old_export['receipt']['report_id'], original.report_id)
        self.assertEqual(old_export['receipt']['receipt_id'], original.receipt.receipt_id)
        self.assertEqual(new_export['parents'][0]['issue_id'], corrected_packet.envelope.issue_id)
        self.assertEqual(new_export['receipt']['report_id'], corrected.report_id)
        self.assertEqual(self.flow.archive_counts(), (2, 2))
        with self.assertRaises(KeyError):
            read(archive, 'unknown-report')
        with self.assertRaises(KeyError):
            export_report(archive, 'unknown-report')
        scenario(
            'v7', {'original_limit': 3, 'corrected_limit': 7, 'correction': 'samples/correction.json'},
            {'old': {'m': '2', 'r': '4'}, 'new': {'m': '4', 'r': '8'}},
            {'old': old_export['range'], 'new': new_export['range']},
            {'same_right_parent': True, 'original_left_revision': True, 'old_receipt_matches': True},
            {'same_right_parent': old_saved.draft.parents[1] == new_saved.draft.parents[1],
             'original_left_revision': old_saved.draft.parents[0].revision_id == self.east_revision,
             'old_receipt_matches': old_saved.receipt == original.receipt},
            ['station/intake.py', 'archive/readback.py', 'archive/export.py', 'review/accepted_store.py'],
            'The correction leaves each U group with mean zero and main variance two; the original shared covariance was one.',
        )

    def test_reopen_preserves_user_data(self):
        user_trial = self.flow.register(trial_id='custom-trial', condition='夜班复测')
        original_user = self.flow.freeze(user_trial, 'east', [row('night-1', '7/4', 0, 0)])
        updated_user = self.flow.freeze(
            user_trial, 'east', [row('night-1', '9/4', 0, 0)], parent_id=original_user
        )
        user_packet = self.flow.issue('east', updated_user)
        user_piece = self.flow.admit(user_packet)
        report = self._decide(self.east, 4)
        self.flow.stop_sources()
        self.flow.open_sources()
        self.flow.reopen_center()
        self.assertEqual(get_trial(self.flow.registry, user_trial).condition, '夜班复测')
        corrected = self.flow.sources['east'].get_revision(updated_user)
        self.assertEqual(corrected.parent_id, original_user)
        self.assertEqual(corrected.rows[0].values, (Fraction(9, 4), 0, 0))
        self.assertEqual(self.flow.catalogs['east'].get(user_packet.envelope.issue_id), user_packet)
        self.assertEqual(self.flow.accepted.get(user_piece).packet, user_packet)
        self.assertEqual(read(self.flow.archive, report.report_id), report)
        self.assertEqual(self.flow.archive_counts(), (1, 1))

    def test_failed_commit_keeps_old_report(self):
        corrected = self._correct_east()
        changed = self.flow.admit(self.flow.issue('east', corrected))
        self.flow.stop_sources()
        old = self._decide(self.east, 3)
        old_export = export_report(self.flow.archive, old.report_id)
        before = self.flow.archive_counts()
        self.flow.center_db.executescript('''
            CREATE TABLE fixture_commit_parent (id INTEGER PRIMARY KEY);
            CREATE TABLE fixture_commit_child (
                id INTEGER REFERENCES fixture_commit_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TRIGGER fixture_fail_on_commit AFTER INSERT ON archive_receipts
            BEGIN
                INSERT INTO fixture_commit_child (id) VALUES (1);
            END;
        ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY constraint failed'):
            self._decide(changed, 7)
        self.flow.reopen_center()
        self.assertEqual(self.flow.archive_counts(), before)
        self.assertEqual(self.flow.center_db.execute('SELECT count(*) FROM fixture_commit_child').fetchone()[0], 0)
        self.assertEqual(read(self.flow.archive, old.report_id), old)
        self.assertEqual(export_report(self.flow.archive, old.report_id), old_export)
        rolled_back = self.flow.archive_counts()
        self.flow.center_db.execute('DROP TRIGGER fixture_fail_on_commit')
        successful = self._decide(changed, 7)
        self.assertEqual(result(successful), (4, 8, True))
        self.assertEqual(self.flow.archive_counts(), (2, 2))
        scenario(
            'v8.atomic_rollback', {'report_count_before': before[0], 'receipt_count_before': before[1]},
            {'after_failure': [1, 1]}, {'after_failure': list(rolled_back)},
            {'after_retry': [2, 2], 'm': '4', 'r': '8'},
            {'after_retry': list(self.flow.archive_counts()), 'm': str(successful.draft.m), 'r': str(successful.draft.r)},
            ['review/decision.py', 'archive/commit.py', 'archive/storage.py', 'archive/readback.py'],
            'A deferred foreign-key violation rejects the transaction after both writes. A fresh connection observes neither new row.',
        )
