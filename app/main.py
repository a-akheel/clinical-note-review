import asyncio
import base64
import secrets
import json
import os
import statistics
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import store
from .engine import generate, validate_references, review_flags, GenerationError
from .evaluation import CASES, evaluate
from .schemas import Generate, Review, EvalRequest

ROOT=Path(__file__).resolve().parent
jobs={}

def local_password():
    path = ROOT.parent / 'data' / '.local-password'
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.exists():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f: f.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
    path.chmod(0o600)
    return path.read_text().strip()

ACCESS_PASSWORD = local_password()

@asynccontextmanager
async def lifespan(app):
    # In-process jobs are not durable workers; make interrupted runs explicit.
    for item in store.list_records('evaluations'):
        if item.get('status')=='running':
            item.update(status='interrupted',error='Server restarted before this evaluation finished.')
            upsert_eval(item)
    yield
    for task in jobs.values(): task.cancel()
    if jobs: await asyncio.gather(*jobs.values(),return_exceptions=True)

app=FastAPI(title='Clinical Note Review',version='0.1.0',lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])

@app.middleware('http')
async def local_requests(request: Request, call_next):
    if request.headers.get('sec-fetch-site') == 'cross-site':
        return JSONResponse({'detail':'Cross-site access is not allowed.'},403)
    try:
        scheme, credential = request.headers.get('authorization','').split(' ',1)
        decoded = base64.b64decode(credential, validate=True).decode('utf-8')
        valid = scheme.lower() == 'basic' and secrets.compare_digest(decoded.encode(), ('adeel:'+ACCESS_PASSWORD).encode())
    except (ValueError, UnicodeError):
        valid = False
    if not valid:
        return JSONResponse({'detail':'Local login required.'},401,headers={'WWW-Authenticate':'Basic realm="Clinical Note Review", charset="UTF-8"','Cache-Control':'no-store'})
    if request.method in ('POST','PUT','PATCH','DELETE'):
        origin=request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'Cross-origin writes are not allowed.'},403)
        if request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'detail':'Cross-site writes are not allowed.'},403)
        if request.headers.get('content-type','').split(';')[0] != 'application/json':
            return JSONResponse({'detail':'Use application/json.'},415)
        if len(await request.body())>120000:
            return JSONResponse({'detail':'Request exceeds 120 KB.'},413)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    response.headers['Cross-Origin-Resource-Policy']='same-origin'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response

@app.get('/api/config')
def config():
    return {'local_model':'qwen3:4b','local_supported':True,'live_available':bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')),'model':os.getenv('OPENAI_MODEL'),'demo':'Extractive rules; no LLM calls','storage':'Local SQLite','version':'0.1.0'}

@app.get('/api/samples')
def samples():
    initial={'id':'sample-visit','category':'Walkthrough','title':'Routine visit · synthetic','transcript':'Clinician: What brings you in today?\nPatient: I have had a dry cough for three days.\nClinician: Have you had a fever?\nPatient: No fever, and I have not felt short of breath.\nPatient: My mother has asthma. I do not have that diagnosis.\nClinician: Vitals: temperature is 37 C.\nClinician: Plan: We will review your symptom diary at follow-up.'}
    return [initial]+[{k:v for k,v in c.items() if k!='checks'} for c in CASES]

@app.get('/api/encounters')
def encounters():
    return [{k:r.get(k) for k in ('id','title','status','revision','created_at','provider','model','latency_ms')} for r in store.list_records('encounters')]

@app.get('/api/encounters/{id}')
def encounter(id:str):
    record=store.get(id)
    if not record: raise HTTPException(404,'Encounter not found.')
    return {**record,'history':store.revisions(id)}

@app.post('/api/generate')
async def create(req:Generate):
    try:
        result=await generate(req.transcript,req.provider,req.prompt_version)
        record=store.create(req.title,req.transcript,result)
        store.event({'type':'generation','status':'success','provider':req.provider,'latency_ms':result['latency_ms'],'usage':result['usage'],'estimated_cost_usd':result['estimated_cost_usd']})
        return {**record,'history':store.revisions(record['id'])}
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    except GenerationError as exc:
        store.event({'type':'generation','status':'failed','provider':req.provider})
        raise HTTPException(502,str(exc))

@app.put('/api/encounters/{id}')
def review(id:str,req:Review):
    record=store.get(id)
    if not record: raise HTTPException(404,'Encounter not found.')
    if req.approve and not req.review_confirmed:
        raise HTTPException(422,'Confirm that you reviewed every statement and all review flags before approval.')
    try:
        validate_references(req.note,record['turns'])
        result=store.save_review(id,req,review_flags(req.note,record['turns']))
    except ValueError as exc: raise HTTPException(422,str(exc))
    except store.Conflict as exc: raise HTTPException(409,str(exc))
    return {**result,'history':store.revisions(id)}

@app.get('/api/encounters/{id}/export')
def export(id:str):
    record=encounter(id)
    return JSONResponse(record,headers={'Content-Disposition':f'attachment; filename="note-{id}.json"'})

def upsert_eval(record):
    with store.connect() as db:
        db.execute('INSERT OR REPLACE INTO evaluations VALUES (?,?)',(record['id'],json.dumps(record)))

async def run_job(id,req):
    try:
        result=await evaluate(req.provider,req.prompt_version,req.limit)
        result['id']=id
        upsert_eval(result)
    finally: jobs.pop(id,None)

@app.post('/api/evaluations')
async def start_eval(req:EvalRequest):
    if len(jobs)>=2: raise HTTPException(429,'Two evaluations are already running. Wait for one to finish.')
    if req.provider=='openai' and not config()['live_available']: raise HTTPException(422,'Configure the model API before running live evaluations.')
    id=str(uuid4())
    item={'id':id,'created_at':store.now(),'provider':req.provider,'prompt_version':req.prompt_version,'status':'running','total':req.limit}
    upsert_eval(item)
    jobs[id]=asyncio.create_task(run_job(id,req))
    return item

@app.get('/api/evaluations')
def evaluations(): return store.list_records('evaluations')

@app.get('/api/metrics')
def metrics():
    events=store.list_records('events')
    good=[e for e in events if e['status']=='success']
    records=store.list_records('encounters')
    return {'requests':len(events),'failures':sum(e['status']=='failed' for e in events),'approved':sum(r['status']=='approved' for r in records),'drafts':sum(r['status']=='draft' for r in records),'demo_requests':sum(e['provider']=='demo' for e in events),'local_requests':sum(e['provider']=='ollama' for e in events),'live_requests':sum(e['provider']=='openai' for e in events),'median_latency_ms':round(statistics.median([e['latency_ms'] for e in good]),2) if good else None,'events':events[:20],'window':'Most recent 200 generation events; evaluation requests excluded.'}

app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
@app.get('/')
def index(): return FileResponse(ROOT/'static'/'index.html')
