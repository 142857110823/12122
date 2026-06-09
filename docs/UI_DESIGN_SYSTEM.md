# UI Design System - Black Soil Water Erosion Intelligent Prediction and Evidence-Based Evaluation Platform

Date: 2026-06-02
Scope: `water_erosion_mvp/app.py` Streamlit single-base frontend only.

## 1. Design Goal

Build a commercial-grade scientific evidence platform that makes the P0-P3 workflow visually clear, operationally safe, and evidence-first:

- P0: data access, preprocessing, and gate status
- P1: model pool, unified metrics, ranking, and selected model
- P2: SHAP/proxy explanations and spatial interpretation artifacts
- P3: prediction, report, reproducibility notes, and evidence bundle

The UI must never become a second frontend or a decorative prototype detached from real computation.

## 2. Visual Direction

Name: Field-station evidence platform.

Intent:

- Black soil, survey grid, field-station instruments, and scientific evidence lineage.
- Dense but calm panels for real research state, not generic SaaS cards.
- Warm earth surface with deep green command areas to support long analytical sessions.
- Gate verdicts and evidence paths are first-class visual elements.

## 3. Design Tokens

Colors:

| Token | Value | Use |
|---|---:|---|
| `--color-primary` | `#1a6b5a` | Primary actions, active stages, evidence emphasis |
| `--color-primary-dark` | `#0f4d3f` | Deep evidence platform text and headers |
| `--color-secondary` | `#b8956a` | Soil/survey accents |
| `--color-accent` | `#e07b39` | Warnings, active notes, risk cues |
| `--color-bg` | `#f8f6f0` | Main research canvas |
| `--color-surface` | `#ffffff` | Cards and panels |
| `--color-success` | `#27ae60` | PASS / OK state |
| `--color-warning` | `#e07b39` | PASS_WITH_RISKS / caution state |
| `--color-danger` | `#c0392b` | BLOCK / error state |

Typography:

- UI text: `Microsoft YaHei UI`, `Microsoft YaHei`, `Noto Sans CJK SC`, `Segoe UI`, sans-serif.
- Technical paths and run IDs: `Cascadia Mono`, `JetBrains Mono`, `Consolas`, monospace.
- Header style: tight letter spacing, high contrast, short scientific labels.

Spacing and radius:

- Small card radius: `12px`
- Large evidence platform panel radius: `22-26px`
- Panel gap: `12-18px`
- Hero padding: desktop `26px 30px`, mobile `20px 18px`

Elevation:

- `--shadow-sm`: message and light controls
- `--shadow-md`: hover lift and buttons
- `--shadow-lg`: hero/evidence platform visual anchor

## 4. Component Library

### Command Hero

Purpose: communicates product identity and the single scientific workflow.

Rules:

- Must mention data, gate, model ranking, interpretation, spatial expression, and evidence export.
- Must not advertise unsupported capabilities as completed.
- Background grid is decorative but reinforces remote-sensing/survey context.

### Stage Rail

Purpose: shows P0-P3 state without replacing real gate reports.

States:

| State | Visual | Meaning |
|---|---|---|
| Default | white soil card | Stage exists but is not current |
| Active | green/amber gradient | Current workflow area |
| Completed | represented by Streamlit progress bar and messages | Tool evidence exists |
| Blocked | must be reported in tool message/gate card | Do not silently continue |

### Evidence Panel

Purpose: exposes run lineage.

Required fields:

- Run ID
- Gate verdict
- Source-data policy
- Output directory

Rules:

- `PASS_WITH_RISKS` remains visible as risk-bearing status.
- Evidence paths must come from real `tools.py` results or `run_context`.

### Option Cards

Purpose: stage-specific user actions.

Rules:

- Every option must map to `handle_action()` and a real tool call, state transition, or explicit non-compute action such as upload/reset/help.
- No fake Figma-only buttons.
- Button labels should be outcome-oriented and stage-specific.

### Design System Strip

Purpose: embedded developer handoff and prototype summary.

Cards:

- Design language
- Interaction prototype
- Developer handoff path

This strip is informational and does not pretend to run computation.

### Gate Workbench

Purpose: gives the user a compact P0-P3 status board before reading detailed logs.

Rules:

- It is derived from `session_state`, uploads, models, explanations, predictions, and run context.
- It is not a replacement for `tools.py` error-corrector gate JSON.
- `PASS_WITH_RISKS` and `BLOCK` must remain text-visible.
- Empty or pending states are acceptable and preferred over invented evidence.

### Result Workbench

Purpose: moves result consumption out of the chat stream into a product-grade review surface.

Tabs:

