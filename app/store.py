from contextlib import contextmanager
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

class Conflict(Exception): pass

def now(): return datetime.now(timezone.utc).isoformat()

@contextmanager
def connect():
    path = Path(os.getenv('NOTE_DB', str(Path(__file__).resolve().parent.parent/'data'/'notes.db')))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    path.chmod(0o600)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''CREATE TABLE IF NOT EXISTS encounters(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY, encounter_id TEXT, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS evaluations(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);''')
    try:
        with db:
            yield db
    finally:
        db.close()

def create(title, transcript, result):
    record = {**result,'id':str(uuid4()),'title':title,'transcript':transcript,'status':'draft','revision':1,'created_at':now(),'updated_at':now()}
    with connect() as db:
        db.execute('INSERT INTO encounters VALUES (?,?)',(record['id'],json.dumps(record)))
        db.execute('INSERT INTO revisions(encounter_id,payload) VALUES (?,?)',(record['id'],json.dumps({'revision':1,'at':now(),'action':'generated','reviewer':None,'note':record['note'],'comment':''})))
    return record

def get(id):
    with connect() as db:
        row = db.execute('SELECT payload FROM encounters WHERE id=?',(id,)).fetchone()
    return json.loads(row[0]) if row else None

def list_records(table):
    assert table in ('encounters','evaluations','events')
    with connect() as db:
        rows = db.execute(f'SELECT payload FROM {table} ORDER BY rowid DESC LIMIT 200').fetchall()
    return [json.loads(r[0]) for r in rows]

def revisions(id):
    with connect() as db:
        rows = db.execute('SELECT payload FROM revisions WHERE encounter_id=? ORDER BY id',(id,)).fetchall()
    return [json.loads(r[0]) for r in rows]

def save_review(id, review, flags):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload FROM encounters WHERE id=?',(id,)).fetchone()
        if not row: raise KeyError(id)
        record = json.loads(row[0])
        if record['revision'] != review.revision: raise Conflict('This draft changed. Reload it before saving.')
        if record['status'] == 'approved': raise Conflict('Approved notes are immutable. Generate a new draft to make changes.')
        previous = record['note']
        record.update(note=review.note.model_dump(), flags=flags, revision=record['revision']+1, updated_at=now(), status='approved' if review.approve else 'draft')
        if review.approve:
            record.update(approved_at=now(), reviewer=review.reviewer)
            record['trace'][-1]['result']='approved by human reviewer'
        db.execute('UPDATE encounters SET payload=? WHERE id=?',(json.dumps(record),id))
        snapshot={'revision':record['revision'],'at':now(),'action':'approved' if review.approve else 'edited','reviewer':review.reviewer,'comment':review.comment,'changed':previous != record['note'],'note':record['note']}
        db.execute('INSERT INTO revisions(encounter_id,payload) VALUES (?,?)',(id,json.dumps(snapshot)))
    return record

def save_evaluation(result):
    with connect() as db: db.execute('INSERT INTO evaluations VALUES (?,?)',(result['id'],json.dumps(result)))

def event(payload):
    with connect() as db: db.execute('INSERT INTO events(payload) VALUES (?)',(json.dumps({'at':now(),**payload}),))
