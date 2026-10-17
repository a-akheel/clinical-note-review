"""Export a review packet or validate completed human annotations."""

import argparse
import json
from pathlib import Path
from app.review import make_packet, summarize_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--cases", default="evaluations/cases.json")
    parser.add_argument("--annotations")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text())
    result = (
        summarize_review(json.loads(Path(args.annotations).read_text()), report)
        if args.annotations
        else make_packet(report, json.loads(Path(args.cases).read_text()))
    )
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
