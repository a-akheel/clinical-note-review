import json
from pathlib import Path
from uuid import uuid4
from .engine import generate
from .store import now

CASES = json.loads((Path(__file__).resolve().parent.parent/'evaluations'/'cases.json').read_text())

def score(note, checks):
    results=[]
    for check in checks:
        text=' '.join(c['text'] for c in note[check['section']]).casefold()
        passed=(not note[check['section']]) if check.get('empty') else ((check['contains'].casefold() in text) == check['expected'])
        results.append({**check,'passed':passed})
    return results

async def evaluate(provider, version, limit=30):
    rows=[]
    for case in CASES[:limit]:
        try:
            result=await generate(case['transcript'],provider,version)
            checks=score(result['note'],case['checks'])
            rows.append({'case_id':case['id'],'title':case['title'],'category':case['category'],'passed':all(c['passed'] for c in checks),'checks':checks,'latency_ms':result['latency_ms'],'note':result['note'],'error':None,'usage':result['usage'],'estimated_cost_usd':result['estimated_cost_usd']})
        except Exception as exc:
            rows.append({'case_id':case['id'],'title':case['title'],'category':case['category'],'passed':False,'checks':[],'latency_ms':None,'note':None,'error':str(exc)[:250]})
    return {'id':str(uuid4()),'created_at':now(),'provider':provider,'prompt_version':version,'status':'completed','total':len(rows),'passed':sum(r['passed'] for r in rows),'checks_passed':sum(c['passed'] for r in rows for c in r['checks']),'checks_total':sum(len(r['checks']) for r in rows),'results':rows,'semantic_review':'not performed','method':'Semantic meaning is not graded: substring and section assertions only. This is a regression score, not clinical accuracy.'}
