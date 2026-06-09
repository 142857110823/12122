"""Smoke test the smart assistant OpenAI backend without exposing secrets.

Run with an `OPENAI_API_KEY` in the process environment or project `.env`.
Use `--require-key` in acceptance checks when a real API response is required.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent  # noqa: E402


def _minimal_state() -> dict:
    return {
        "uploads": {},
        "feature_table": None,
        "models": {},
        "best_model": None,
        "predictions": None,
        "workflow_stage": "idle",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the smart assistant OpenAI backend.")
    parser.add_argument(
        "--require-key",
        action="store_true",
        help="Fail when OPENAI_API_KEY is unavailable instead of running only fallback smoke.",
    )
    parser.add_argument(
        "--message",
        default="请用一句话回复：智能小助手 API 烟测成功。",
        help="Prompt sent to the assistant during the smoke test.",
    )
    args = parser.parse_args()

    assistant = agent.Agent()
    ok, reason = assistant.backend.available()
    if not ok:
        if args.require_key:
            print(f"FAIL: OpenAI backend unavailable: {reason}")
            return 2
        response = assistant.respond(args.message, _minimal_state())
        if response.get("error") or not str(response.get("text") or "").strip():
            print("FAIL: fallback response is empty or errored.")
            return 1
        print(f"SKIP_REAL_API: {reason}; fallback response is non-empty.")
        return 0

    response = assistant.respond(args.message, _minimal_state())
    text = str(response.get("text") or "").strip()
    if response.get("error") or not text:
        print("FAIL: OpenAI backend returned an empty or errored response.")
        return 1
    print(f"OK_REAL_API: backend={assistant.settings.backend}; model={assistant.settings.openai_model}; chars={len(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
