from dataclasses import dataclass
import json
from uuid import uuid4

from database import write_transaction
from evidence.coordinates import ChannelCoordinates
from evidence.packet_format import StationPacket, decode_packet, encode_packet
from trial.roles import BenchRole, require_identifier


@dataclass(frozen=True)
class AcceptedPacket:
    accepted_id: str
    packet: StationPacket
    role: BenchRole
    coordinates: ChannelCoordinates


def _restore(record):
    accepted_id, payload, role, coordinates_json = record
    main, first, second = json.loads(coordinates_json)
    return AcceptedPacket(
        accepted_id, decode_packet(payload), BenchRole(role), ChannelCoordinates(main, (first, second))
    )


def _same_evidence(saved, incoming, role, coordinates):
    return (
        saved.packet.envelope == incoming.envelope
        and saved.role == role
        and saved.coordinates == coordinates
        and saved.packet.moments.in_order(coordinates) == incoming.moments.in_order(coordinates)
    )


class AcceptedStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS accepted_packets (
                accepted_id TEXT PRIMARY KEY NOT NULL,
                issue_id TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('left', 'right')),
                coordinates TEXT NOT NULL
            )
        ''')

    def accept(self, packet, role, coordinates):
        with write_transaction(self.connection):
            record = self.connection.execute('''
                SELECT accepted_id, payload, role, coordinates
                FROM accepted_packets WHERE issue_id = ?
            ''', (packet.envelope.issue_id,)).fetchone()
            if record is not None:
                saved = _restore(record)
                if not _same_evidence(saved, packet, role, coordinates):
                    raise ValueError('conflicting packet for issue identifier')
                return saved.accepted_id
            accepted_id = uuid4().hex
            self.connection.execute('''
                INSERT INTO accepted_packets (accepted_id, issue_id, payload, role, coordinates)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                accepted_id, packet.envelope.issue_id, encode_packet(packet),
                role.value, json.dumps(coordinates.channels),
            ))
        return accepted_id

    def get(self, accepted_id):
        accepted_id = require_identifier(accepted_id, 'accepted packet identifier')
        record = self.connection.execute('''
            SELECT accepted_id, payload, role, coordinates
            FROM accepted_packets WHERE accepted_id = ?
        ''', (accepted_id,)).fetchone()
        if record is None:
            raise KeyError(accepted_id)
        return _restore(record)
