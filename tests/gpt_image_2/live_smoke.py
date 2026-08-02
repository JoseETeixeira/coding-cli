"""OPT-IN live smoke. This is the only script here that spends money.

Deliberately NOT a pytest module and deliberately not collectable: it has no
top-level `test_` function and it refuses to run without an explicit
confirmation flag. Requirements IMG-REQ-011 authorises exactly one minimal live
generation after every deterministic gate has passed.

Run:
    py -3.12 tests/gpt_image_2/live_smoke.py --i-understand-this-costs-money

It uses quality=low, 1024x1024, n=1 — the cheapest request that still proves
the real integration. Records only safe metadata: model, request id, timing,
output path, dimensions, byte count. Never records the prompt response body,
never records the credential.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gpt_image_2 import api, constants, credentials, errors, images, models  # noqa: E402

SMOKE_PROMPT = (
    "A single bright red ceramic coffee mug centered on a plain white studio "
    "background, soft even lighting, photographed from slightly above."
)


async def run(output_dir: Path) -> int:
    started = time.monotonic()
    budget = api.Budget()

    request = models.validate_generate(
        prompt=SMOKE_PROMPT,
        quality="low",  # cheapest tier — this is a compatibility proof, not art
        size="1024x1024",
        n=1,
        output_format="png",
        output_dir=str(output_dir),
        basename="live-smoke",
    )

    try:
        secret = credentials.resolve_api_key()
    except errors.ImageToolError as exc:
        print(json.dumps({"result": "BLOCKED", **exc.to_payload()}, indent=2))
        return 2

    try:
        result = await api.call_generate(request, secret=secret, budget=budget)
    except errors.ImageToolError as exc:
        # An organization-verification, billing, or moderation failure is an
        # external blocker to REPORT, never a reason to weaken a safeguard.
        print(json.dumps({"result": "BLOCKED", **exc.to_payload()}, indent=2))
        return 2

    decoded = images.decode_image_payload(
        result.payloads[0], request.output_format, index=0
    )
    path = images.publish_atomic(
        decoded.data, request.output_dir, request.basename, request.extension
    )

    evidence = {
        "result": "PASS",
        "model": constants.MODEL,
        "operation": "generate",
        "requested": {"quality": "low", "size": "1024x1024", "n": 1, "output_format": "png"},
        "request_id": result.request_id,
        "attempts": result.attempts,
        "usage": result.usage,
        "elapsed_s": round(time.monotonic() - started, 2),
        "output_path": str(path),
        "output_bytes": decoded.size_bytes,
        "output_dimensions": f"{decoded.width}x{decoded.height}",
        "visual_inspection": "REQUIRED — open the file above and confirm it "
        "materially follows the prompt. HTTP success alone does not pass this gate.",
    }
    print(json.dumps(evidence, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--i-understand-this-costs-money",
        action="store_true",
        help="required; without it this script refuses to run",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / ".batman" / "create-gpt-image-2-skill-and-tool" / "evidence"),
    )
    args = parser.parse_args()

    if not getattr(args, "i_understand_this_costs_money"):
        print(
            "Refusing to run: this script makes a real, billed OpenAI request.\n"
            "Re-run with --i-understand-this-costs-money if that is intended.",
            file=sys.stderr,
        )
        return 1

    return asyncio.run(run(Path(args.output_dir)))


if __name__ == "__main__":
    raise SystemExit(main())
