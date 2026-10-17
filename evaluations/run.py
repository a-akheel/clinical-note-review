import argparse
import asyncio
import json
from pathlib import Path
from app.evaluation import evaluate

parser = argparse.ArgumentParser()
parser.add_argument("--provider", choices=["demo", "openai", "ollama"], default="demo")
parser.add_argument(
    "--version",
    choices=["baseline-v1", "grounded-v2", "corrections-v3"],
    default="grounded-v2",
)
parser.add_argument("--cases", default="evaluations/cases.json")
parser.add_argument("--output", default="evaluations/latest.json")
args = parser.parse_args()
cases = json.loads(Path(args.cases).read_text())
result = asyncio.run(
    evaluate(args.provider, args.version, limit=len(cases), cases=cases)
)
Path(args.output).write_text(json.dumps(result, indent=2))
print(
    f"{result['passed']}/{result['total']} cases passed ({result['provider']}, {result['prompt_version']}). Not clinical accuracy."
)