- `模型排行`: real `session_state.models` metrics only; summary cards and RMSE rank bars are derived from actual metric values.
- `解释图件`: real files from `_explanation_meta.explanation_files` and `_explanation_meta.spatial_files`; category chips and image gallery use existing paths only.
- `证据包`: existing report/bundle files and real `run_context.evidence_paths`; method/reproduce/gate/index entry cards show available only when files exist.
- `门禁索引`: existing gate JSON files from `run_context.gate_reports` or `data/runs/<run_id>/gates`; PASS/PASS_WITH_RISKS/BLOCK totals are parsed from JSON verdicts.

Rules:

- No model metrics, images, downloads, or gate JSON may be displayed unless the state/file exists.
- Empty states must explain which workflow stage produces the missing artifact.
- Download buttons render only for existing files.
- Rank bars must not be decorative; the width is computed from real RMSE values.
- Gate summary counts must not be decorative; they are computed from existing gate JSON verdicts.
- Gallery thumbnails must not be decorative; images render only from existing artifact files.
- Bundle entry cards must not imply export success; unavailable method/reproduce/gate/index files show `待导出`.

## 5. Interaction Prototype

Primary route:

```text
Data loaded
  -> P0 quality gate / one-click P0-P3
  -> feature table
  -> model training and ranking
  -> explanations and spatial maps
  -> prediction / report / bundle export
```

One-click route:

```text
run_one_click_pipeline(run_mode='quick', source_mode='rusle_raw', output_dpi=300)
  -> evidence paths
  -> gate verdict
  -> bundle zip
  -> workflow_stage='reported'
```

Risk route:

```text
Tool returns BLOCK
  -> show blocker in message/expander
  -> do not advance stage
  -> keep evidence path visible if produced
```

## 6. Responsive Rules

Desktop:

- Hero and command grid remain two-column.
- Stage rail uses four columns.
- Metric ribbon uses four columns.
- Sidebar width stays between 320 and 360 px.

Tablet under 900 px:

- Command grid becomes single-column.
- Stage rail and metric ribbon become two-column.
- Design-system strip becomes single-column.

Mobile under 560 px:

- Hero padding and heading size are reduced.
- Stage rail and metric ribbon become single-column.
- Progress steps can scroll horizontally.

## 7. Motion Rules

Allowed motion:

- Hero reveal on load.
- Panel lift on load.
- Stage/card hover lift.
- Button hover lift.

Forbidden motion:

- Constant ambient animation that distracts from map or metric reading.
- Motion that implies a computation succeeded before the tool returns.

## 8. Development Constraints

- Single frontend entry: `app.py`.
- No external CDN fonts or assets.
- No second HTML/Vue/React frontend.
- No decorative-only workflow buttons.
- No source-data writes.
- Keep evidence and gate status visible.

## 9. Current Implementation Map

| UI asset | File/function |
|---|---|
| Design tokens and responsive CSS | `app.py::CUSTOM_CSS` |
| Workflow state rail | `app.py::render_command_center()` |
| Embedded design handoff panel | `app.py::render_design_system_panel()` |
| P0-P3 gate status board | `app.py::render_gate_workbench()` |
| Product result tabs | `app.py::render_results_workbench()` |
| Sidebar status and design notes | `app.py::render_sidebar()` |
| Real workflow options | `app.py::get_options()` and `app.py::handle_action()` |

## 10. Figma-Style Handoff Assets

The project now includes a dedicated handoff package under `docs/figma_handoff/`:

| Asset | Purpose |
|---|---|
| `design-tokens.json` | Machine-readable color, typography, radius, shadow, motion, and breakpoint tokens |
| `component-library.json` | Component inventory with slots, states, rules, and implementation mapping |
| `prototype-map.json` | P0-P3 screen flow and real tool-binding map |
| `high-fidelity-evidence-platform.svg` | 1440x1080 high-fidelity reference frame for Figma import or visual QA |
| `responsive-spec.json` | Desktop/tablet/mobile frame behavior and layout rules |
| `interaction-states.json` | Figma variant matrix for buttons, gate cards, stage tiles, evidence rows, and downloads |
| `responsive-reference.svg` | Multi-device reference board for responsive reconstruction |
| `accessibility-qa-checklist.md` | Visual hierarchy, keyboard, readability, and scientific-integrity QA checklist |
| `README.md` | Reconstruction steps and non-negotiable product rules |

These assets are covered by `test_ui_design_assets.py` so that required design deliverables cannot silently disappear.

## 11. Native Figma Note

This environment can implement and document a Figma-grade UI system, but it cannot author or export a native `.fig` source file directly. The current deliverable is therefore the runnable Streamlit prototype plus this developer handoff specification. If a native Figma file is required later, this document can be used as the import brief for manual Figma reconstruction or automated design-token transfer.
