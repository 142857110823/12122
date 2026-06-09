# Figma Handoff Package

This directory contains the design assets needed to reconstruct or inspect the current Streamlit evidence platform in Figma-like workflows without creating a second app frontend.

## Assets

- `design-tokens.json`: machine-readable colors, typography, radius, elevation, motion, and breakpoints.
- `component-library.json`: component inventory, slots, states, do/don't rules, and implementation mapping.
- `prototype-map.json`: screen-to-screen interaction map aligned with `app.py::get_options()` and `app.py::handle_action()`.
- `interactive-prototype-preview.html`: static clickable prototype walkthrough for human review of screen states, real tool bindings, gate semantics, responsive behavior, and motion boundaries. It is not a runnable platform frontend.
- `high-fidelity-evidence-platform.svg`: high-fidelity reference screen at `1440x1080` for Figma import or visual QA.
- `responsive-spec.json`: desktop/tablet/mobile frame behavior and layout rules.
- `interaction-states.json`: Figma variant/state matrix for buttons, gates, stage tiles, evidence rows, and downloads.
- `acceptance-matrix.json`: Goal3.0-style requirement-to-evidence matrix showing which Figma/UI requirements are locally verified, partially verified, or still require native Figma execution.
- `native-figma-inspection-checklist.json`: machine-readable page, interaction, motion, and source-of-truth checklist for the external native Figma inspection step.
- `native-figma-receipt.template.json`: evidence template for the external native Figma save/export step.
- `responsive-reference.svg`: multi-device reference board for desktop/tablet/mobile reconstruction.
- `accessibility-qa-checklist.md`: readability, keyboard, risk visibility, and scientific-integrity UX checklist.
- `../../scripts/ui_visual_qa.py`: rendered desktop/tablet/mobile screenshot QA runner for the Streamlit evidence platform.
- `figma_plugin/`: Figma development plugin rebuild kit that can create editable token, component, and prototype pages inside Figma Desktop.

## Implemented Workbench Components

- `GateWorkbench`: in-app P0-P3 status board derived from real session state; not a substitute for formal gate JSON.
- `ResultWorkbench`: tabbed result review surface for model ranking, explanation previews, evidence downloads, and gate indexes.

## Source Of Truth

The runnable UI remains `../app.py`. These files are handoff and reconstruction assets, not a second frontend and not a substitute for real tool execution.

## Interactive Prototype Preview

Open `interactive-prototype-preview.html` locally when a designer, reviewer, or developer needs to inspect the intended prototype flow without Figma access. The preview is deliberately static: it shows screen-state transitions, action-to-tool mappings, PASS/PASS_WITH_RISKS/BLOCK states, and responsive behavior, but it never executes workflow actions or presents itself as the application. Use it as a review aid before running the Figma Desktop rebuild plugin.

Claim boundary: this preview strengthens local reviewability of the prototype map. It does not satisfy native Figma source delivery, does not prove Figma prototype reactions, and does not replace `streamlit run app.py`.

## Visual QA

Run the screenshot verifier from the project root:

```powershell
python scripts/ui_visual_qa.py --port 8516 --timeout 90
```

The script starts `app.py` through Streamlit, captures desktop/tablet/mobile screenshots, checks required text anchors, runs a lightweight non-blank image check, and writes `visual_qa_manifest.json` under `data/runs/ui_visual_qa_<timestamp>/`.

Claim boundary: visual QA proves the page rendered for the captured breakpoints. It does not prove native `.fig` source creation, pixel-perfect Figma parity, model validity, SHAP validity, or scientific conclusions.

## Handoff Audit

Run the local handoff audit before reporting Figma progress:

```powershell
python scripts/figma_handoff_audit.py
```

The script writes `figma_handoff_audit.json` under `data/runs/figma_handoff_audit_<timestamp>/`. It checks required handoff assets, plugin reconstruction markers, latest visual QA manifest availability, and whether any local `.fig` or `.figjam` source artifact exists. A passing audit proves the repository handoff package is internally consistent; it still does not prove native Figma source completion unless a real `.fig/.figjam` artifact or verified Figma file URL is present.

