"""Small, transparent synthetic regression set; not a clinical validation dataset."""

import json
from pathlib import Path

cases = []


def add(category, name, transcript, checks):
    cases.append(
        {
            "id": f"case-{len(cases) + 1:02}",
            "category": category,
            "title": name,
            "transcript": transcript,
            "checks": checks,
        }
    )


def present(section, text):
    return {"section": section, "contains": text, "expected": True}


def absent(section, text):
    return {"section": section, "contains": text, "expected": False}


for symptom in ["fever", "chest pain", "nausea", "dizziness", "shortness of breath"]:
    add(
        "Negation",
        f"Denied {symptom}",
        f"Clinician: Have you had {symptom}?\nPatient: I have not had {symptom}.",
        [
            present("subjective", f"not had {symptom}"),
            absent("subjective", f"Have you had {symptom}?"),
        ],
    )
for relative, condition in [
    ("mother", "asthma"),
    ("father", "diabetes"),
    ("sister", "migraine"),
    ("brother", "eczema"),
    ("grandmother", "arthritis"),
]:
    add(
        "Attribution",
        f"{relative.capitalize()} history",
        f"Clinician: Tell me about your family history.\nPatient: My {relative} has {condition}. I do not have that diagnosis.",
        [
            present("subjective", f"My {relative} has {condition}"),
            present("subjective", "I do not have that diagnosis"),
            absent("assessment", condition),
        ],
    )
for finding in [
    "temperature is 37 C",
    "pulse is 72 beats per minute",
    "blood pressure is 118 over 76",
    "respiratory rate is 14",
    "oxygen saturation is 98 percent",
]:
    add(
        "Section routing",
        finding.capitalize(),
        f"Patient: I came for a routine visit.\nClinician: Vitals: {finding}.",
        [present("objective", finding), absent("subjective", finding)],
    )
for topic in ["headache", "cough", "fatigue", "itching", "back discomfort"]:
    add(
        "Missing evidence",
        f"No examination — {topic}",
        f"Clinician: What brings you in?\nPatient: I have {topic}.",
        [
            present("subjective", topic),
            {"section": "objective", "empty": True},
            {"section": "assessment", "empty": True},
            {"section": "plan", "empty": True},
        ],
    )
for old, new in [
    ("three", "five"),
    ("two", "four"),
    ("six", "seven"),
    ("one", "two"),
    ("four", "eight"),
]:
    add(
        "Corrections",
        f"Duration corrected {old} to {new}",
        f"Patient: The cough started {old} days ago.\nPatient: Correction: the cough started {new} days ago, not {old}.",
        [
            present("subjective", f"started {new} days ago"),
            absent("subjective", f"started {old} days ago."),
        ],
    )
for task in [
    "review the symptom diary at follow-up",
    "discuss the test results at the next visit",
    "check the home readings at follow-up",
    "review the medication list next visit",
    "discuss the referral at follow-up",
]:
    add(
        "Explicit plan",
        task.capitalize(),
        f"Patient: I understand.\nClinician: Plan: We will {task}.",
        [present("plan", task), absent("subjective", task)],
    )
assert len(cases) == 30
Path(__file__).with_name("cases.json").write_text(json.dumps(cases, indent=2))
