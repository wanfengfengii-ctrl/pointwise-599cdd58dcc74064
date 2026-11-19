from dataclasses import dataclass
import json

from evidence.coordinates import ChannelCoordinates
from evidence.moments import LocalMoments
from trial.roles import require_identifier
from trial.units import parse_rational


@dataclass(frozen=True)
class PacketEnvelope:
    version: int
    issue_id: str
    trial_id: str
    bench_id: str
    revision_id: str


@dataclass(frozen=True)
class StationPacket:
    envelope: PacketEnvelope
    moments: LocalMoments


def encode_packet(packet):
    envelope = packet.envelope
    moments = packet.moments
    return json.dumps({
        'version': envelope.version,
        'issue_id': envelope.issue_id,
        'trial_id': envelope.trial_id,
        'bench_id': envelope.bench_id,
        'revision_id': envelope.revision_id,
        'body': {
            'channels': moments.coordinates.channels,
            'means': [str(value) for value in moments.means],
            'covariance': [[str(value) for value in row] for row in moments.covariance],
        },
    }, sort_keys=True, separators=(',', ':'))


def _unique_object(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f'duplicate JSON key: {key}')
        data[key] = value
    return data


def _rational_vector(values):
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError('station vectors must have three entries')
    return tuple(parse_rational(value) for value in values)


def decode_packet(payload):
    if not isinstance(payload, str):
        raise ValueError('station packet must be JSON text')
    data = json.loads(payload, object_pairs_hook=_unique_object)
    if not isinstance(data, dict) or set(data) != {
        'version', 'issue_id', 'trial_id', 'bench_id', 'revision_id', 'body',
    }:
        raise ValueError('invalid station packet envelope')
    if type(data['version']) is not int or data['version'] != 1:
        raise ValueError('unsupported station packet version')
    envelope = PacketEnvelope(
        data['version'], require_identifier(data['issue_id'], 'issue identifier'),
        require_identifier(data['trial_id'], 'trial identifier'),
        require_identifier(data['bench_id'], 'bench identifier'),
        require_identifier(data['revision_id'], 'revision identifier'),
    )
    body = data['body']
    if not isinstance(body, dict) or set(body) != {'channels', 'means', 'covariance'}:
        raise ValueError('invalid station packet body')
    channels = body['channels']
    if not isinstance(channels, list) or len(channels) != 3:
        raise ValueError('station body must name three channels')
    coordinates = ChannelCoordinates(channels[0], tuple(channels[1:]))
    means = _rational_vector(body['means'])
    matrix = body['covariance']
    if not isinstance(matrix, list) or len(matrix) != 3:
        raise ValueError('invalid station covariance shape')
    covariance = tuple(_rational_vector(row) for row in matrix)
    if covariance != tuple(zip(*covariance, strict=True)):
        raise ValueError('station covariance must be symmetric')
    return StationPacket(envelope, LocalMoments(coordinates, means, covariance))
