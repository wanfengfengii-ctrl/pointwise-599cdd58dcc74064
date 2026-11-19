from evidence.coordinates import ChannelCoordinates, channel_permutation
from evidence.packet_format import decode_packet
from trial.protocols import get_trial


def admit(registry, accepted, packet_json):
    packet = decode_packet(packet_json)
    spec = get_trial(registry, packet.envelope.trial_id)
    role = spec.roles.role_for(packet.envelope.bench_id)
    main, first, second = spec.expected_channels()
    coordinates = ChannelCoordinates(main, (first, second))
    channel_permutation(packet.moments.coordinates, coordinates)
    return accepted.accept(packet, role, coordinates)
