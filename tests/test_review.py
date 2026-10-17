import copy
import pytest
from app.review import make_packet, summarize_review


@pytest.fixture
def sample():
    report = {
        "id": "run-1",
        "results": [
            {
                "case_id": "c1",
                "error": None,
                "note": {
                    "subjective": [
                        {"text": "Patient denies fever.", "source_turn_ids": ["T2"]}
                    ],
                    "objective": [],
                    "assessment": [],
                    "plan": [],
                },
            }
        ],
    }
    cases = [{"id": "c1", "transcript": "Clinician: Fever?\nPatient: No."}]
    return report, make_packet(report, cases)


def test_unreviewed_is_unknown_not_perfect(sample):
    report, packet = sample
    result = summarize_review(packet, report)
    assert result["supported_claim_fraction"] is None
    assert not result["complete"]


def test_completed_review(sample):
    report, packet = sample
    task = packet["tasks"][0]
    task.update(reviewer="Reviewer", reviewed_at="2026-10-15", omissions=[])
    task["claims"][0].update(
        label="supported", rationale="Patient explicitly denied fever."
    )
    assert summarize_review(packet, report)["supported_claim_fraction"] == 1


@pytest.mark.parametrize("mutation", ["run", "note", "packet_note", "duplicate", "claim", "missing"])
def test_stale_or_incomplete_packet_rejected(sample, mutation):
    report, packet = sample
    if mutation == "run":
        packet["report_id"] = "another-run"
    if mutation == "note":
        report["results"][0]["note"]["subjective"][0]["text"] = "Fever present"
    if mutation == "packet_note":
        packet["tasks"][0]["note"]["subjective"][0]["source_turn_ids"] = ["T1"]
    if mutation == "duplicate":
        packet["tasks"].append(copy.deepcopy(packet["tasks"][0]))
    if mutation == "claim":
        packet["tasks"][0]["claims"][0]["text"] = "changed"
    if mutation == "missing":
        packet["tasks"][0]["claims"] = []
    with pytest.raises(ValueError):
        summarize_review(packet, report)


def test_no_implicit_omission_approval(sample):
    report, packet = sample
    packet["tasks"][0].update(reviewer="Reviewer", reviewed_at="2026-10-15")
    with pytest.raises(ValueError):
        summarize_review(packet, report)
