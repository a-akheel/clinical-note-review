"""Bounded generation pipeline. Demo is extractive, never an LLM simulation."""

import os
import re
import time
from .schemas import Note

SECTIONS = ("subjective", "objective", "assessment", "plan")
from .providers import GenerationError, openai_generate, ollama_generate


def parse_turns(transcript):
    turns = []
    for line in transcript.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(
            r"^(?:T\d+\s*[—–-]\s*)?(Patient|Clinician|Doctor|Nurse|Caregiver|Family member)\s*:\s*(.+)$",
            line,
            re.I,
        )
        if not match:
            raise ValueError(
                "Use one speaker turn per line, starting with Patient:, Clinician:, Nurse:, or Caregiver:."
            )
        speaker = match[1].capitalize()
        if speaker == "Doctor":
            speaker = "Clinician"
        turns.append({"id": f"T{len(turns) + 1}", "speaker": speaker, "text": match[2]})
    if not 2 <= len(turns) <= 120:
        raise ValueError("Enter between 2 and 120 speaker turns.")
    return turns


def validate_references(note, turns):
    ids = {t["id"] for t in turns}
    errors = []
    for section in SECTIONS:
        for i, claim in enumerate(getattr(note, section)):
            if len(set(claim.source_turn_ids)) != len(claim.source_turn_ids):
                errors.append(
                    f"{section} statement {i + 1}: duplicate source reference."
                )
            missing = set(claim.source_turn_ids) - ids
            if missing:
                errors.append(
                    f"{section} statement {i + 1}: unknown source {', '.join(sorted(missing))}."
                )
    if not any(getattr(note, s) for s in SECTIONS):
        errors.append(
            "The note contains no statements. Add an evidence-linked statement before saving."
        )
    if errors:
        raise ValueError(" ".join(errors))


def review_flags(note, turns):
    flags = []
    for section in SECTIONS:
        if not getattr(note, section):
            flags.append(
                {
                    "kind": "missing",
                    "text": f"{section.capitalize()}: no information documented. Confirm this matches the transcript.",
                }
            )
    text = " ".join(t["text"].lower() for t in turns)
    if any(
        word in text
        for word in ["actually", "correction", "not sure", "unsure", "maybe", "i think"]
    ):
        flags.append(
            {
                "kind": "ambiguity",
                "text": "Correction or uncertainty detected. Check chronology and qualifiers.",
            }
        )
    if any(
        word in text for word in ["mother", "father", "sister", "brother", "family"]
    ):
        flags.append(
            {
                "kind": "attribution",
                "text": "Family-history language detected. Verify who each finding belongs to.",
            }
        )
    flags.append(
        {
            "kind": "review",
            "text": "Source references are structurally valid, not proof of factual support. Review every statement against its evidence.",
        }
    )
    return flags


def demo_generate(turns, version):
    """Extract verbatim statements. No hidden fixture lookup, learned inference or AI call."""
    result = {s: [] for s in SECTIONS}
    for turn in turns:
        text, speaker = turn["text"], turn["speaker"]
        section = "subjective"
        if version in ("grounded-v2", "corrections-v3"):
            if speaker in ("Clinician", "Nurse"):
                if text.endswith("?"):
                    continue
                lower = text.lower()
                if lower.startswith(("exam:", "vitals:", "measurement:")):
                    section = "objective"
                elif lower.startswith(("assessment:", "impression:")):
                    section = "assessment"
                elif lower.startswith(("plan:", "follow-up:")):
                    section = "plan"
                else:
                    continue
        result[section].append(
            {"text": f"{speaker}: {text}", "source_turn_ids": [turn["id"]]}
        )
    return Note.model_validate(result)


async def generate(transcript, provider, version):
    started = time.perf_counter()
    turns = parse_turns(transcript)
    if provider == "demo":
        note, usage, model = demo_generate(turns, version), {}, "extractive-demo"
    elif provider == "ollama":
        note, usage, model = await ollama_generate(turns, version)
    else:
        note, usage, model = await openai_generate(turns, version)
    try:
        validate_references(note, turns)
    except ValueError as exc:
        raise GenerationError(str(exc)) from exc
    cost = None
    input_rate, output_rate = (
        os.getenv("INPUT_USD_PER_MILLION"),
        os.getenv("OUTPUT_USD_PER_MILLION"),
    )
    if provider == "openai" and input_rate and output_rate:
        try:
            cost = (
                usage.get("input_tokens", 0) * float(input_rate)
                + usage.get("output_tokens", 0) * float(output_rate)
            ) / 1e6
        except ValueError:
            pass
    return {
        "turns": turns,
        "note": note.model_dump(),
        "flags": review_flags(note, turns),
        "provider": provider,
        "model": model,
        "prompt_version": version,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "usage": usage,
        "estimated_cost_usd": cost,
        "trace": [
            {"step": "parse_transcript", "result": f"{len(turns)} speaker turns"},
            {"step": "generate_note", "result": model},
            {"step": "validate_structure_and_references", "result": "passed"},
            {"step": "human_review", "result": "pending"},
        ],
    }
