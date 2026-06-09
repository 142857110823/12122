"""Register an externally produced native Figma artifact for audit.

This script does not create a Figma file. It records evidence after the
Figma Desktop plugin or a Figma MCP workflow has produced a native artifact
or verified URL.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs" / "figma_handoff"
RUNS = ROOT / "data" / "runs"
RECEIPT_PATH = HANDOFF / "native-figma-receipt.json"
CHECKLIST_PATH = HANDOFF / "native-figma-inspection-checklist.json"
PREVIEW_PATH = HANDOFF / "interactive-prototype-preview.html"

REQUIRED_PAGES = [
    "EvidencePlatform Tokens",
    "EvidencePlatform Components",
    "EvidencePlatform Design System Spec",
    "EvidencePlatform Prototype",
    "EvidencePlatform Interactive Flow",
    "EvidencePlatform Motion System",
    "EvidencePlatform Developer Handoff",
    "EvidencePlatform Acceptance Evidence",
    "EvidencePlatform Native Inspection Checklist",
]

REQUIRED_INTERACTION_CHECKS = [
    "One-click P0-P3 flow edge exists",
    "Export evidence bundle edge exists",
    "BLOCK state prevents next-stage progression",
    "PASS_WITH_RISKS remains visible",
]

REQUIRED_MOTION_CHECKS = [
    "PASS_WITH_RISKS pulse is represented",
    "BLOCK shake/error emphasis is represented",
    "No fake progress animation is introduced",
]

FIGMA_URL_RE = re.compile(r"^https://(www\.)?figma\.com/(file|design|proto|board)/[A-Za-z0-9]+")


def load_inspection_checklist() -> dict:
    if not CHECKLIST_PATH.exists():
        return {}
    try:
        return json.loads(CHECKLIST_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register native Figma source/prototype evidence.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fig", help="Path to an exported .fig file.")
    source.add_argument("--figjam", help="Path to an exported .figjam file.")
    source.add_argument("--url", help="Verified Figma file/prototype URL.")
    parser.add_argument("--verified-by", default="", help="Person/tool that inspected the artifact.")
    parser.add_argument("--notes", default="", help="Short inspection notes.")
    parser.add_argument("--allow-missing-local", action="store_true", help="Record a local path even if it is not accessible on this machine.")
    parser.add_argument("--confirm-pages", action="store_true", help="Confirm all required generated Figma pages were inspected.")
    parser.add_argument("--confirm-interactions", action="store_true", help="Confirm required prototype interactions and BLOCK behavior were inspected.")
    parser.add_argument("--confirm-motion", action="store_true", help="Confirm required motion/microinteraction states were inspected.")
    parser.add_argument("--confirm-source-truth", action="store_true", help="Confirm the file preserves app.py/tools.py as the source of truth and adds no second frontend.")
    parser.add_argument("--confirm-all", action="store_true", help="Set all inspection confirmations at once.")
    return parser.parse_args()


def validate_source(args: argparse.Namespace) -> tuple[str, str, list[str]]:
    blockers: list[str] = []
    if args.url:
        if not FIGMA_URL_RE.match(args.url.strip()):
            blockers.append("Figma URL must start with https://figma.com/file, /design, /proto, or /board.")
        return "figma_url", args.url.strip(), blockers

    raw_path = args.fig or args.figjam
    path = Path(raw_path).expanduser()
    expected_suffix = ".fig" if args.fig else ".figjam"
    if path.suffix.lower() != expected_suffix:
        blockers.append(f"Expected a {expected_suffix} file.")
    if not path.exists() and not args.allow_missing_local:
        blockers.append("Local native artifact path does not exist. Use --allow-missing-local only for handoff records from another machine.")
    return expected_suffix.lstrip("."), str(path), blockers


def main() -> int:
    args = parse_args()
    artifact_type, artifact_value, blockers = validate_source(args)
    checklist = load_inspection_checklist()
    required_pages = [
        item.get("name")
        for item in checklist.get("required_pages", [])
        if item.get("name")
    ] or REQUIRED_PAGES
    interaction_checks = checklist.get("prototype_checks") or REQUIRED_INTERACTION_CHECKS
    motion_checks = checklist.get("motion_checks") or REQUIRED_MOTION_CHECKS
    source_of_truth_checks = checklist.get("source_of_truth_checks") or [
        "Workflow actions map back to app.py/tools.py",
        "No second frontend is introduced",
        "Scientific/model validity is not claimed from Figma evidence",
    ]
    confirmations = {
        "required_pages_inspected": bool(args.confirm_pages or args.confirm_all),
        "prototype_interactions_inspected": bool(args.confirm_interactions or args.confirm_all),
        "motion_states_inspected": bool(args.confirm_motion or args.confirm_all),
        "source_of_truth_verified": bool(args.confirm_source_truth or args.confirm_all),
    }
    if not args.verified_by.strip():
        blockers.append("--verified-by is required for native completion evidence.")
    for key, value in confirmations.items():
        if not value:
            blockers.append(f"Missing confirmation: {key}.")
    inspection_complete = not blockers and all(confirmations.values())
    now = datetime.now().isoformat(timespec="seconds")
    run_id = "native_figma_registration_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    receipt = {
        "schema": "evidence_platform.native_figma_receipt.v1",
        "status": "verified_native_figma_artifact" if inspection_complete else "blocked",
        "registered_at": now,
        "verified_at": now if inspection_complete else "",
        "verified_by": args.verified_by,
        "artifact_type": artifact_type,
        "local_artifact_path": artifact_value if artifact_type in {"fig", "figjam"} else "",
        "figma_url": artifact_value if artifact_type == "figma_url" else "",
        "inspection_checklist_path": str(CHECKLIST_PATH),
        "inspection_checklist_schema": checklist.get("schema"),
        "required_pages_inspected": required_pages,
        "interaction_checks": interaction_checks,
        "motion_checks": motion_checks,
        "source_of_truth_checks": source_of_truth_checks,
        "inspection_confirmations": confirmations,
        "inspection_complete": inspection_complete,
        "blockers": blockers,
        "notes": args.notes,
        "claim_boundary": "This receipt records native Figma artifact/prototype evidence only; it does not prove scientific/model validity.",
        "local_preview_reference": str(PREVIEW_PATH),
    }

    RECEIPT_PATH.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    out_path = out_dir / "native-figma-receipt.json"
    out_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": receipt["status"],
        "receipt": str(RECEIPT_PATH),
        "run_receipt": str(out_path),
        "blockers": blockers,
    }, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
