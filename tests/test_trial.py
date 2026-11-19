from fractions import Fraction
import unittest

from station.intake import freeze
from tests.support import Workflow, row, sample, scenario
from trial.protocols import get_trial, register
from trial.roles import BenchRole


class TestTrial(unittest.TestCase):
    def setUp(self):
        self.flow = Workflow(self)
        self.trial = self.flow.register()

    def test_freeze_normalized_runs(self):
        milli = row('original-9', {'value': 1500, 'unit': 'mK'}, 0, '-1/4')
        base = row('original-9', '3/2', 0, '-1/4')
        first = self.flow.freeze(self.trial, 'east', [milli])
        second = self.flow.freeze(self.trial, 'east', [base])
        book = self.flow.sources['east']
        frozen = book.get_revision(first)
        self.assertEqual(frozen.rows, book.get_revision(second).rows)
        self.assertEqual(frozen.channels, ('main', 'U', 'V'))
        self.assertEqual(frozen.rows[0].run_id, 'original-9')
        self.assertEqual(frozen.rows[0].values, (Fraction(3, 2), Fraction(0), Fraction(-1, 4)))
        packet = self.flow.issue('east', first)
        self.assertEqual(packet.moments.means, (Fraction(3, 2), Fraction(0), Fraction(-1, 4)))
        self.assertEqual(packet.moments.covariance, ((0, 0, 0), (0, 0, 0), (0, 0, 0)))
        scenario(
            'v1.unit_equivalence', {'reading': milli, 'equivalent': base},
            {'main': '3/2', 'run_id': 'original-9'},
            {'main': str(frozen.rows[0].values[0]), 'run_id': frozen.rows[0].run_id},
            {'packet_mean': '3/2', 'packet_variance': '0'},
            {'packet_mean': str(packet.moments.means[0]), 'packet_variance': str(packet.moments.covariance[0][0])},
            ['trial/units.py', 'station/sourcebook.py', 'evidence/moments.py'],
            '1500 divided by 1000 is 3/2; a single reading has zero centered variance.',
        )

    def test_registration_guard(self):
        registry = self.flow.registry
        original = get_trial(registry, self.trial)
        self.assertEqual(original.roles.role_for('east'), BenchRole.LEFT)
        self.assertEqual(original.roles.role_for('west'), BenchRole.RIGHT)
        self.assertEqual(self.flow.register(references=['V', 'U']), self.trial)
        invalid = [
            ({'condition': 'different'}, 'conflicting trial'),
            ({'references': ['U', 'U']}, 'distinct'),
            ({'references': ['main', 'V']}, 'distinct'),
            ({'right_bench': 'east'}, 'distinct'),
        ]
        for changes, reason in invalid:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, reason):
                self.flow.register(**changes)
        invalid_units = sample('trial')
        invalid_units['units']['U'] = {'unit': 'K', 'inputs': ['mV']}
        with self.assertRaisesRegex(ValueError, 'incompatible input unit'):
            register(registry, **invalid_units)
        self.assertEqual(get_trial(registry, self.trial), original)
        with self.assertRaises(KeyError):
            get_trial(registry, 'unknown-trial')

    def test_reject_invalid_rows(self):
        self.flow.freeze(self.trial, 'east', [row('valid', 0, 0, 0)])
        before = self.flow.revision_count('east')
        cases = [
            ([row('dup', 1, 0, 0), row('dup', 2, 0, 0)], 'duplicate run'),
            ([{'run_id': 'missing', 'values': {'main': 0, 'U': 0}}], 'incomplete channels'),
            ([row('null', None, 0, 0)], 'invalid reading'),
            ([row('false', False, 0, 0)], 'invalid reading'),
            ([row('float', 0.1, 0, 0)], 'invalid reading'),
            ([row('bad fraction', '1/0', 0, 0)], 'invalid rational'),
            ([row('bad unit', {'value': 1, 'unit': 'uK'}, 0, 0)], 'outside the convention'),
        ]
        for rows, reason in cases:
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(ValueError, reason):
                    self.flow.freeze(self.trial, 'east', rows)
                self.assertEqual(self.flow.revision_count('east'), before)

    def test_empty_queue_does_not_freeze(self):
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            self.flow.freeze(self.trial, 'east', [])
        self.assertEqual(self.flow.revision_count('east'), 0)
        with self.assertRaisesRegex(ValueError, 'outside the trial'):
            freeze(self.flow.registry, self.flow.sources['east'], self.trial, 'other', [row('01', 0, 0, 0)])
        self.assertEqual(self.flow.revision_count('east'), 0)
