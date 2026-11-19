from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class SuccessReceipt:
    receipt_id: str
    report_id: str


def build_success_receipt(report_id):
    return SuccessReceipt(f'receipt-{report_id}', report_id)


def encode_receipt(receipt):
    return json.dumps(asdict(receipt), sort_keys=True, separators=(',', ':'))


def decode_receipt(payload):
    return SuccessReceipt(**json.loads(payload))
