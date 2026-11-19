from database import write_transaction
from evidence.packet_format import decode_packet, encode_packet
from trial.roles import require_identifier


class PacketCatalog:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS station_packets (
                issue_id TEXT PRIMARY KEY NOT NULL,
                payload TEXT NOT NULL
            )
        ''')

    def save(self, packet):
        payload = encode_packet(packet)
        with write_transaction(self.connection):
            self.connection.execute(
                'INSERT INTO station_packets (issue_id, payload) VALUES (?, ?)',
                (packet.envelope.issue_id, payload),
            )
        return packet

    def get(self, issue_id):
        issue_id = require_identifier(issue_id, 'issue identifier')
        record = self.connection.execute(
            'SELECT payload FROM station_packets WHERE issue_id = ?', (issue_id,)
        ).fetchone()
        if record is None:
            raise KeyError(issue_id)
        return decode_packet(record[0])
