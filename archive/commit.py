from dataclasses import asdict, dataclass
from fractions import Fraction
import json
from uuid import uuid4

from archive.receipts import build_success_receipt, encode_receipt


@dataclass(frozen=True)
class ParentRef:
    accepted_id: str
    issue_id: str
    bench_id: str
    revision_id: str


@dataclass(frozen=True)
class ReportDraft:
    trial_id: str
    parents: tuple[ParentRef, ParentRef]
    limit: Fraction
    m: Fraction
    r: Fraction
    passed: bool


def encode_report(report_id, draft):
    return json.dumps({
        'report_id': report_id,
        'trial_id': draft.trial_id,
        'parents': [asdict(parent) for parent in draft.parents],
        'limit': str(draft.limit),
        'range': {'m': str(draft.m), 'r': str(draft.r)},
        'passed': draft.passed,
    }, sort_keys=True, separators=(',', ':'))


def commit_report(archive, draft):
    report_id = uuid4().hex
    receipt = build_success_receipt(report_id)
    archive.write_report_and_receipt(
        report_id, encode_report(report_id, draft), encode_receipt(receipt)
    )
    return report_id, receipt
