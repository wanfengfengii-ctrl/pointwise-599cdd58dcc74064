from dataclasses import dataclass
import json

from archive.commit import ParentRef, ReportDraft
from archive.receipts import SuccessReceipt, decode_receipt
from trial.units import parse_rational


@dataclass(frozen=True)
class ArchivedReport:
    report_id: str
    draft: ReportDraft
    receipt: SuccessReceipt


def decode_report(payload):
    data = json.loads(payload)
    left, right = (ParentRef(**parent) for parent in data['parents'])
    limits = data['range']
    draft = ReportDraft(
        data['trial_id'], (left, right), parse_rational(data['limit']),
        parse_rational(limits['m']), parse_rational(limits['r']), data['passed'],
    )
    return data['report_id'], draft


def read(archive, report_id):
    report_payload, receipt_payload = archive.get_report_and_receipt(report_id)
    saved_id, draft = decode_report(report_payload)
    receipt = decode_receipt(receipt_payload)
    if saved_id != report_id or receipt.report_id != report_id:
        raise ValueError('inconsistent archived report identity')
    return ArchivedReport(saved_id, draft, receipt)
