"""Build a distributable Figma handoff ZIP.

The bundle is a developer/Figma Desktop handoff package. It is not a native
.fig file, and the generated manifest keeps that boundary explicit.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs" / "figma_handoff"
RUNS = ROOT / "data" / "runs"


def latest_file(pattern: str) -> Path | None:
    candidates = sorted(RUNS.glob(pattern))
    return candidates[-1] if candidates else None


def add_file(zf: zipfile.ZipFile, path: Path, arcname: str, included: list[dict]) -> None:
    if not path.exists():
        return
    zf.write(path, arcname)
    included.append({"path": str(path), "arcname": arcname, "size_bytes": path.stat().st_size})


def add_tree(zf: zipfile.ZipFile, root: Path, prefix: str, included: list[dict]) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            add_file(zf, path, f"{prefix}/{path.relative_to(root).as_posix()}", included)


def main() -> int:
    run_id = "figma_handoff_bundle_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    latest_audit = latest_file("figma_handoff_audit_*/figma_handoff_audit.json")
    latest_visual = latest_file("ui_visual_qa_*/visual_qa_manifest.json")
    native_fig_files = sorted(
        str(path)
        for pattern in ("*.fig", "*.figjam")
        for path in ROOT.rglob(pattern)
    )
    native_receipt_path = HANDOFF / "native-figma-receipt.json"
    native_receipt = {}
    if native_receipt_path.exists():
        native_receipt = json.loads(native_receipt_path.read_text(encoding="utf-8-sig"))
    native_receipt_complete = (
        native_receipt.get("status") == "verified_native_figma_artifact"
        and bool(native_receipt.get("inspection_complete"))
    )
    acceptance_path = HANDOFF / "acceptance-matrix.json"
    acceptance_matrix = {}
    if acceptance_path.exists():
        acceptance_matrix = json.loads(acceptance_path.read_text(encoding="utf-8-sig"))
    inspection_path = HANDOFF / "native-figma-inspection-checklist.json"
    inspection_checklist = {}
    if inspection_path.exists():
        inspection_checklist = json.loads(inspection_path.read_text(encoding="utf-8-sig"))

    included: list[dict] = []
    zip_path = out_dir / f"{run_id}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        add_tree(zf, HANDOFF, "docs/figma_handoff", included)
        add_file(zf, ROOT / "docs" / "UI_DESIGN_SYSTEM.md", "docs/UI_DESIGN_SYSTEM.md", included)
        add_file(zf, ROOT / "scripts" / "figma_handoff_audit.py", "scripts/figma_handoff_audit.py", included)
        add_file(zf, ROOT / "scripts" / "register_native_figma_artifact.py", "scripts/register_native_figma_artifact.py", included)
        add_file(zf, ROOT / "scripts" / "ui_visual_qa.py", "scripts/ui_visual_qa.py", included)
        add_file(zf, ROOT / "app.py", "source/app.py", included)
        if latest_audit:
            add_file(zf, latest_audit, "evidence/latest_figma_handoff_audit.json", included)
        if latest_visual:
            add_file(zf, latest_visual, "evidence/latest_visual_qa_manifest.json", included)

    manifest = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "bundle_zip": str(zip_path),
        "included_count": len(included),
        "included_files": included,
        "latest_audit_manifest": str(latest_audit) if latest_audit else None,
        "latest_visual_qa_manifest": str(latest_visual) if latest_visual else None,
        "native_source": {
            "fig_or_figjam_files_found": native_fig_files,
            "receipt_path": str(native_receipt_path),
            "receipt_status": native_receipt.get("status"),
            "receipt_figma_url": native_receipt.get("figma_url"),
            "receipt_local_artifact_path": native_receipt.get("local_artifact_path"),
            "receipt_inspection_complete": bool(native_receipt.get("inspection_complete")),
            "complete": bool(native_fig_files) or native_receipt_complete,
            "claim_boundary": "This ZIP is a handoff/rebuild package, not a native Figma source file.",
        },
        "acceptance_matrix": {
            "path": str(acceptance_path),
            "overall_status": acceptance_matrix.get("overall_status"),
            "missing_external_fulfillment": [
                item.get("id")
                for item in acceptance_matrix.get("requirements", [])
                if item.get("status") == "missing_external_fulfillment"
            ] if acceptance_matrix else [],
        },
        "native_inspection_checklist": {
            "path": str(inspection_path),
            "schema": inspection_checklist.get("schema"),
            "required_page_count": len(inspection_checklist.get("required_pages", [])) if inspection_checklist else 0,
            "prototype_check_count": len(inspection_checklist.get("prototype_checks", [])) if inspection_checklist else 0,
            "motion_check_count": len(inspection_checklist.get("motion_checks", [])) if inspection_checklist else 0,
            "source_of_truth_check_count": len(inspection_checklist.get("source_of_truth_checks", [])) if inspection_checklist else 0,
        },
        "required_external_completion": [
            "Run docs/figma_handoff/figma_plugin/manifest.json inside Figma Desktop or a working Figma MCP.",
            "Inspect EvidencePlatform Tokens, Components, Design System Spec, Prototype, Interactive Flow, Motion System, Developer Handoff, and Acceptance Evidence pages.",
            "Save/export the generated Figma file and record the .fig/.figjam artifact or verified Figma URL with scripts/register_native_figma_artifact.py plus explicit inspection confirmations.",
        ],
    }

    manifest_path = out_dir / "figma_handoff_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(manifest_path, out_dir / "README_BUNDLE_MANIFEST.json")

    print(json.dumps({
        "status": "ok",
        "bundle_zip": str(zip_path),
        "manifest": str(manifest_path),
        "native_complete": manifest["native_source"]["complete"],
        "included_count": len(included),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
