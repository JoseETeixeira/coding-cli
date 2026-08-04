"""Command line for optical compression: inspect, compress, retrieve, benchmark.

    python -m optical_compression estimate --file big.log
    python -m optical_compression compress --file big.log --density balanced
    python -m optical_compression retrieve --digest 3f9a...
    python -m optical_compression benchmark --suite all
    python -m optical_compression prune --days 14
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import benchmark as benchmark_module
from . import constants, guard, pipeline
from .render import preflight
from .store import OpticalStore


def _read_input(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return Path(args.file).read_text(encoding="utf-8", errors="replace")
    return sys.stdin.read()


def cmd_estimate(args: argparse.Namespace) -> int:
    text = _read_input(args)
    verdict = guard.scan(text)
    report = {
        "chars": len(text),
        "guard": verdict.to_dict(),
        "max_safe_density": guard.max_safe_density(text),
        "densities": {
            name: preflight(text, density=name) for name in sorted(constants.DENSITIES)
        },
    }
    print(json.dumps(report, indent=2))
    return 0


def cmd_compress(args: argparse.Namespace) -> int:
    text = _read_input(args)
    store = OpticalStore(args.store)
    outcome = pipeline.compress(
        text,
        density=args.density,
        store=store,
        enforce_guard=args.enforce_guard,
        source=args.file or "stdin",
    )
    report = outcome.to_dict()

    if outcome.accepted and outcome.result is not None and args.outdir:
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        written = []
        for page in outcome.result.pages:
            target = outdir / f"{outcome.digest}_p{page.index}.png"
            target.write_bytes(page.png)
            written.append(str(target))
        report["written"] = written
        report["framing"] = pipeline.framing_text(outcome, source=args.file)

    print(json.dumps(report, indent=2))
    return 0 if outcome.accepted else 1


def cmd_retrieve(args: argparse.Namespace) -> int:
    store = OpticalStore(args.store)
    stored = store.get_original(args.digest)
    if stored is None:
        print(json.dumps({"status": "not_found", "digest": args.digest}, indent=2))
        return 1
    span = store.slice_original(args.digest, start=args.start, length=args.length)
    if args.raw:
        sys.stdout.write(span or "")
    else:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "digest": stored.digest,
                    "total_chars": stored.chars,
                    "returned_chars": len(span or ""),
                    "text": span,
                },
                indent=2,
            )
        )
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    report = benchmark_module.run(args.suite, Path(args.outdir) if args.outdir else None)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


def cmd_stats(args: argparse.Namespace) -> int:
    store = OpticalStore(args.store)
    print(json.dumps({"store": store.stats(), "densities": constants.DENSITIES}, indent=2))
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    store = OpticalStore(args.store)
    print(json.dumps({"removed": store.prune(older_than_days=args.days)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="optical_compression")
    parser.add_argument("--store", default=None, help="store root (default: ./)")
    sub = parser.add_subparsers(dest="command", required=True)

    estimate = sub.add_parser("estimate", help="predict the outcome without rendering")
    estimate.add_argument("--file")
    estimate.set_defaults(func=cmd_estimate)

    compress = sub.add_parser("compress", help="render a payload to pages")
    compress.add_argument("--file")
    compress.add_argument("--density", default=constants.DEFAULT_DENSITY,
                          choices=sorted(constants.DENSITIES))
    compress.add_argument("--outdir")
    compress.add_argument("--enforce-guard", action="store_true",
                          help="refuse identifier-bearing payloads, as the hook does")
    compress.set_defaults(func=cmd_compress)

    retrieve = sub.add_parser("retrieve", help="fetch exact original text by digest")
    retrieve.add_argument("--digest", required=True)
    retrieve.add_argument("--start", type=int, default=0)
    retrieve.add_argument("--length", type=int, default=None)
    retrieve.add_argument("--raw", action="store_true")
    retrieve.set_defaults(func=cmd_retrieve)

    bench = sub.add_parser("benchmark", help="reproduce the published claims")
    bench.add_argument("--suite", default="all",
                       choices=["all", "token_model", "density", "cipher", "cache",
                                "guard", "fidelity"])
    bench.add_argument("--outdir", default=None)
    bench.set_defaults(func=cmd_benchmark)

    stats = sub.add_parser("stats", help="store statistics")
    stats.set_defaults(func=cmd_stats)

    prune = sub.add_parser("prune", help="drop entries past retention")
    prune.add_argument("--days", type=int, default=constants.DEFAULT_RETENTION_DAYS)
    prune.set_defaults(func=cmd_prune)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
