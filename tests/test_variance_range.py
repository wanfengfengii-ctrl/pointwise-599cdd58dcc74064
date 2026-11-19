from fractions import Fraction
import unittest

from review.decision import decide
from tests.support import Workflow, result, sample, sign_rows


class TestVarianceRange(unittest.TestCase):
    """Regression for the cross-bench release review incident.

    Station packets must preserve the complete population second-order
    statistics of the frozen queue, and the signed range must be the exact
    achievable interval of the difference variance over all positive
    semidefinite joint covariances consistent with both packets.
    """

    def setUp(self):
        self.flow = Workflow(self)
        self.trial = self.flow.register()

    def _decide(self, left, right, limit):
        return decide(self.flow.accepted, self.flow.archive, left, right, limit)

    def test_packet_preserves_full_population_covariance(self):
        rows = sample('morning')
        revision = self.flow.freeze(self.trial, 'east', rows['east'])
        packet = self.flow.issue('east', revision)
        self.assertEqual(
            packet.moments.covariance,
            ((2, 1, 1), (1, 1, 1), (1, 1, 1)),
        )
        corrected = self.flow.freeze(
            self.trial, 'east', sample('correction'), parent_id=revision
        )
        corrected_packet = self.flow.issue('east', corrected)
        self.assertEqual(
            corrected_packet.moments.covariance,
            ((2, 0, 0), (0, 1, 1), (0, 1, 1)),
        )
        self.assertEqual(corrected_packet.moments.means, (0, 0, 0))

    def test_correction_range_rejects_formerly_misreleased_limit(self):
        east_revision, west_revision = self.flow.morning(self.trial)
        east = self.flow.admit(self.flow.issue('east', east_revision))
        west = self.flow.admit(self.flow.issue('west', west_revision, ('V', 'U')))
        self.flow.stop_sources()
        self.assertEqual(result(self._decide(east, west, 3)), (2, 4, False))
        self.assertEqual(result(self._decide(east, west, 4)), (2, 4, True))
        self.flow.open_sources()
        corrected_revision = self.flow.freeze(
            self.trial, 'east', sample('correction'), parent_id=east_revision
        )
        corrected = self.flow.admit(self.flow.issue('east', corrected_revision))
        self.flow.stop_sources()
        # The incident: limit 5 was wrongly released as [4,4]; the exact
        # reachable range is [4 - sqrt(8), 4 + sqrt(8)] and must be denied.
        self.assertEqual(result(self._decide(corrected, west, 5)), (4, 8, False))
        self.assertEqual(result(self._decide(corrected, west, 7)), (4, 8, True))
        just_below = Fraction('6.82842712474619')
        just_above = Fraction('6.82842712474620')
        self.assertEqual(result(self._decide(corrected, west, just_below)), (4, 8, False))
        self.assertEqual(result(self._decide(corrected, west, just_above)), (4, 8, True))

    def test_opposite_shared_parts_widen_the_range(self):
        east = self.flow.prepare(self.trial, 'east', sign_rows('e', lambda u, p: (u + p, u, u)))
        west = self.flow.prepare(self.trial, 'west', sign_rows('w', lambda u, p: (p - u, u, u)))
        self.flow.stop_sources()
        # Shared covariance is -1, so the difference variance is centered at
        # 2 + 2 + 2 = 6 with residual spread 2 on each side.
        self.assertEqual(result(self._decide(east, west, 7)), (6, 4, False))
        self.assertEqual(result(self._decide(east, west, 8)), (6, 4, True))
