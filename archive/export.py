import json

from archive.commit import encode_report
from archive.readback import read
from archive.receipts import encode_receipt


def format_handoff(report):
    handoff = json.loads(encode_report(report.report_id, report.draft))
    handoff['receipt'] = json.loads(encode_receipt(report.receipt))
    return handoff


def export_report(archive, report_id):
    return json.dumps(format_handoff(read(archive, report_id)), sort_keys=True, separators=(',', ':'))
