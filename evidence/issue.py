from uuid import uuid4

from evidence.coordinates import ChannelCoordinates
from evidence.moments import compute_population_moments
from evidence.packet_format import PacketEnvelope, StationPacket


def issue(source, catalog, revision_id, reference_order=None):
    revision = source.get_revision(revision_id)
    moments = compute_population_moments(revision)
    if reference_order is not None:
        if not isinstance(reference_order, (list, tuple)):
            raise ValueError('reference order must be an array of channel identifiers')
        requested = ChannelCoordinates(moments.coordinates.main, tuple(reference_order))
        moments = moments.in_order(requested)
    envelope = PacketEnvelope(1, uuid4().hex, revision.trial_id, revision.bench_id, revision.revision_id)
    return catalog.save(StationPacket(envelope, moments))
