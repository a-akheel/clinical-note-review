import asyncio
import copy
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app, ACCESS_PASSWORD
from app.engine import (
    parse_turns,
    demo_generate,
    validate_references,
    generate,
    GenerationError,
)
from app.schemas import Note
from app.evaluation import evaluate, CASES

TRANSCRIPT = "Clinician: Do you have a fever?\nPatient: I do not have a fever.\nClinician: Vitals: temperature is 37 C.\nClinician: Plan: Review the symptom diary."


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTE_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with TestClient(app) as c:
        c.auth = ("adeel", ACCESS_PASSWORD)
        yield c


def create(client):
    r = client.post(
        "/api/generate",
        json={
            "title": "Test encounter",
            "transcript": TRANSCRIPT,
            "synthetic_confirmed": True,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def review_payload(record, **kwargs):
    return {
        "note": copy.deepcopy(record["note"]),
        "revision": record["revision"],
        "reviewer": "Adeel",
        "comment": "Checked against transcript.",
        **kwargs,
    }


def test_demo_citations_and_negation(client):
    r = create(client)
    assert r["note"]["subjective"][0]["text"] == "Patient: I do not have a fever."
    assert r["note"]["objective"][0]["source_turn_ids"] == ["T3"]
    assert r["note"]["assessment"] == []
    assert r["provider"] == "demo" and r["usage"] == {}


def test_requires_synthetic_confirmation(client):
    assert (
        client.post(
            "/api/generate",
            json={"transcript": TRANSCRIPT, "synthetic_confirmed": False},
        ).status_code
        == 422
    )


def test_bad_transcript(client):
    assert (
        client.post(
            "/api/generate",
            json={
                "transcript": "unlabeled conversation data",
                "synthetic_confirmed": True,
            },
        ).status_code
        == 422
    )


def test_size_limit(client):
    assert (
        client.post(
            "/api/generate",
            json={"transcript": "x" * 130000, "synthetic_confirmed": True},
        ).status_code
        == 413
    )


def test_approval_requires_confirmation(client):
    r = create(client)
    assert (
        client.put(
            "/api/encounters/" + r["id"], json=review_payload(r, approve=True)
        ).status_code
        == 422
    )


def test_revisions_and_immutable_approval(client):
    r = create(client)
    payload = review_payload(r)
    payload["note"]["subjective"][0]["text"] = "Patient denies fever."
    saved = client.put("/api/encounters/" + r["id"], json=payload).json()
    assert saved["revision"] == 2 and saved["history"][0]["note"] == r["note"]
    approved = client.put(
        "/api/encounters/" + r["id"],
        json=review_payload(saved, approve=True, review_confirmed=True),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert (
        client.put(
            "/api/encounters/" + r["id"], json=review_payload(approved.json())
        ).status_code
        == 409
    )


def test_stale_revision(client):
    r = create(client)
    assert (
        client.put("/api/encounters/" + r["id"], json=review_payload(r)).status_code
        == 200
    )
    assert (
        client.put("/api/encounters/" + r["id"], json=review_payload(r)).status_code
        == 409
    )


def test_unknown_citation(client):
    r = create(client)
    p = review_payload(r)
    p["note"]["subjective"][0]["source_turn_ids"] = ["T999"]
    assert client.put("/api/encounters/" + r["id"], json=p).status_code == 422


def test_empty_citation(client):
    r = create(client)
    p = review_payload(r)
    p["note"]["subjective"][0]["source_turn_ids"] = []
    assert client.put("/api/encounters/" + r["id"], json=p).status_code == 422


def test_blank_statement(client):
    r = create(client)
    p = review_payload(r)
    p["note"]["subjective"][0]["text"] = "  "
    assert client.put("/api/encounters/" + r["id"], json=p).status_code == 422


def test_empty_note(client):
    r = create(client)
    p = review_payload(r)
    p["note"] = {k: [] for k in p["note"]}
    assert client.put("/api/encounters/" + r["id"], json=p).status_code == 422


def test_export_and_history(client):
    r = create(client)
    exported = client.get("/api/encounters/" + r["id"] + "/export")
    assert exported.json()["history"][0]["note"] == r["note"]
    assert "attachment;" in exported.headers["content-disposition"]


def test_no_secret_in_config(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-never-expose")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    r = client.get("/api/config")
    assert r.json()["live_available"] and "secret-never-expose" not in r.text


def test_live_without_key_fails_explicitly(client):
    r = client.post(
        "/api/generate",
        json={
            "transcript": TRANSCRIPT,
            "provider": "openai",
            "synthetic_confirmed": True,
        },
    )
    assert r.status_code == 502
    assert client.get("/api/encounters").json() == []
    assert client.get("/api/metrics").json()["failures"] == 1


def test_cross_origin_blocked(client):
    assert (
        client.post(
            "/api/generate", json={}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_non_json_blocked(client):
    assert (
        client.post(
            "/api/generate", content="hello", headers={"Content-Type": "text/plain"}
        ).status_code
        == 415
    )


def test_unknown_encounter(client):
    assert client.get("/api/encounters/missing").status_code == 404


def test_metrics_do_not_contain_transcript(client):
    create(client)
    metrics = client.get("/api/metrics")
    assert "fever" not in metrics.text and metrics.json()["demo_requests"] == 1


def test_regression_comparison_records_known_failures():
    a = asyncio.run(evaluate("demo", "baseline-v1"))
    b = asyncio.run(evaluate("demo", "grounded-v2"))
    assert a["total"] == b["total"] == 30
    assert a["passed"] < b["passed"] < 30
    assert all(not r["passed"] for r in b["results"] if r["category"] == "Corrections")
    assert b["semantic_review"] == "not performed"


def test_eval_run_persists(client):
    r = client.post("/api/evaluations", json={"limit": 5})
    assert r.status_code == 200
    import time

    for _ in range(30):
        runs = client.get("/api/evaluations").json()
        if runs[0]["status"] == "completed":
            break
        time.sleep(0.01)
    assert runs[0]["status"] == "completed"


def test_live_adapter_with_mock(monkeypatch):
    from app import providers as engine

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    expected = demo_generate(parse_turns(TRANSCRIPT), "grounded-v2").model_dump()

    class Response:
        status_code = 200

        def json(self):
            return {
                "status": "completed",
                "output": [
                    {"content": [{"type": "output_text", "text": json.dumps(expected)}]}
                ],
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, headers, json):
            assert url == "https://api.openai.com/v1/responses"
            assert json["store"] is False
            assert json["text"]["format"]["strict"] is True
            return Response()

    monkeypatch.setattr(engine.httpx, "AsyncClient", Client)
    result = asyncio.run(generate(TRANSCRIPT, "openai", "grounded-v2"))
    assert result["note"] == expected and result["usage"]["input_tokens"] == 100


def test_duplicate_citations_rejected():
    turns = parse_turns(TRANSCRIPT)
    note = demo_generate(turns, "grounded-v2")
    note.subjective[0].source_turn_ids = ["T2", "T2"]
    with pytest.raises(ValueError):
        validate_references(note, turns)


def test_auth_required(client):
    r = client.get("/api/encounters", auth=("adeel", "wrong"))
    assert r.status_code == 401
    assert client.get("/", auth=None).status_code == 401


def test_browser_security_headers(client):
    r = client.get("/api/encounters")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"
    assert (
        client.get(
            "/api/encounters", headers={"sec-fetch-site": "cross-site"}
        ).status_code
        == 403
    )
    assert client.get("/openapi.json").status_code == 404


def test_private_database(client):
    import os
    from pathlib import Path

    create(client)
    assert Path(os.environ["NOTE_DB"]).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "failure", [None, "truncated", "unknown-source", "unavailable"]
)
def test_local_adapter(monkeypatch, failure):
    from app import providers as engine

    expected = demo_generate(parse_turns(TRANSCRIPT), "grounded-v2").model_dump()
    if failure == "unknown-source":
        expected["subjective"][0]["source_turn_ids"] = ["T999"]

    class Response:
        status_code = 503 if failure == "unavailable" else 200

        def json(self):
            return {
                "done": True,
                "done_reason": "length" if failure == "truncated" else "stop",
                "message": {"content": json.dumps(expected)},
                "prompt_eval_count": 80,
                "eval_count": 40,
            }

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            assert url == "http://127.0.0.1:11434/api/chat"
            assert json["model"] == "qwen3:4b" and json["stream"] is False
            assert json["format"]["additionalProperties"] is False
            return Response()

    monkeypatch.setattr(engine.httpx, "AsyncClient", Client)
    if failure:
        with pytest.raises(GenerationError):
            asyncio.run(generate(TRANSCRIPT, "ollama", "grounded-v2"))
    else:
        r = asyncio.run(generate(TRANSCRIPT, "ollama", "grounded-v2"))
        assert r["note"] == expected and r["usage"]["input_tokens"] == 80
        assert r["estimated_cost_usd"] is None
