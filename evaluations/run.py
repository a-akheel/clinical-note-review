import argparse
import asyncio
import json
from pathlib import Path
from app.evaluation import evaluate

parser=argparse.ArgumentParser()
parser.add_argument('--provider',choices=['demo','openai','ollama'],default='demo')
parser.add_argument('--version',choices=['baseline-v1','grounded-v2'],default='grounded-v2')
parser.add_argument('--output',default='evaluations/latest.json')
args=parser.parse_args()
result=asyncio.run(evaluate(args.provider,args.version))
Path(args.output).write_text(json.dumps(result,indent=2))
print(f"{result['passed']}/{result['total']} cases passed ({result['provider']}, {result['prompt_version']}). Not clinical accuracy.")
