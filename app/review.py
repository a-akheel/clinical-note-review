"""Human semantic review, tied to exact generated notes. No automated clinical verdict."""

import copy
import hashlib
import json

LABELS = {
    "supported",
    "unsupported",
    "contradicted",
    "incorrect_attribution",
    "uncertain",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def make_packet(report, cases):
    transcripts = {case["id"]: case["transcript"] for case in cases}
    tasks = []
    for row in report["results"]:
        if row.get("error") or not row.get("note"):
            continue
        note = row["note"]
        tasks.append(
            {
                "case_id": row["case_id"],
                "note_sha256": digest(note),
                "transcript": transcripts[row["case_id"]],
                "note": copy.deepcopy(note),
                "claims": [
                    {
                        "section": section,
                        "index": index,
                        "text": claim["text"],
                        "label": None,
                        "rationale": "",
                    }
                    for section, claims in note.items()
                    for index, claim in enumerate(claims)
                ],
                "omissions": None,
                "reviewer": "",
                "reviewed_at": "",
            }
        )
    return {"report_id": report["id"], "rubric_version": "1", "tasks": tasks}


def summarize_review(packet, report):
    if packet.get("report_id") != report["id"]:
        raise ValueError("review belongs to a different run")
    expected = {
        r["case_id"]: r["note"]
        for r in report["results"]
        if not r.get("error") and r.get("note")
    }
    reviewed, seen, counts, omissions = 0, set(), dict.fromkeys(sorted(LABELS), 0), 0
    for task in packet["tasks"]:
        cid = task["case_id"]
        if cid in seen or cid not in expected:
            raise ValueError("duplicate or unknown review case")
        seen.add(cid)
        note = expected[cid]
        if task.get("note_sha256") != digest(note) or digest(task.get("note")) != digest(note):
            raise ValueError("note changed after review packet was created")
        keys = {
            (section, i): claim["text"]
            for section, claims in note.items()
            for i, claim in enumerate(claims)
        }
        claim_keys = [(c["section"], c["index"]) for c in task["claims"]]
        if len(claim_keys) != len(set(claim_keys)) or set(claim_keys) != set(keys):
            raise ValueError("review must cover each generated claim exactly once")
        for claim in task["claims"]:
            if claim["text"] != keys[(claim["section"], claim["index"])]:
                raise ValueError("review claim text does not match generated note")
        if (
            not task.get("reviewer", "").strip()
            or not task.get("reviewed_at", "").strip()
        ):
            continue
        if not isinstance(task.get("omissions"), list):
            raise ValueError(
                "reviewer must explicitly record omissions (empty list if none)"
            )
        for omission in task["omissions"]:
            if not isinstance(omission, str) or not omission.strip():
                raise ValueError("omissions must contain nonempty descriptions")
        for claim in task["claims"]:
            if (
                claim.get("label") not in LABELS
                or not claim.get("rationale", "").strip()
            ):
                raise ValueError("every claim needs a valid label and rationale")
            counts[claim["label"]] += 1
        omissions += len(task["omissions"])
        reviewed += 1
    total = sum(counts.values())
    return {
        "reviewed_cases": reviewed,
        "eligible_cases": len(expected),
        "complete": reviewed == len(expected) and bool(expected),
        "labels": counts,
        "supported_claim_fraction": counts["supported"] / total if total else None,
        "omitted_facts": omissions,
        "scope": "Reviewer judgments on synthetic examples; not clinical validation.",
    }