Use `acceptance-matrix.json` before any completion claim. It currently marks native Figma source/prototype delivery as `missing_external_fulfillment` until a real `.fig/.figjam` artifact or verified Figma URL is produced, inspected, and registered.

## Native Artifact Registration

After the Figma Desktop plugin or a working Figma MCP produces native evidence, register it from the project root:

```powershell
python scripts/register_native_figma_artifact.py --fig D:\path\EvidencePlatform.fig --verified-by "designer-name" --confirm-all
```

For a verified hosted Figma file or prototype URL:

```powershell
python scripts/register_native_figma_artifact.py --url https://www.figma.com/design/FILEKEY/EvidencePlatform --verified-by "designer-name" --confirm-pages --confirm-interactions --confirm-motion --confirm-source-truth
```

The script writes `docs/figma_handoff/native-figma-receipt.json` and mirrors the receipt under `data/runs/native_figma_registration_<timestamp>/`. This receipt is a completion-gate input, not a substitute for inspection. Registration now requires explicit page, interaction, motion, and source-of-truth confirmations; otherwise the receipt is written as `blocked`. If the receipt is absent or inspection is incomplete, the audit must continue to report native Figma completion as unproven.

The inspection standard is defined in `native-figma-inspection-checklist.json`. It requires all eight generated pages, the key prototype edges, PASS_WITH_RISKS/BLOCK visibility, motion rules, and source-of-truth checks before a native `.fig/.figjam` artifact or verified Figma URL can satisfy R8.

## Handoff Bundle

Build a distributable ZIP package for the designer/developer who will run the Figma Desktop plugin:

```powershell
python scripts/build_figma_handoff_bundle.py
```

The script writes `figma_handoff_bundle_manifest.json` and a ZIP under `data/runs/figma_handoff_bundle_<timestamp>/`. The ZIP contains the Figma handoff assets, plugin rebuild kit, design-system documentation, visual/audit evidence manifests, and source reference files. Claim boundary: this ZIP is a handoff/rebuild package, not a native `.fig` file.

## Native Figma Limitation

The current environment cannot create a proprietary native `.fig` file directly. Use these assets as the import brief for Figma:

1. Import `high-fidelity-evidence-platform.svg` as a reference frame.
2. Create local styles from `design-tokens.json`.
3. Rebuild components from `component-library.json`.
4. Wire prototype transitions from `prototype-map.json`.
5. Add variants from `interaction-states.json`.
6. Create desktop/tablet/mobile frames from `responsive-spec.json` and `responsive-reference.svg`.
7. Keep all workflow buttons aligned with the real Streamlit actions in `app.py`.

Optional Figma-native reconstruction path:

1. Open Figma Desktop.
2. Import `figma_plugin/manifest.json` through `Plugins > Development > Import plugin from manifest...`.
3. Run `Black Soil Water Erosion Intelligent Prediction and Evidence-Based Evaluation Platform Rebuild Kit`.
4. Inspect the generated pages: `EvidencePlatform Tokens`, `EvidencePlatform Components`, `EvidencePlatform Design System Spec`, `EvidencePlatform Prototype`, `EvidencePlatform Interactive Flow`, `EvidencePlatform Motion System`, `EvidencePlatform Developer Handoff`, `EvidencePlatform Acceptance Evidence`, and `EvidencePlatform Native Inspection Checklist`.
5. Confirm the acceptance markers on the generated checklist pages: native paint/text/effect styles, Figma color variables when supported, component masters, gate variants, responsive frames, design-system spec markers, developer handoff markers, interactive flow chips, motion/microinteraction samples, risk visibility, source-of-truth boundaries, forbidden-claim boundaries, and final save/export requirement.
6. Save the generated Figma file manually as the native source artifact.
7. Register the saved artifact or verified hosted URL with `scripts/register_native_figma_artifact.py`, then rerun `python scripts/figma_handoff_audit.py`.

This plugin path creates editable Figma nodes when run in Figma, but the repository still does not contain a verified native `.fig` file until that external Figma save/export step is completed.

## Non-Negotiable Product Rules

- Do not create or ship a second HTML/React/Vue frontend.
- Do not add visual-only workflow buttons.
- Do not hide `BLOCK` or `PASS_WITH_RISKS` states.
- Do not imply full scientific validation from UI state alone.
