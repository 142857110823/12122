# Accessibility And QA Checklist

Scope: Streamlit single-base UI in `app.py` plus `docs/figma_handoff/` design assets.

## Visual Hierarchy

- Hero title is the strongest visual anchor and states the product purpose.
- P0-P3 stage rail appears before action cards.
- Gate board appears before design handoff material.
- Evidence and risk states use text plus color, never color alone.

## Keyboard And Interaction

- Primary workflow actions are Streamlit buttons and remain keyboard reachable.
- Download actions render only when files exist.
- Status/progress messages use Streamlit status and expander primitives.
- No hidden hover-only critical controls.

## Readability

- Chinese UI text uses local system-safe fonts.
- Run IDs and paths use monospace.
- Mobile layout keeps gate cards visible as one-column stack.
- `PASS_WITH_RISKS` and `BLOCK` are not abbreviated away.

## Scientific Integrity UX

- Stage active state is not treated as proof of scientific validity.
- `PASS_WITH_RISKS` must remain visible in gate cards and evidence rows.
- `BLOCK` must prevent next-stage progression.
- Proxy explanation outputs must not be labeled as real SHAP.
- Native `.fig` absence must remain explicit until resolved.

## QA Commands

```powershell
python -m py_compile app.py test_ui_design_assets.py
python -m unittest test_ui_design_assets.py
python -m unittest test_p0_p3_upgrade.py
python test_v03_quick.py
python test_v03_e2e.py
python -m streamlit run app.py --server.headless=true --server.port=8508
python scripts/ui_visual_qa.py --port 8516 --timeout 90
```

## Rendered Screenshot QA

- `scripts/ui_visual_qa.py` captures desktop, tablet, and mobile viewports.
- Required anchors: `黑土区水蚀智能预测与证据化评估平台`, `EVIDENCE PLATFORM`, `证据化评估工作台`.
- Required visible selectors: `.command-hero`, `.gate-board`, `.result-workbench`.
- The manifest is written to `data/runs/ui_visual_qa_<timestamp>/visual_qa_manifest.json`.
- The image check catches blank-like screenshots with color count and non-white ratio.
- The layout check records `layout_health`, including visible ratios for core evidence platform components and whether the Streamlit sidebar dominates the viewport.
- Passing screenshot QA does not prove native `.fig` output, model quality, real SHAP, GeoShapley, or scientific validity.

Latest accepted evidence: `data/runs/ui_visual_qa_20260602_172626/visual_qa_manifest.json` reported `status=ok` with non-blank desktop/tablet/mobile captures, anchors found, `first_paint_visible=true`, and `sidebar_dominates_viewport=false` for all three viewports after Chinese copy restoration.

Historical evidence: `data/runs/ui_visual_qa_20260602_170446/visual_qa_manifest.json` reported `status=ok` after layout-health checks but before Chinese copy restoration. `data/runs/ui_visual_qa_20260602_155624/visual_qa_manifest.json` predates layout-health checks and should be kept only as a rendering-history reference.
