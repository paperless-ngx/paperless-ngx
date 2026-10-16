"""Compare the reference native RapidFuzz path and Rust on identical synthetic data."""

# ruff: noqa: INP001

import argparse
import hashlib
import json
import math
import platform
import random
import resource
import statistics
import subprocess
import sys
import time
from itertools import combinations
from pathlib import Path


def synthetic_documents(count: int, length: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    alphabet = "Invoice ABC xyz 0123456789 .,\nİΣé中文\u0661😀\u0301"
    base = "".join(rng.choices(alphabet, k=length))
    documents = []
    for index in range(count):
        text = list(base if index % 3 else "".join(rng.choices(alphabet, k=length)))
        for _ in range(length // 20):
            text[rng.randrange(length)] = rng.choice(alphabet)
        documents.append("".join(text))
    return documents


def measure(args):
    documents = synthetic_documents(args.documents, args.length, args.seed)
    if args.engine == "reference":
        import rapidfuzz
        from rapidfuzz.fuzz_cpp import ratio
        from rapidfuzz.utils_cpp import default_process

        if rapidfuzz.__version__ != "3.14.6":
            raise SystemExit("Benchmark requires reference RapidFuzz 3.14.6")

        def score(first, second, cutoff):
            return ratio(
                default_process(first),
                default_process(second),
                score_cutoff=cutoff,
            )

        version = rapidfuzz.__version__
    else:
        from paperless_fuzzy_native import process_and_ratio as score

        version = "paperless-fuzzy-native 0.1.0 / rapidfuzz-rs 0.5.0"
    score(documents[0], documents[1], args.cutoff)
    started = time.perf_counter()
    scores = [
        score(first, second, args.cutoff)
        for first, second in combinations(documents, 2)
    ]
    elapsed = time.perf_counter() - started
    return {
        "engine": args.engine,
        "version": version,
        "seconds": elapsed,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "pairs": len(scores),
        "matches": sum(score >= args.cutoff for score in scores),
        "score_sum": math.fsum(scores),
        "input_sha256": hashlib.sha256("\0".join(documents).encode()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=int, default=64)
    parser.add_argument("--length", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=4004)
    parser.add_argument("--cutoff", type=float, default=85.0)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--engine",
        choices=["reference", "rust"],
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if args.documents < 2 or args.length < 1 or args.repeats < 1:
        parser.error("Need at least 2 documents, positive length and repeats")
    if args.engine:
        sys.stdout.write(json.dumps(measure(args)) + "\n")
        return
    results = []
    for _ in range(args.repeats):
        for engine in ("reference", "rust"):
            output = subprocess.check_output(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    *sys.argv[1:],
                    "--engine",
                    engine,
                ],
                text=True,
            )
            results.append(json.loads(output))
    first = results[0]
    for result in results:
        assert result["input_sha256"] == first["input_sha256"]
        assert result["matches"] == first["matches"]
        assert math.isclose(
            result["score_sum"],
            first["score_sum"],
            abs_tol=1e-6,
            rel_tol=0,
        )
    report = {
        "platform": platform.platform(),
        "python": sys.version,
        "parameters": vars(args),
        "runs": results,
        "median_seconds": {
            engine: statistics.median(
                result["seconds"] for result in results if result["engine"] == engine
            )
            for engine in ("reference", "rust")
        },
    }
    sys.stdout.write(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
