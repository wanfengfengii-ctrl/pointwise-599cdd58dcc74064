from database import write_transaction
from trial.roles import require_identifier


class ArchiveStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        with write_transaction(self.connection):
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS archive_reports (
                    report_id TEXT PRIMARY KEY NOT NULL,
                    payload TEXT NOT NULL
                )
            ''')
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS archive_receipts (
                    report_id TEXT PRIMARY KEY NOT NULL REFERENCES archive_reports(report_id),
                    payload TEXT NOT NULL
                )
            ''')

    def write_report_and_receipt(self, report_id, report_payload, receipt_payload):
        with write_transaction(self.connection):
            self.connection.execute(
                'INSERT INTO archive_reports (report_id, payload) VALUES (?, ?)',
                (report_id, report_payload),
            )
            self.connection.execute(
                'INSERT INTO archive_receipts (report_id, payload) VALUES (?, ?)',
                (report_id, receipt_payload),
            )

    def get_report_and_receipt(self, report_id):
        report_id = require_identifier(report_id, 'report identifier')
        row = self.connection.execute('''
            SELECT report.payload, receipt.payload
            FROM archive_reports AS report
            JOIN archive_receipts AS receipt ON receipt.report_id = report.report_id
            WHERE report.report_id = ?
        ''', (report_id,)).fetchone()
        if row is None:
            raise KeyError(report_id)
        return row
