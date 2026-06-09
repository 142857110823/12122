# Figma Plugin Rebuild Kit

This folder contains a native Figma plugin script that reconstructs the Streamlit evidence platform as editable Figma frames, component masters, design-system spec pages, responsive prototype frames, an interactive flow page, a motion-system page, a developer-handoff page, an acceptance-evidence page, and a native-inspection checklist page.

## Files

- `manifest.json`: Figma plugin manifest.
- `code.js`: plugin entrypoint that creates native paint/text/effect styles, optional Figma Variables, pages, token swatches, component masters, design-system spec pages, developer handoff pages, gate verdict variants, desktop/tablet/mobile prototype frames, clickable prototype-flow chips when supported by Figma, motion/microinteraction samples, native-handoff acceptance checks, and the `EvidencePlatform Native Inspection Checklist` page.

## How To Use

1. Open Figma Desktop.
2. Go to `Plugins > Development > Import plugin from manifest...`.
3. Select `docs/figma_handoff/figma_plugin/manifest.json`.
4. Run `Black Soil Water Erosion Intelligent Prediction and Evidence-Based Evaluation Platform Rebuild Kit`.
5. Inspect the generated pages:
   - `EvidencePlatform Tokens`
   - `EvidencePlatform Components`
   - `EvidencePlatform Design System Spec`
   - `EvidencePlatform Prototype`
   - `EvidencePlatform Interactive Flow`
   - `EvidencePlatform Motion System`
   - `EvidencePlatform Developer Handoff`
   - `EvidencePlatform Acceptance Evidence`
   - `EvidencePlatform Native Inspection Checklist`
6. Confirm these acceptance markers before saving the native source:
   - Component masters named `Master / CommandHero`, `Master / GateWorkbench`, `Master / ResultWorkbench`, and `Master / OptionAction`.
   - Gate variants named `GateCard / PASS`, `GateCard / PASS_WITH_RISKS`, and `GateCard / BLOCK`; when Figma supports `combineAsVariants`, they are combined into `Component Set / GateCard Verdicts`.
   - OptionAction variants named `OptionAction / default`, `OptionAction / hover`, `OptionAction / running`, `OptionAction / disabled`, and `OptionAction / blocked`; when supported, they are combined into `Component Set / OptionAction States`.
   - Responsive frames named `Desktop Evidence Platform`, `Tablet Evidence Platform`, and `Mobile Evidence Platform`.
   - Interactive flow markers named `Prototype Edge / One-click P0-P3`, `Prototype Edge / Export evidence bundle`, and `BLOCK edge rule`.
   - Motion markers named `Motion Spec / PASS_WITH_RISKS Pulse`, `Motion Spec / BLOCK Shake`, and `Motion Rule / no fake progress`.
   - Design spec markers named `EvidencePlatform Design System Spec`, `Type Scale / Display 44`, `Spacing Scale / 8pt Grid`, `Color Role / PASS_WITH_RISKS Warning`, and `Layout Rule / Responsive Shell`.
   - Developer handoff markers named `EvidencePlatform Developer Handoff`, `Source of Truth / app.py and tools.py`, `Figma Save/Export Requirement`, and `Registration Path / native-figma-receipt`.
   - Native inspection markers named `EvidencePlatform Native Inspection Checklist`, `evidence_platform.native_figma_inspection_checklist.v1`, `Required Pages`, `Prototype Checks`, `Motion Checks`, `Source-of-Truth Checks`, and `Forbidden Claims Until Registered`.
   - Native style markers named `Paint Style / EvidencePlatform/Primary`, `Paint Style / EvidencePlatform/Warning`, `Paint Style / EvidencePlatform/Danger`, `Text Style / EvidencePlatform/Display 44`, `Text Style / EvidencePlatform/Body 14`, and `Effect Style / EvidencePlatform/Panel Lift`.
   - Native variable markers named `Variable Collection / EvidencePlatform Tokens`, `Variable / color/primary`, `Variable / color/warning`, `Variable / color/danger`, `Variable / color/surface`, and `Variable / color/background`.
   - The acceptance page explicitly states that saving/exporting the Figma file is still required for the final native source artifact.

## Claim Boundary

This plugin can create editable Figma nodes when run inside Figma. The repository still does not contain a proprietary native `.fig` file, and this script is not a substitute for scientific validation, real SHAP validation, GeoShapley validation, or manual visual inspection of the generated Figma file.

## Source Alignment

The generated frames mirror the single Streamlit source of truth in `app.py` and the handoff assets in `docs/figma_handoff/`. Do not use this plugin to create a second product frontend or fake workflow buttons.
