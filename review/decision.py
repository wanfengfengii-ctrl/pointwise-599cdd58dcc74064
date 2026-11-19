from archive.commit import ParentRef, ReportDraft, commit_report
from archive.readback import ArchivedReport
from review.bounds import solve_variance_range
from review.compatibility import align_accepted_pair
from trial.units import parse_rational


def _parent_reference(record):
    envelope = record.packet.envelope
    return ParentRef(record.accepted_id, envelope.issue_id, envelope.bench_id, envelope.revision_id)


def decide(accepted, archive, first_id, second_id, limit):
    threshold = parse_rational(limit)
    if threshold < 0:
        raise ValueError('release limit must be nonnegative')
    pair = align_accepted_pair(accepted.get(first_id), accepted.get(second_id))
    variance_range = solve_variance_range(pair)
    draft = ReportDraft(
        pair.left.packet.envelope.trial_id,
        (_parent_reference(pair.left), _parent_reference(pair.right)),
        threshold, variance_range.m, variance_range.r, variance_range.upper_at_most(threshold),
    )
    report_id, receipt = commit_report(archive, draft)
    return ArchivedReport(report_id, draft, receipt)
