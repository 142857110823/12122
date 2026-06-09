"""Audit the Figma handoff package without claiming native .fig completion.

The script checks repository artifacts that can be verified locally and writes a
manifest under data/runs/figma_handoff_audit_<timestamp>/.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs" / "figma_handoff"
PLUGIN = HANDOFF / "figma_plugin"
RUNS = ROOT / "data" / "runs"

REQUIRED_ASSETS = [
    ROOT / "docs" / "UI_DESIGN_SYSTEM.md",
    HANDOFF / "README.md",
    HANDOFF / "design-tokens.json",
    HANDOFF / "component-library.json",
    HANDOFF / "prototype-map.json",
    HANDOFF / "interactive-prototype-preview.html",
    HANDOFF / "high-fidelity-evidence-platform.svg",
    HANDOFF / "responsive-spec.json",
    HANDOFF / "interaction-states.json",
    HANDOFF / "acceptance-matrix.json",
    HANDOFF / "native-figma-inspection-checklist.json",
    HANDOFF / "native-figma-receipt.template.json",
    HANDOFF / "responsive-reference.svg",
    HANDOFF / "accessibility-qa-checklist.md",
    PLUGIN / "manifest.json",
    PLUGIN / "code.js",
    PLUGIN / "README.md",
]

PLUGIN_MARKERS = [
    "EvidencePlatform Tokens",
    "EvidencePlatform Components",
    "EvidencePlatform Design System Spec",
    "EvidencePlatform Prototype",
    "EvidencePlatform Interactive Flow",
    "EvidencePlatform Motion System",
    "EvidencePlatform Developer Handoff",
    "EvidencePlatform Acceptance Evidence",
    "EvidencePlatform Native Inspection Checklist",
    "Master / CommandHero",
    "Master / GateWorkbench",
    "Master / ResultWorkbench",
    "Master / OptionAction",
    "GateCard / PASS_WITH_RISKS",
    "GateCard / BLOCK",
    "Component Set / GateCard Verdicts",
    "OptionAction / default",
    "OptionAction / hover",
    "OptionAction / running",
    "OptionAction / disabled",
    "OptionAction / blocked",
    "Component Set / OptionAction States",
    "combineAsVariants",
    "Desktop Evidence Platform",
    "Tablet Evidence Platform",
    "Mobile Evidence Platform",
    "Prototype Edge / One-click P0-P3",
    "Prototype Edge / Export evidence bundle",
    "BLOCK edge rule",
    "wirePrototype",
    "source.reactions",
    "Motion Spec / PASS_WITH_RISKS Pulse",
    "Motion Spec / BLOCK Shake",
    "Motion Rule / no fake progress",
    "Type Scale / Display 44",
    "Spacing Scale / 8pt Grid",
    "Color Role / PASS_WITH_RISKS Warning",
    "Layout Rule / Responsive Shell",
    "Source of Truth / app.py and tools.py",
    "Figma Save/Export Requirement",
    "Registration Path / native-figma-receipt",
    "evidence_platform.native_figma_inspection_checklist.v1",
    "Forbidden Claims Until Registered",
    "Paint Style / EvidencePlatform/Primary",
    "Paint Style / EvidencePlatform/Warning",
    "Paint Style / EvidencePlatform/Danger",
    "Text Style / EvidencePlatform/Display 44",
    "Text Style / EvidencePlatform/Body 14",
    "Effect Style / EvidencePlatform/Panel Lift",
    "Variable Collection / EvidencePlatform Tokens",
    "Variable / color/primary",
    "Variable / color/warning",
    "Variable / color/danger",
    "Variable / color/surface",
    "Variable / color/background",
    "createPaintStyle",
    "createTextStyle",
    "createEffectStyle",
    "figma.variables",
    "createVariableCollection",
    "createVariable",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def latest_visual_qa_manifest() -> str | None:
    candidates = sorted(RUNS.glob("ui_visual_qa_*/visual_qa_manifest.json"))
    return str(candidates[-1]) if candidates else None


def load_native_receipt() -> dict:
    receipt_path = HANDOFF / "native-figma-receipt.json"
    if not receipt_path.exists():
        return {}
    try:
        return json.loads(read_text(receipt_path))
    except Exception as exc:
        return {"status": "invalid", "error": str(exc), "path": str(receipt_path)}


def checklist_markers(checklist: dict) -> list[str]:
    """Flatten page names, page markers, and inspection checks into audit markers."""
    if not isinstance(checklist, dict):
        return []

    markers: list[str] = []
    for page in checklist.get("required_pages", []):
        if isinstance(page, dict):
            name = page.get("name")
            if name:
                markers.append(str(name))
            for marker in page.get("required_markers", []):
                markers.append(str(marker))

    for key in ("prototype_checks", "motion_checks", "source_of_truth_checks", "forbidden_claims_until_registered"):
        for marker in checklist.get(key, []):
            markers.append(str(marker))

    registration = checklist.get("registration_requirements", {})
    if isinstance(registration, dict):
        for key in ("script", "shortcut_flag", "must_write", "completion_status"):
            value = registration.get(key)
            if value:
                markers.append(str(value))
        for marker in registration.get("required_flags", []):
            markers.append(str(marker))

    return sorted(set(markers))


def main() -> int:
    run_id = "figma_handoff_audit_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    missing = [str(path) for path in REQUIRED_ASSETS if not path.exists()]
    small = [str(path) for path in REQUIRED_ASSETS if path.exists() and path.stat().st_size < 200]

    plugin_code = read_text(PLUGIN / "code.js") if (PLUGIN / "code.js").exists() else ""
    missing_markers = [marker for marker in PLUGIN_MARKERS if marker not in plugin_code]

    native_fig_files = sorted(
        str(path)
        for pattern in ("*.fig", "*.figjam")
        for path in ROOT.rglob(pattern)
    )
    native_receipt = load_native_receipt()
    receipt_status = native_receipt.get("status")
    receipt_url = native_receipt.get("figma_url")
    receipt_local_path = native_receipt.get("local_artifact_path")
    receipt_inspection_complete = bool(native_receipt.get("inspection_complete"))
    receipt_complete = (
        receipt_status == "verified_native_figma_artifact"
        and receipt_inspection_complete
        and (
            bool(receipt_url)
            or bool(receipt_local_path)
            or bool(native_fig_files)
        )
    )
    acceptance_matrix = {}
    acceptance_path = HANDOFF / "acceptance-matrix.json"
    if acceptance_path.exists():
        try:
            acceptance_matrix = json.loads(read_text(acceptance_path))
        except Exception:
            acceptance_matrix = {}
    inspection_checklist = {}
    inspection_path = HANDOFF / "native-figma-inspection-checklist.json"
    if inspection_path.exists():
        try:
            inspection_checklist = json.loads(read_text(inspection_path))
        except Exception:
            inspection_checklist = {}
    inspection_markers_required = checklist_markers(inspection_checklist)
    inspection_markers_missing = [
        marker for marker in inspection_markers_required
        if marker not in plugin_code
        and marker not in read_text(HANDOFF / "README.md")
        and marker not in read_text(PLUGIN / "README.md")
        and marker not in read_text(ROOT / "scripts" / "register_native_figma_artifact.py")
    ]
    status = "ok" if not missing and not small and not missing_markers and not inspection_markers_missing else "needs_attention"

    manifest = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "handoff_root": str(HANDOFF),
        "status": status,
        "assets": {
            "required_count": len(REQUIRED_ASSETS),
            "missing": missing,
            "too_small": small,
        },
        "figma_rebuild_plugin": {
            "path": str(PLUGIN),
            "markers_required": PLUGIN_MARKERS,
            "missing_markers": missing_markers,
            "claim": "Plugin can reconstruct editable Figma nodes and attempt prototype reactions only after it is run inside Figma Desktop.",
        },
        "native_source": {
            "fig_or_figjam_files_found": native_fig_files,
            "receipt_path": str(HANDOFF / "native-figma-receipt.json"),
            "receipt_status": receipt_status,
            "receipt_figma_url": receipt_url,
            "receipt_local_artifact_path": receipt_local_path,
            "receipt_inspection_complete": receipt_inspection_complete,
            "complete": bool(native_fig_files) or receipt_complete,
            "claim_boundary": "No local native Figma source is proven unless a .fig/.figjam artifact or verified Figma file URL is present.",
        },
        "acceptance_matrix": {
            "path": str(acceptance_path),
            "overall_status": acceptance_matrix.get("overall_status"),
            "requirement_count": len(acceptance_matrix.get("requirements", [])) if isinstance(acceptance_matrix, dict) else 0,
            "missing_external_fulfillment": [
                item.get("id")
                for item in acceptance_matrix.get("requirements", [])
                if item.get("status") == "missing_external_fulfillment"
            ] if isinstance(acceptance_matrix, dict) else [],
        },
        "native_inspection_checklist": {
            "path": str(inspection_path),
            "schema": inspection_checklist.get("schema"),
            "required_page_count": len(inspection_checklist.get("required_pages", [])) if isinstance(inspection_checklist, dict) else 0,
            "prototype_check_count": len(inspection_checklist.get("prototype_checks", [])) if isinstance(inspection_checklist, dict) else 0,
            "motion_check_count": len(inspection_checklist.get("motion_checks", [])) if isinstance(inspection_checklist, dict) else 0,
            "source_of_truth_check_count": len(inspection_checklist.get("source_of_truth_checks", [])) if isinstance(inspection_checklist, dict) else 0,
            "markers_required": inspection_markers_required,
            "missing_markers": inspection_markers_missing,
            "claim_boundary": inspection_checklist.get("claim_boundary") if isinstance(inspection_checklist, dict) else None,
        },
        "visual_qa": {
            "latest_manifest": latest_visual_qa_manifest(),
            "claim_boundary": "Rendered Streamlit screenshots do not prove native Figma source or scientific validity.",
        },
        "non_negotiables": [
            "Do not create a second frontend.",
            "Do not invent workflow buttons.",
            "Keep PASS_WITH_RISKS and BLOCK visible.",
            "Do not treat Figma visual quality as model/scientific validation.",
        ],
    }

    out_path = out_dir / "figma_handoff_audit.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "manifest": str(out_path)}, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
