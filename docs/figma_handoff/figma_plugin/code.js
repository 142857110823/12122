// Black Soil Water Erosion Intelligent Prediction and Evidence-Based Evaluation Platform Rebuild Kit
// Run inside Figma as a development plugin. It creates editable frames that
// mirror the Streamlit single-base UI and its Figma handoff assets.

const TOKENS = {
  color: {
    primary: '#1a6b5a',
    primaryLight: '#2d8f7a',
    primaryDark: '#0f4d3f',
    secondary: '#b8956a',
    accent: '#e07b39',
    background: '#f8f6f0',
    surface: '#ffffff',
    text: '#2d2d2d',
    textMuted: '#6b6b6b',
    border: '#e0ded8',
    success: '#27ae60',
    warning: '#e07b39',
    danger: '#c0392b'
  },
  radius: {
    small: 8,
    medium: 12,
    large: 22,
    hero: 26,
    pill: 999
  },
  frames: [
    { name: 'Desktop Evidence Platform', width: 1440, height: 1080, columns: 4 },
    { name: 'Tablet Evidence Platform', width: 834, height: 1194, columns: 2 },
    { name: 'Mobile Evidence Platform', width: 390, height: 844, columns: 1 }
  ]
};

const COMPONENTS = [
  ['CommandHero', 'Brand anchor and P0-P3 workflow promise.'],
  ['StageTile', 'Stage tile for P0, P1, P2, and P3. Active is not a gate PASS.'],
  ['MetricChip', 'Compact run/model/path summary.'],
  ['EvidenceItem', 'Run lineage, gate verdict, and evidence path display.'],
  ['GateWorkbench', 'P0-P3 status board derived from real state and gate files.'],
  ['ResultWorkbench', 'Model ranking, explanation gallery, bundle index, and gate JSON tabs.'],
  ['OptionAction', 'A real Streamlit action bound to app.py handle_action and tools.py.'],
  ['DesignSystemStrip', 'Embedded design handoff and implementation notes.']
];

const TOKEN_AUDIT_MARKERS = ['Primary', 'Secondary', 'Accent', 'Success', 'Warning', 'Danger'];

const FIGMA_STYLE_MARKERS = [
  'Paint Style / EvidencePlatform/Primary',
  'Paint Style / EvidencePlatform/Warning',
  'Paint Style / EvidencePlatform/Danger',
  'Text Style / EvidencePlatform/Display 44',
  'Text Style / EvidencePlatform/Body 14',
  'Effect Style / EvidencePlatform/Panel Lift'
];

const FIGMA_VARIABLE_MARKERS = [
  'Variable Collection / EvidencePlatform Tokens',
  'Variable / color/primary',
  'Variable / color/warning',
  'Variable / color/danger',
  'Variable / color/surface',
  'Variable / color/background'
];

const PROTOTYPE_STEPS = [
  ['S0_IDLE', 'Welcome / No Data', 'Upload files or use rusle_raw quick source.'],
  ['S1_DATA_LOADED', 'P0 Data Loaded', 'Run one-click pipeline or assess quality.'],
  ['S2_QUALITY', 'P0 Quality Gate', 'Build feature table only after data gate.'],
  ['S3_FEATURES', 'P1 Feature Matrix Ready', 'Train candidate model pool.'],
  ['S4_MODELS', 'P1 Model Ranking', 'Generate explanations or predictions.'],
  ['S5_EXPLAINED', 'P2 Explanation And Spatial Artifacts', 'Export artifacts with proxy/SHAP boundary.'],
  ['S6_PREDICTED', 'P3 Prediction / Spatial View', 'Generate report and bundle.'],
  ['S7_BUNDLE', 'P3 Report And Evidence Bundle', 'Download report, bundle, gate summary.']
];

const INTERACTIVE_FLOW_EDGES = [
  ['S0_IDLE', 'S1_DATA_LOADED', 'Upload files'],
  ['S1_DATA_LOADED', 'S2_QUALITY', 'Assess quality'],
  ['S1_DATA_LOADED', 'S7_BUNDLE', 'One-click P0-P3'],
  ['S2_QUALITY', 'S3_FEATURES', 'Build feature table'],
  ['S3_FEATURES', 'S4_MODELS', 'Train candidates'],
  ['S4_MODELS', 'S5_EXPLAINED', 'Generate explanations'],
  ['S4_MODELS', 'S6_PREDICTED', 'Predict scenario'],
  ['S5_EXPLAINED', 'S7_BUNDLE', 'Export evidence bundle'],
  ['S6_PREDICTED', 'S7_BUNDLE', 'Generate report'],
  ['S7_BUNDLE', 'S0_IDLE', 'Restart']
];

const MOTION_SPECS = [
  ['Motion Spec / Hero Reveal', '520ms ease-out', 'Initial evidence platform arrival; reveal context without implying computation.'],
  ['Motion Spec / Panel Lift', '250ms cubic-bezier(0.4, 0, 0.2, 1)', 'Hover elevation for cards and action affordance.'],
  ['Motion Spec / Button Pressed', '120ms ease-out', 'Pressed state reduces elevation and returns immediately.'],
  ['Motion Spec / Focus Ring', 'instant + persistent', 'Keyboard focus ring must remain visible on workflow actions.'],
  ['Motion Spec / Loading Sweep', '900ms linear loop', 'Only during real tool execution or Streamlit st.status running state.'],
  ['Motion Spec / PASS_WITH_RISKS Pulse', '1400ms subtle pulse', 'Risk pulse keeps caveats visible; never implies success without evidence.'],
  ['Motion Spec / BLOCK Shake', '180ms x-axis shake', 'Used only when a gate or tool blocks downstream flow.']
];

const ACCEPTANCE_MARKERS = {
  componentMasters: [
    'Master / CommandHero',
    'Master / GateWorkbench',
    'Master / ResultWorkbench',
    'Master / OptionAction'
  ],
  gateVariants: [
    'GateCard / PASS',
    'GateCard / PASS_WITH_RISKS',
    'GateCard / BLOCK',
    'Component Set / GateCard Verdicts'
  ],
  actionVariants: [
    'OptionAction / default',
    'OptionAction / hover',
    'OptionAction / running',
    'OptionAction / disabled',
    'OptionAction / blocked',
    'Component Set / OptionAction States'
  ],
  responsiveFrames: [
    'Desktop Evidence Platform',
    'Tablet Evidence Platform',
    'Mobile Evidence Platform'
  ],
  interactiveFlow: [
    'EvidencePlatform Interactive Flow',
    'Prototype Edge / One-click P0-P3',
    'Prototype Edge / Export evidence bundle',
    'BLOCK edge rule'
  ],
  motionSystem: [
    'EvidencePlatform Motion System',
    'Motion Spec / PASS_WITH_RISKS Pulse',
    'Motion Spec / BLOCK Shake',
    'Motion Rule / no fake progress'
  ],
  designSpec: [
    'EvidencePlatform Design System Spec',
    'Type Scale / Display 44',
    'Spacing Scale / 8pt Grid',
    'Color Role / PASS_WITH_RISKS Warning',
    'Layout Rule / Responsive Shell'
  ],
  developerHandoff: [
    'EvidencePlatform Developer Handoff',
    'Source of Truth / app.py and tools.py',
    'Figma Save/Export Requirement',
    'Registration Path / native-figma-receipt'
  ]
};

const NATIVE_INSPECTION_CHECKLIST = {
  schema: 'evidence_platform.native_figma_inspection_checklist.v1',
  requiredPages: [
    'EvidencePlatform Tokens',
    'EvidencePlatform Components',
    'EvidencePlatform Design System Spec',
    'EvidencePlatform Prototype',
    'EvidencePlatform Interactive Flow',
    'EvidencePlatform Motion System',
    'EvidencePlatform Developer Handoff',
    'EvidencePlatform Acceptance Evidence',
    'EvidencePlatform Native Inspection Checklist'
  ],
  prototypeChecks: [
    'One-click P0-P3 flow edge exists',
    'Export evidence bundle edge exists',
    'BLOCK state prevents next-stage progression',
    'PASS_WITH_RISKS remains visible',
    'No action chip represents a workflow that is absent from app.py/tools.py'
  ],
  motionChecks: [
    'PASS_WITH_RISKS pulse is represented',
    'BLOCK shake/error emphasis is represented',
    'Loading animation is only described for real tool execution',
    'No fake progress animation is introduced'
  ],
  sourceTruthChecks: [
    'Workflow actions map back to app.py/tools.py',
    'No second frontend is introduced',
    'Figma artifact does not claim scientific/model validity',
    'Design handoff references docs/figma_handoff and docs/UI_DESIGN_SYSTEM.md'
  ],
  forbiddenClaims: [
    'Native Figma source is complete',
    'Figma prototype interactions were inspected',
    'Pixel-perfect Figma parity is proven',
    'UI evidence proves model or scientific validity'
  ]
};

function hexToRgb(hex) {
  const value = hex.replace('#', '');
  const number = parseInt(value, 16);
  return {
    r: ((number >> 16) & 255) / 255,
    g: ((number >> 8) & 255) / 255,
    b: (number & 255) / 255
  };
}

function solid(hex, opacity = 1) {
  return [{ type: 'SOLID', color: hexToRgb(hex), opacity }];
}

function findLocalStyle(kind, name) {
  const getters = {
    paint: figma.getLocalPaintStyles,
    text: figma.getLocalTextStyles,
    effect: figma.getLocalEffectStyles
  };
  try {
    const getStyles = getters[kind];
    if (!getStyles) {
      return null;
    }
    return getStyles().find(style => style.name === name) || null;
  } catch (error) {
    return null;
  }
}

function upsertPaintStyle(name, hex, description) {
  try {
    const style = findLocalStyle('paint', name) || figma.createPaintStyle();
    style.name = name;
    style.paints = solid(hex);
    style.description = description;
    return true;
  } catch (error) {
    figma.root.setSharedPluginData('evidence_platform', `paint_style_error_${name}`, error.message);
    return false;
  }
}

async function upsertTextStyle(name, size, weight, description) {
  try {
    await figma.loadFontAsync({ family: 'Inter', style: weight });
    const style = findLocalStyle('text', name) || figma.createTextStyle();
    style.name = name;
    style.fontName = { family: 'Inter', style: weight };
    style.fontSize = size;
    style.lineHeight = { unit: 'AUTO' };
    style.description = description;
    return true;
  } catch (error) {
    figma.root.setSharedPluginData('evidence_platform', `text_style_error_${name}`, error.message);
    return false;
  }
}

function upsertEffectStyle(name, effects, description) {
  try {
    const style = findLocalStyle('effect', name) || figma.createEffectStyle();
    style.name = name;
    style.effects = effects;
    style.description = description;
    return true;
  } catch (error) {
    figma.root.setSharedPluginData('evidence_platform', `effect_style_error_${name}`, error.message);
    return false;
  }
}

async function buildNativeStyles() {
  const paintSpecs = [
    ['EvidencePlatform/Primary', TOKENS.color.primary, 'Primary green for command surfaces and active scientific workflow affordances.'],
    ['EvidencePlatform/Secondary', TOKENS.color.secondary, 'Field-soil accent for brand warmth and subdued labels.'],
    ['EvidencePlatform/Accent', TOKENS.color.accent, 'High-energy accent used sparingly for emphasis.'],
    ['EvidencePlatform/Success', TOKENS.color.success, 'PASS and positive evidence state.'],
    ['EvidencePlatform/Warning', TOKENS.color.warning, 'PASS_WITH_RISKS warning state; never hide risk copy.'],
    ['EvidencePlatform/Danger', TOKENS.color.danger, 'BLOCK and error state; blocks downstream progression.'],
    ['EvidencePlatform/Background', TOKENS.color.background, 'Paper field-station background.'],
    ['EvidencePlatform/Surface', TOKENS.color.surface, 'Card and workbench surface.'],
    ['EvidencePlatform/Text', TOKENS.color.text, 'Primary text.'],
    ['EvidencePlatform/Text Muted', TOKENS.color.textMuted, 'Secondary text and evidence metadata.']
  ];
  let paintCreated = 0;
  for (const [name, hex, description] of paintSpecs) {
    if (upsertPaintStyle(name, hex, description)) {
      paintCreated += 1;
    }
  }

  const textSpecs = [
    ['EvidencePlatform/Display 44', 44, 'Bold', 'Hero title and evidence platform identity.'],
    ['EvidencePlatform/Section 34', 34, 'Bold', 'Section and Figma page headings.'],
    ['EvidencePlatform/Panel Title 22', 22, 'Bold', 'Workbench and card titles.'],
    ['EvidencePlatform/Body 14', 14, 'Regular', 'Primary body and evidence copy.'],
    ['EvidencePlatform/Caption 12', 12, 'Regular', 'Metadata, chips, and compact labels.'],
    ['EvidencePlatform/Label 12 Bold', 12, 'Bold', 'Stage codes, gate labels, and action chips.']
  ];
  let textCreated = 0;
  for (const [name, size, weight, description] of textSpecs) {
    if (await upsertTextStyle(name, size, weight, description)) {
      textCreated += 1;
    }
  }

  const shadowColor = { r: 0.0588, g: 0.1137, b: 0.0941, a: 0.16 };
  const effects = [{
    type: 'DROP_SHADOW',
    visible: true,
    color: shadowColor,
    offset: { x: 0, y: 18 },
    radius: 40,
    spread: -18,
    blendMode: 'NORMAL'
  }];
  const effectCreated = upsertEffectStyle('EvidencePlatform/Panel Lift', effects, 'Elevated panel hover and focus effect; not a progress indicator.') ? 1 : 0;

  return { paintCreated, textCreated, effectCreated };
}

function findVariableCollection(name) {
  try {
    if (!figma.variables || !figma.variables.getLocalVariableCollections) {
      return null;
    }
    return figma.variables.getLocalVariableCollections().find(collection => collection.name === name) || null;
  } catch (error) {
    return null;
  }
}

function findVariableByName(name, collectionId) {
  try {
    if (!figma.variables || !figma.variables.getLocalVariables) {
      return null;
    }
    return figma.variables.getLocalVariables('COLOR').find(variable => (
      variable.name === name && variable.variableCollectionId === collectionId
    )) || null;
  } catch (error) {
    return null;
  }
}

function upsertColorVariable(collection, modeId, name, hex, description) {
  try {
    if (!figma.variables || !figma.variables.createVariable) {
      return false;
    }
    const variable = findVariableByName(name, collection.id) || figma.variables.createVariable(name, collection, 'COLOR');
    const color = hexToRgb(hex);
    variable.setValueForMode(modeId, { r: color.r, g: color.g, b: color.b, a: 1 });
    variable.description = description;
    return true;
  } catch (error) {
    figma.root.setSharedPluginData('evidence_platform', `variable_error_${name}`, error.message);
    return false;
  }
}

function buildNativeVariables() {
  try {
    if (!figma.variables || !figma.variables.createVariableCollection) {
      figma.root.setSharedPluginData('evidence_platform', 'variable_collection_status', 'unsupported');
      return { variableCollectionCreated: false, colorVariablesCreated: 0, supported: false };
    }
    const collection = findVariableCollection('EvidencePlatform Tokens') || figma.variables.createVariableCollection('EvidencePlatform Tokens');
    const modeId = collection.modes && collection.modes[0] ? collection.modes[0].modeId : collection.defaultModeId;
    const variableSpecs = [
      ['color/primary', TOKENS.color.primary, 'Primary workflow and command color.'],
      ['color/secondary', TOKENS.color.secondary, 'Soil-gold brand accent.'],
      ['color/accent', TOKENS.color.accent, 'Emphasis accent.'],
      ['color/success', TOKENS.color.success, 'PASS state.'],
      ['color/warning', TOKENS.color.warning, 'PASS_WITH_RISKS state.'],
      ['color/danger', TOKENS.color.danger, 'BLOCK/error state.'],
      ['color/surface', TOKENS.color.surface, 'Card surface.'],
      ['color/background', TOKENS.color.background, 'Paper background.'],
      ['color/text', TOKENS.color.text, 'Primary text.'],
      ['color/text-muted', TOKENS.color.textMuted, 'Secondary text.']
    ];
    let colorVariablesCreated = 0;
    for (const [name, hex, description] of variableSpecs) {
      if (upsertColorVariable(collection, modeId, name, hex, description)) {
        colorVariablesCreated += 1;
      }
    }
    return { variableCollectionCreated: true, colorVariablesCreated, supported: true };
  } catch (error) {
    figma.root.setSharedPluginData('evidence_platform', 'variable_collection_error', error.message);
    return { variableCollectionCreated: false, colorVariablesCreated: 0, supported: false };
  }
}

function ensurePage(name) {
  const existing = figma.root.children.find(page => page.name === name);
  if (existing) {
    figma.currentPage = existing;
    existing.children.slice().forEach(child => child.remove());
    return existing;
  }
  const page = figma.createPage();
  page.name = name;
  figma.currentPage = page;
  return page;
}

async function setText(node, text, size = 14, color = TOKENS.color.text, weight = 'REGULAR') {
  await figma.loadFontAsync({ family: 'Inter', style: weight });
  node.characters = text;
  node.fontName = { family: 'Inter', style: weight };
  node.fontSize = size;
  node.fills = solid(color);
  node.lineHeight = { unit: 'AUTO' };
}

function makeFrame(name, width, height, fill = TOKENS.color.surface) {
  const frame = figma.createFrame();
  frame.name = name;
  frame.resize(width, height);
  frame.fills = solid(fill);
  frame.cornerRadius = TOKENS.radius.large;
  frame.clipsContent = false;
  return frame;
}

function makeComponent(name, width, height, fill = TOKENS.color.surface) {
  const component = figma.createComponent();
  component.name = name;
  component.resize(width, height);
  component.fills = solid(fill);
  component.cornerRadius = TOKENS.radius.large;
  component.clipsContent = false;
  return component;
}

function autoLayout(frame, direction = 'VERTICAL', gap = 16, padding = 24) {
  frame.layoutMode = direction;
  frame.itemSpacing = gap;
  frame.paddingTop = padding;
  frame.paddingBottom = padding;
  frame.paddingLeft = padding;
  frame.paddingRight = padding;
  frame.primaryAxisSizingMode = 'AUTO';
  frame.counterAxisSizingMode = 'FIXED';
}

function addStroke(node, color = TOKENS.color.border) {
  node.strokes = solid(color);
  node.strokeWeight = 1;
}

async function label(parent, text, size = 14, color = TOKENS.color.text, weight = 'REGULAR') {
  const node = figma.createText();
  await setText(node, text, size, color, weight);
  parent.appendChild(node);
  return node;
}

async function componentMaster(name, purpose) {
  const master = makeComponent(`Master / ${name}`, 360, 180, TOKENS.color.surface);
  autoLayout(master, 'VERTICAL', 10, 18);
  addStroke(master);
  await label(master, name, 20, TOKENS.color.primaryDark, 'BOLD');
  await label(master, purpose, 13, TOKENS.color.textMuted);
  const badge = makeFrame(`${name} state badge`, 170, 34, TOKENS.color.background);
  badge.cornerRadius = TOKENS.radius.pill;
  badge.layoutMode = 'HORIZONTAL';
  badge.primaryAxisAlignItems = 'CENTER';
  badge.counterAxisAlignItems = 'CENTER';
  master.appendChild(badge);
  await label(badge, name === 'GateWorkbench' ? 'PASS_WITH_RISKS' : 'REAL DATA ONLY', 11, name === 'GateWorkbench' ? TOKENS.color.warning : TOKENS.color.primary, 'BOLD');
  return master;
}

async function buildTokensPage() {
  ensurePage('EvidencePlatform Tokens');
  const board = makeFrame('Design Tokens / Field-station evidence platform', 1180, 760, TOKENS.color.background);
  autoLayout(board, 'VERTICAL', 24, 36);
  board.x = 80;
  board.y = 80;
  await label(board, 'Black Soil Water Erosion Intelligent Prediction and Evidence-Based Evaluation Platform', 34, TOKENS.color.primaryDark, 'BOLD');
  await label(board, 'Token source: docs/figma_handoff/design-tokens.json. Generated nodes are editable reconstruction assets, not scientific proof.', 15, TOKENS.color.textMuted);

  const swatchGrid = makeFrame('Color tokens', 1090, 420, TOKENS.color.surface);
  autoLayout(swatchGrid, 'HORIZONTAL', 14, 20);
  swatchGrid.layoutWrap = 'WRAP';
  addStroke(swatchGrid);
  board.appendChild(swatchGrid);

  for (const [name, hex] of Object.entries(TOKENS.color)) {
    const card = makeFrame(`Token / ${name}`, 156, 150, TOKENS.color.surface);
    autoLayout(card, 'VERTICAL', 8, 12);
    addStroke(card);
    const swatch = makeFrame(`${name} ${hex}`, 132, 56, hex);
    swatch.cornerRadius = TOKENS.radius.medium;
    card.appendChild(swatch);
    await label(card, name, 13, TOKENS.color.text, 'BOLD');
    await label(card, hex, 12, TOKENS.color.textMuted);
    swatchGrid.appendChild(card);
  }

  const rules = makeFrame('Non-negotiable UX rules', 1090, 180, TOKENS.color.surface);
  autoLayout(rules, 'VERTICAL', 8, 18);
  addStroke(rules);
  board.appendChild(rules);
  await label(rules, 'Rules', 18, TOKENS.color.primaryDark, 'BOLD');
  await label(rules, 'Single Streamlit base only: app.py remains the runnable UI source of truth.', 13, TOKENS.color.text);
  await label(rules, 'PASS_WITH_RISKS and BLOCK must stay visible on every breakpoint.', 13, TOKENS.color.warning, 'BOLD');
  await label(rules, 'No visual-only buttons. Primary actions must map to real tools.py behavior.', 13, TOKENS.color.danger, 'BOLD');

  const auditMarkers = makeFrame('Token audit markers / Primary Secondary Accent Success Warning Danger', 1090, 92, TOKENS.color.surface);
  autoLayout(auditMarkers, 'HORIZONTAL', 10, 14);
  auditMarkers.layoutWrap = 'WRAP';
  addStroke(auditMarkers, TOKENS.color.primaryLight);
  board.appendChild(auditMarkers);
  for (const marker of TOKEN_AUDIT_MARKERS) {
    const pill = makeFrame(`Token Marker / ${marker}`, 150, 34, TOKENS.color.background);
    pill.cornerRadius = TOKENS.radius.pill;
    pill.layoutMode = 'HORIZONTAL';
    pill.primaryAxisAlignItems = 'CENTER';
    pill.counterAxisAlignItems = 'CENTER';
    auditMarkers.appendChild(pill);
    await label(pill, marker, 11, TOKENS.color.primaryDark, 'BOLD');
  }

  const styleMarkers = makeFrame('Native Figma style markers', 1090, 130, TOKENS.color.surface);
  autoLayout(styleMarkers, 'VERTICAL', 6, 14);
  addStroke(styleMarkers, TOKENS.color.primaryLight);
  board.appendChild(styleMarkers);
  await label(styleMarkers, 'Native Figma Styles', 16, TOKENS.color.primaryDark, 'BOLD');
  await label(styleMarkers, FIGMA_STYLE_MARKERS.join(' / '), 11, TOKENS.color.textMuted);

  const variableMarkers = makeFrame('Native Figma variable markers', 1090, 112, TOKENS.color.surface);
  autoLayout(variableMarkers, 'VERTICAL', 6, 14);
  addStroke(variableMarkers, TOKENS.color.primaryLight);
  board.appendChild(variableMarkers);
  await label(variableMarkers, 'Native Figma Variables', 16, TOKENS.color.primaryDark, 'BOLD');
  await label(variableMarkers, FIGMA_VARIABLE_MARKERS.join(' / '), 11, TOKENS.color.textMuted);
}

async function componentCard(name, purpose, x, y) {
  const card = makeFrame(`Component / ${name}`, 360, 170, TOKENS.color.surface);
  card.x = x;
  card.y = y;
  autoLayout(card, 'VERTICAL', 10, 18);
  addStroke(card);
  await label(card, name, 20, TOKENS.color.primaryDark, 'BOLD');
  await label(card, purpose, 13, TOKENS.color.textMuted);
  const badge = makeFrame(`${name} state badge`, 150, 34, TOKENS.color.background);
  badge.cornerRadius = TOKENS.radius.pill;
  badge.layoutMode = 'HORIZONTAL';
  badge.primaryAxisAlignItems = 'CENTER';
  badge.counterAxisAlignItems = 'CENTER';
  card.appendChild(badge);
  await label(badge, name === 'GateWorkbench' ? 'PASS_WITH_RISKS' : 'REAL DATA ONLY', 11, name === 'GateWorkbench' ? TOKENS.color.warning : TOKENS.color.primary, 'BOLD');
  return card;
}

function combineGateVariants(variants, parent) {
  try {
    if (!figma.combineAsVariants || variants.length < 2) {
      figma.root.setSharedPluginData('evidence_platform', 'gate_variant_set_status', 'unsupported');
      return null;
    }
    const set = figma.combineAsVariants(variants, parent);
    set.name = 'Component Set / GateCard Verdicts';
    set.description = 'GateCard component set with PASS, PASS_WITH_RISKS, BLOCK, and PENDING variants. BLOCK means downstream progression is forbidden.';
    set.setSharedPluginData('evidence_platform', 'variant_property', 'verdict=PASS|PASS_WITH_RISKS|BLOCK|PENDING');
    return set;
  } catch (error) {
    figma.root.setSharedPluginData('evidence_platform', 'gate_variant_set_error', error.message);
    return null;
  }
}

function combineActionVariants(variants, parent) {
  try {
    if (!figma.combineAsVariants || variants.length < 2) {
      figma.root.setSharedPluginData('evidence_platform', 'option_action_variant_set_status', 'unsupported');
      return null;
    }
    const set = figma.combineAsVariants(variants, parent);
    set.name = 'Component Set / OptionAction States';
    set.description = 'OptionAction component set with default, hover, running, disabled, and blocked states. Actions must map to real app.py/tools.py behavior.';
    set.setSharedPluginData('evidence_platform', 'variant_property', 'state=default|hover|running|disabled|blocked');
    return set;
  } catch (error) {
    figma.root.setSharedPluginData('evidence_platform', 'option_action_variant_set_error', error.message);
    return null;
  }
}

async function optionActionVariant(name, color, note, invert = false) {
  const variant = makeComponent(`OptionAction / ${name}`, 260, 92, invert ? color : TOKENS.color.surface);
  autoLayout(variant, 'VERTICAL', 6, 14);
  addStroke(variant, color);
  await label(variant, name.toUpperCase(), 13, invert ? TOKENS.color.surface : color, 'BOLD');
  await label(variant, note, 11, invert ? '#eef7f2' : TOKENS.color.textMuted);
  return variant;
}

async function buildComponentsPage() {
  ensurePage('EvidencePlatform Components');
  const board = makeFrame('Black Soil Water Erosion Intelligent Prediction and Evidence-Based Evaluation Platform Component Library', 1320, 1120, TOKENS.color.background);
  board.x = 80;
  board.y = 80;
  autoLayout(board, 'VERTICAL', 20, 36);
  await label(board, 'Component Library', 34, TOKENS.color.primaryDark, 'BOLD');
  await label(board, 'Editable component masters aligned to docs/figma_handoff/component-library.json and app.py. Instances are references only; runtime truth remains Streamlit.', 15, TOKENS.color.textMuted);

  const grid = makeFrame('Component master grid', 1220, 720, TOKENS.color.background);
  grid.layoutMode = 'HORIZONTAL';
  grid.layoutWrap = 'WRAP';
  grid.itemSpacing = 18;
  grid.counterAxisSpacing = 18;
  grid.paddingTop = 8;
  grid.paddingLeft = 8;
  grid.paddingRight = 8;
  grid.paddingBottom = 8;
  grid.fills = [];
  board.appendChild(grid);

  for (const [name, purpose] of COMPONENTS) {
    const master = await componentMaster(name, purpose);
    grid.appendChild(master);
  }

  const variantBoard = makeFrame('Gate verdict variant samples', 1220, 220, TOKENS.color.surface);
  autoLayout(variantBoard, 'HORIZONTAL', 14, 18);
  addStroke(variantBoard);
  board.appendChild(variantBoard);
  const gateVariants = [];
  for (const [verdict, color] of [
    ['PASS', TOKENS.color.success],
    ['PASS_WITH_RISKS', TOKENS.color.warning],
    ['BLOCK', TOKENS.color.danger],
    ['PENDING', TOKENS.color.textMuted]
  ]) {
    const variant = makeComponent(`GateCard / ${verdict}`, 270, 140, TOKENS.color.background);
    autoLayout(variant, 'VERTICAL', 8, 16);
    addStroke(variant, color);
    await label(variant, verdict, 16, color, 'BOLD');
    await label(variant, verdict === 'BLOCK' ? 'Stops downstream stage execution.' : 'Visible state, not a scientific conclusion.', 12, TOKENS.color.textMuted);
    variantBoard.appendChild(variant);
    gateVariants.push(variant);
  }
  const gateVariantSet = combineGateVariants(gateVariants, variantBoard);
  if (gateVariantSet) {
    await label(variantBoard, 'Component Set / GateCard Verdicts', 12, TOKENS.color.primaryDark, 'BOLD');
  }

  const actionBoard = makeFrame('OptionAction state variant samples', 1220, 220, TOKENS.color.surface);
  autoLayout(actionBoard, 'HORIZONTAL', 14, 18);
  addStroke(actionBoard);
  board.appendChild(actionBoard);
  const actionVariants = [];
  for (const [name, color, note, invert] of [
    ['default', TOKENS.color.primary, 'Real tool action available.', false],
    ['hover', TOKENS.color.primaryDark, 'Affordance only; no fake progress.', true],
    ['running', TOKENS.color.warning, 'Only while tools.py is executing.', false],
    ['disabled', TOKENS.color.textMuted, 'Unavailable until evidence exists.', false],
    ['blocked', TOKENS.color.danger, 'Gate BLOCK prevents downstream flow.', false]
  ]) {
    const variant = await optionActionVariant(name, color, note, invert);
    actionBoard.appendChild(variant);
    actionVariants.push(variant);
  }
  const actionVariantSet = combineActionVariants(actionVariants, actionBoard);
  if (actionVariantSet) {
    await label(actionBoard, 'Component Set / OptionAction States', 12, TOKENS.color.primaryDark, 'BOLD');
  }
}

async function stageTile(parent, code, title, status, fill) {
  const tile = makeFrame(`Stage ${code} / ${status}`, 0, 116, fill);
  tile.layoutSizingHorizontal = 'FILL';
  autoLayout(tile, 'VERTICAL', 6, 14);
  addStroke(tile, status === 'BLOCK' ? TOKENS.color.danger : TOKENS.color.border);
  await label(tile, code, 12, status === 'BLOCK' ? TOKENS.color.danger : TOKENS.color.primary, 'BOLD');
  await label(tile, title, 16, TOKENS.color.text, 'BOLD');
  await label(tile, status, 12, status === 'PASS_WITH_RISKS' ? TOKENS.color.warning : TOKENS.color.textMuted, 'BOLD');
  parent.appendChild(tile);
}

async function evidenceRow(parent, title, value, color = TOKENS.color.text) {
  const row = makeFrame(`Evidence / ${title}`, 0, 58, TOKENS.color.surface);
  row.layoutSizingHorizontal = 'FILL';
  autoLayout(row, 'HORIZONTAL', 10, 12);
  row.counterAxisAlignItems = 'CENTER';
  addStroke(row);
  await label(row, title, 12, TOKENS.color.textMuted, 'BOLD');
  await label(row, value, 12, color, 'BOLD');
  parent.appendChild(row);
}

function wirePrototype(source, destination) {
  if (!source || !destination) {
    return false;
  }
  try {
    source.reactions = [{
      trigger: { type: 'ON_CLICK' },
      action: {
        type: 'NODE',
        destinationId: destination.id,
        navigation: 'NAVIGATE',
        transition: { type: 'DISSOLVE', easing: { type: 'EASE_OUT' }, duration: 0.25 }
      }
    }];
    return true;
  } catch (error) {
    source.setSharedPluginData('evidence_platform', 'prototype_reaction_error', error.message);
    return false;
  }
}

async function buildFlowCard(step, x, y) {
  const [id, name, note] = step;
  const card = makeFrame(`Prototype State / ${id}`, 330, 190, TOKENS.color.surface);
  card.x = x;
  card.y = y;
  autoLayout(card, 'VERTICAL', 10, 18);
  addStroke(card, id === 'S7_BUNDLE' ? TOKENS.color.warning : TOKENS.color.border);
  await label(card, id, 12, TOKENS.color.primary, 'BOLD');
  await label(card, name, 18, TOKENS.color.primaryDark, 'BOLD');
  await label(card, note, 12, TOKENS.color.textMuted);
  await label(card, id === 'S7_BUNDLE' ? 'Final delivery state: still requires native Figma save/export.' : 'Click linked action chips to navigate.', 11, id === 'S7_BUNDLE' ? TOKENS.color.warning : TOKENS.color.textMuted, 'BOLD');
  return card;
}

async function buildFlowChip(labelText, destinationName) {
  const chip = makeFrame(`Prototype Edge / ${labelText}`, 0, 34, TOKENS.color.background);
  chip.layoutSizingHorizontal = 'FILL';
  chip.cornerRadius = TOKENS.radius.pill;
  chip.layoutMode = 'HORIZONTAL';
  chip.primaryAxisAlignItems = 'CENTER';
  chip.counterAxisAlignItems = 'CENTER';
  chip.paddingLeft = 12;
  chip.paddingRight = 12;
  chip.paddingTop = 6;
  chip.paddingBottom = 6;
  addStroke(chip, TOKENS.color.primaryLight);
  await label(chip, `${labelText} -> ${destinationName}`, 11, TOKENS.color.primary, 'BOLD');
  return chip;
}

async function buildInteractiveFlowPage() {
  ensurePage('EvidencePlatform Interactive Flow');
  const board = makeFrame('Interactive Prototype Flow / P0-P3', 1680, 1040, TOKENS.color.background);
  board.x = 80;
  board.y = 80;
  autoLayout(board, 'VERTICAL', 16, 32);
  await label(board, 'Interactive Flow', 34, TOKENS.color.primaryDark, 'BOLD');
  await label(board, 'Generated flow states include clickable prototype reactions where Figma supports node.reactions. BLOCK edge rule: failed gates must show blockers and must not navigate forward.', 14, TOKENS.color.textMuted);

  const canvas = makeFrame('Interactive flow canvas', 1560, 820, TOKENS.color.background);
  canvas.fills = [];
  canvas.clipsContent = false;
  board.appendChild(canvas);

  const cards = {};
  const positions = [
    [0, 0], [410, 0], [820, 0], [1230, 0],
    [0, 260], [410, 260], [820, 260], [1230, 260]
  ];
  for (let i = 0; i < PROTOTYPE_STEPS.length; i++) {
    const card = await buildFlowCard(PROTOTYPE_STEPS[i], positions[i][0], positions[i][1]);
    canvas.appendChild(card);
    cards[PROTOTYPE_STEPS[i][0]] = card;
  }

  let wired = 0;
  for (const [sourceId, targetId, labelText] of INTERACTIVE_FLOW_EDGES) {
    const source = cards[sourceId];
    const target = cards[targetId];
    if (!source || !target) {
      continue;
    }
    const chip = await buildFlowChip(labelText, targetId);
    source.appendChild(chip);
    if (wirePrototype(chip, target)) {
      wired += 1;
    }
  }

  const rule = makeFrame('BLOCK edge rule', 1560, 116, TOKENS.color.surface);
  rule.layoutSizingHorizontal = 'FILL';
  autoLayout(rule, 'VERTICAL', 6, 16);
  addStroke(rule, TOKENS.color.danger);
  board.appendChild(rule);
  await label(rule, 'BLOCK edge rule', 16, TOKENS.color.danger, 'BOLD');
  await label(rule, 'If any stage gate returns BLOCK or a tool returns status=error, the prototype must show blockers and must not navigate to downstream target screens.', 12, TOKENS.color.text);
  await label(rule, `Prototype reactions attempted: ${wired}/${INTERACTIVE_FLOW_EDGES.length}`, 12, TOKENS.color.textMuted, 'BOLD');
}

async function buildMotionCard(spec, x, y) {
  const [name, timing, note] = spec;
  const isBlock = name.includes('BLOCK');
  const isRisk = name.includes('PASS_WITH_RISKS');
  const card = makeFrame(name, 420, 190, TOKENS.color.surface);
  card.x = x;
  card.y = y;
  autoLayout(card, 'VERTICAL', 10, 18);
  addStroke(card, isBlock ? TOKENS.color.danger : isRisk ? TOKENS.color.warning : TOKENS.color.border);
  await label(card, name.replace('Motion Spec / ', ''), 18, isBlock ? TOKENS.color.danger : isRisk ? TOKENS.color.warning : TOKENS.color.primaryDark, 'BOLD');
  await label(card, timing, 13, TOKENS.color.primary, 'BOLD');
  await label(card, note, 12, TOKENS.color.textMuted);
  const sample = makeFrame(`${name} visual sample`, 0, 42, isBlock ? TOKENS.color.danger : isRisk ? TOKENS.color.warning : TOKENS.color.primary);
  sample.layoutSizingHorizontal = 'FILL';
  sample.cornerRadius = TOKENS.radius.pill;
  sample.opacity = isRisk ? 0.78 : 1;
  card.appendChild(sample);
  await label(sample, isBlock ? 'BLOCK' : isRisk ? 'PASS_WITH_RISKS' : 'STATE SAMPLE', 11, TOKENS.color.surface, 'BOLD');
  return card;
}

async function buildMotionSystemPage() {
  ensurePage('EvidencePlatform Motion System');
  const board = makeFrame('Motion And Microinteraction System', 1480, 960, TOKENS.color.background);
  board.x = 80;
  board.y = 80;
  autoLayout(board, 'VERTICAL', 18, 32);
  await label(board, 'Motion System', 34, TOKENS.color.primaryDark, 'BOLD');
  await label(board, 'Micro-interactions clarify affordance and risk state only. They must never imply scientific validation or fake progress.', 14, TOKENS.color.textMuted);

  const canvas = makeFrame('Motion token canvas', 1360, 660, TOKENS.color.background);
  canvas.fills = [];
  canvas.clipsContent = false;
  board.appendChild(canvas);

  const positions = [
    [0, 0], [460, 0], [920, 0],
    [0, 230], [460, 230], [920, 230],
    [0, 460]
  ];
  for (let i = 0; i < MOTION_SPECS.length; i++) {
    const card = await buildMotionCard(MOTION_SPECS[i], positions[i][0], positions[i][1]);
    canvas.appendChild(card);
  }

  const rule = makeFrame('Motion Rule / no fake progress', 1360, 116, TOKENS.color.surface);
  rule.layoutSizingHorizontal = 'FILL';
  autoLayout(rule, 'VERTICAL', 6, 16);
  addStroke(rule, TOKENS.color.danger);
  board.appendChild(rule);
  await label(rule, 'Motion Rule / no fake progress', 16, TOKENS.color.danger, 'BOLD');
  await label(rule, 'Loading Sweep and running states are allowed only while a real tools.py/app.py action is executing. PASS_WITH_RISKS Pulse and BLOCK Shake are risk disclosure affordances, not success claims.', 12, TOKENS.color.text);
}

async function buildDesignSpecPage() {
  ensurePage('EvidencePlatform Design System Spec');
  const board = makeFrame('Design System Specification', 1280, 1040, TOKENS.color.background);
  board.x = 80;
  board.y = 80;
  autoLayout(board, 'VERTICAL', 18, 32);
  await label(board, 'Design System Spec', 34, TOKENS.color.primaryDark, 'BOLD');
  await label(board, 'This page turns the evidence platform into a reproducible, developer-readable design spec: type scale, spacing, color roles, layout rules, and interaction intent.', 14, TOKENS.color.textMuted);

  const sections = [
    ['Type Scale / Display 44', 'H1 44 / H2 34 / H3 22 / Body 14 / Caption 12. Use Inter in the plugin, but preserve the app’s visual hierarchy and commercial contrast.'],
    ['Spacing Scale / 8pt Grid', 'All spacing steps should align to 8, 12, 16, 24, 32, 40, and 56. Avoid ad-hoc offsets except for deliberate optical alignment.'],
    ['Color Role / PASS_WITH_RISKS Warning', 'Primary = deep green, warning = amber, danger = red, surface = white, background = paper. Risk states must stay visible.'],
    ['Layout Rule / Responsive Shell', 'Desktop uses a wide three-zone evidence platform; tablet collapses side density; mobile prioritizes first paint, hero, and evidence context.'],
    ['Interaction Rule / Real Tools Only', 'Every obvious action chip must map back to app.py or tools.py. Decorative actions are forbidden.'],
    ['Delivery Rule / Native Figma Save', 'The final native file still requires a manual Figma save/export and registration through native-figma-receipt.json.'],
    ['Native Styles / Paint Text Effect', 'Plugin creates paint styles, text styles, and an effect style so the saved Figma source behaves like a reusable design system, not just a static mockup.'],
    ['Native Variables / EvidencePlatform Tokens', 'When supported by the Figma API, the plugin creates a EvidencePlatform Tokens variable collection with color variables for primary, warning, danger, surface, background, and text roles.']
  ];

  for (const [title, body] of sections) {
    const row = makeFrame(`Spec / ${title}`, 0, 88, TOKENS.color.surface);
    row.layoutSizingHorizontal = 'FILL';
    autoLayout(row, 'VERTICAL', 6, 16);
    addStroke(row);
    await label(row, title, 16, TOKENS.color.primaryDark, 'BOLD');
    await label(row, body, 12, TOKENS.color.textMuted);
    board.appendChild(row);
  }
}

async function buildDeveloperHandoffPage() {
  ensurePage('EvidencePlatform Developer Handoff');
  const board = makeFrame('Developer Handoff Notes', 1320, 1000, TOKENS.color.background);
  board.x = 80;
  board.y = 80;
  autoLayout(board, 'VERTICAL', 18, 32);
  await label(board, 'Developer Handoff', 34, TOKENS.color.primaryDark, 'BOLD');
  await label(board, 'This page is the bridge between the reconstructed Figma file and implementation. It states what maps to code, what maps to evidence, and what still needs external native Figma completion.', 14, TOKENS.color.textMuted);

  const checklist = [
    ['Source of Truth / app.py and tools.py', 'Do not treat plugin output as a second frontend. The runnable app stays in app.py with tools.py-backed actions.'],
    ['Evidence Paths / data/runs/<run_id>', 'Every visible claim must be backed by a run directory, gate JSON, or export artifact.'],
    ['Figma Save/Export Requirement', 'The generated file must be manually saved in Figma Desktop before native completion can be claimed.'],
    ['Registration Path / native-figma-receipt', 'After save/export, register the artifact or verified URL with scripts/register_native_figma_artifact.py.'],
    ['No Fake Progress', 'Use PASS_WITH_RISKS and BLOCK verbatim in the design. Never remove them for aesthetic reasons.'],
    ['Developer Use', 'Import tokens, inspect component masters, verify responsive frames, then hand the file back to implementation and QA.']
  ];

  for (const [title, body] of checklist) {
    const row = makeFrame(`Handoff / ${title}`, 0, 84, TOKENS.color.surface);
    row.layoutSizingHorizontal = 'FILL';
    autoLayout(row, 'VERTICAL', 6, 16);
    addStroke(row);
    await label(row, title, 16, TOKENS.color.primaryDark, 'BOLD');
    await label(row, body, 12, TOKENS.color.textMuted);
    board.appendChild(row);
  }
}

async function buildPrototypeFrame(spec, x, y) {
  const frame = makeFrame(spec.name, spec.width, spec.height, TOKENS.color.background);
  frame.x = x;
  frame.y = y;
  autoLayout(frame, 'VERTICAL', spec.width < 560 ? 14 : 22, spec.width < 560 ? 18 : 28);

  const hero = makeFrame('CommandHero', 0, 220, TOKENS.color.primaryDark);
  hero.layoutSizingHorizontal = 'FILL';
  autoLayout(hero, 'VERTICAL', 10, 24);
  hero.cornerRadius = TOKENS.radius.hero;
  frame.appendChild(hero);
  await label(hero, 'EVIDENCE PLATFORM', 12, TOKENS.color.secondary, 'BOLD');
  await label(hero, '黑土区水蚀智能预测与证据化评估平台', spec.width < 560 ? 30 : 44, TOKENS.color.surface, 'BOLD');
  await label(hero, 'P0-P3: 数据门禁 -> 模型排行 -> 解释空间化 -> 证据包导出', 14, '#d7efe7');

  const stages = makeFrame('P0-P3 Stage Rail', 0, 150, TOKENS.color.background);
  stages.layoutSizingHorizontal = 'FILL';
  stages.layoutMode = 'HORIZONTAL';
  stages.layoutWrap = spec.columns === 1 ? 'NO_WRAP' : 'WRAP';
  stages.itemSpacing = 12;
  stages.counterAxisSpacing = 12;
  stages.paddingTop = 0;
  stages.paddingBottom = 0;
  stages.paddingLeft = 0;
  stages.paddingRight = 0;
  stages.fills = [];
  frame.appendChild(stages);
  await stageTile(stages, 'P0', '止损固化', 'PASS', TOKENS.color.surface);
  await stageTile(stages, 'P1', '统一评估', 'PASS', TOKENS.color.surface);
  await stageTile(stages, 'P2', '解释空间化', 'PASS_WITH_RISKS', TOKENS.color.surface);
  await stageTile(stages, 'P3', '应用交付', 'PASS_WITH_RISKS', TOKENS.color.surface);

  const gate = makeFrame('GateWorkbench', 0, spec.width < 560 ? 250 : 190, TOKENS.color.surface);
  gate.layoutSizingHorizontal = 'FILL';
  autoLayout(gate, 'VERTICAL', 10, 18);
  addStroke(gate);
  frame.appendChild(gate);
  await label(gate, '门禁工作台', 20, TOKENS.color.primaryDark, 'BOLD');
  await evidenceRow(gate, 'Official gate source', 'data/runs/<run_id>/gates/*.json', TOKENS.color.primary);
  await evidenceRow(gate, 'Risk rule', 'BLOCK prevents next stage', TOKENS.color.danger);
  await evidenceRow(gate, 'Claim cap', 'Screenshot is not scientific validation', TOKENS.color.warning);

  const results = makeFrame('ResultWorkbench', 0, spec.width < 560 ? 340 : 260, TOKENS.color.surface);
  results.layoutSizingHorizontal = 'FILL';
  autoLayout(results, 'VERTICAL', 12, 18);
  addStroke(results);
  frame.appendChild(results);
  await label(results, '证据化评估工作台', 22, TOKENS.color.primaryDark, 'BOLD');
  await evidenceRow(results, '模型排行', 'MAE / RMSE / R2 / NRMSE / PBIAS / train_seconds');
  await evidenceRow(results, '解释图件', 'SHAP or proxy + spatial aggregation, 300dpi');
  await evidenceRow(results, '证据包', 'method_note.md / reproduce.md / gate_summary.json');

  const proto = makeFrame('Prototype flow notes', 0, 170, TOKENS.color.surface);
  proto.layoutSizingHorizontal = 'FILL';
  autoLayout(proto, 'VERTICAL', 6, 16);
  addStroke(proto);
  frame.appendChild(proto);
  await label(proto, 'Prototype Flow', 16, TOKENS.color.primaryDark, 'BOLD');
  for (const [id, name, note] of PROTOTYPE_STEPS.slice(0, spec.width < 560 ? 4 : 8)) {
    await label(proto, `${id}: ${name} - ${note}`, 11, TOKENS.color.textMuted);
  }

  return frame;
}

async function buildPrototypePage() {
  ensurePage('EvidencePlatform Prototype');
  let x = 80;
  for (const spec of TOKENS.frames) {
    await buildPrototypeFrame(spec, x, 80);
    x += spec.width + 160;
  }
}

async function buildAcceptancePage() {
  ensurePage('EvidencePlatform Acceptance Evidence');
  const board = makeFrame('Native Figma Acceptance Checklist', 1180, 820, TOKENS.color.background);
  board.x = 80;
  board.y = 80;
  autoLayout(board, 'VERTICAL', 18, 36);
  await label(board, 'Acceptance Evidence', 34, TOKENS.color.primaryDark, 'BOLD');
  await label(board, 'Use this page after running the plugin to decide whether the native Figma source/prototype is ready to save and hand off.', 15, TOKENS.color.textMuted);

  const checks = [
    ['Pages generated', 'EvidencePlatform Tokens / Components / Prototype / Acceptance Evidence'],
    ['Responsive frames', `${ACCEPTANCE_MARKERS.responsiveFrames.join(' / ')} at 1440x1080, 834x1194, 390x844`],
    ['Component masters', ACCEPTANCE_MARKERS.componentMasters.join(' / ')],
    ['Gate variants', ACCEPTANCE_MARKERS.gateVariants.join(' / ')],
    ['Interactive flow', ACCEPTANCE_MARKERS.interactiveFlow.join(' / ')],
    ['Motion system', ACCEPTANCE_MARKERS.motionSystem.join(' / ')],
    ['Risk visibility', 'PASS_WITH_RISKS and BLOCK are visible in component and prototype frames'],
    ['Prototype fidelity', 'P0-P3 flow notes match docs/figma_handoff/prototype-map.json'],
    ['Source truth', 'All workflow actions remain bound to app.py and tools.py; no second frontend'],
    ['Claim cap', 'Figma visual quality does not prove model validity, real SHAP, GeoShapley, or publication readiness'],
    ['Final save', 'Only after manual Figma inspection: save/export the Figma file as the native source artifact']
  ];

  for (const [title, detail] of checks) {
    const row = makeFrame(`Acceptance / ${title}`, 0, 62, TOKENS.color.surface);
    row.layoutSizingHorizontal = 'FILL';
    autoLayout(row, 'HORIZONTAL', 12, 14);
    row.counterAxisAlignItems = 'CENTER';
    addStroke(row);
    await label(row, title, 13, TOKENS.color.primaryDark, 'BOLD');
    await label(row, detail, 12, TOKENS.color.textMuted);
    board.appendChild(row);
  }
}

async function checklistSection(parent, title, items, accent = TOKENS.color.primaryDark) {
  const section = makeFrame(`Native Inspection / ${title}`, 0, 0, TOKENS.color.surface);
  section.layoutSizingHorizontal = 'FILL';
  autoLayout(section, 'VERTICAL', 8, 16);
  addStroke(section, accent);
  parent.appendChild(section);
  await label(section, title, 16, accent, 'BOLD');
  for (const item of items) {
    await label(section, `- ${item}`, 12, TOKENS.color.textMuted);
  }
  return section;
}

async function buildNativeInspectionChecklistPage() {
  ensurePage('EvidencePlatform Native Inspection Checklist');
  const board = makeFrame('Native Inspection Checklist / R8 Gate', 1280, 1220, TOKENS.color.background);
  board.x = 80;
  board.y = 80;
  autoLayout(board, 'VERTICAL', 16, 32);
  await label(board, 'Native Inspection Checklist', 34, TOKENS.color.primaryDark, 'BOLD');
  await label(board, NATIVE_INSPECTION_CHECKLIST.schema, 13, TOKENS.color.primary, 'BOLD');
  await label(board, 'This page mirrors docs/figma_handoff/native-figma-inspection-checklist.json. It is an on-canvas audit guide, not native completion evidence by itself.', 14, TOKENS.color.textMuted);

  await checklistSection(board, 'Required Pages', NATIVE_INSPECTION_CHECKLIST.requiredPages);
  await checklistSection(board, 'Prototype Checks', NATIVE_INSPECTION_CHECKLIST.prototypeChecks, TOKENS.color.warning);
  await checklistSection(board, 'Motion Checks', NATIVE_INSPECTION_CHECKLIST.motionChecks, TOKENS.color.warning);
  await checklistSection(board, 'Source-of-Truth Checks', NATIVE_INSPECTION_CHECKLIST.sourceTruthChecks, TOKENS.color.primary);
  await checklistSection(board, 'Forbidden Claims Until Registered', NATIVE_INSPECTION_CHECKLIST.forbiddenClaims, TOKENS.color.danger);

  const registration = makeFrame('Registration Requirement / native-figma-receipt', 0, 120, TOKENS.color.surface);
  registration.layoutSizingHorizontal = 'FILL';
  autoLayout(registration, 'VERTICAL', 6, 16);
  addStroke(registration, TOKENS.color.danger);
  board.appendChild(registration);
  await label(registration, 'Registration Requirement / native-figma-receipt', 16, TOKENS.color.danger, 'BOLD');
  await label(registration, 'After saving/exporting the native file, run scripts/register_native_figma_artifact.py with --verified-by and --confirm-pages --confirm-interactions --confirm-motion --confirm-source-truth, or --confirm-all.', 12, TOKENS.color.text);
}

async function main() {
  const styleSummary = await buildNativeStyles();
  const variableSummary = buildNativeVariables();
  await buildTokensPage();
  await buildComponentsPage();
  await buildDesignSpecPage();
  await buildPrototypePage();
  await buildInteractiveFlowPage();
  await buildMotionSystemPage();
  await buildDeveloperHandoffPage();
  await buildAcceptancePage();
  await buildNativeInspectionChecklistPage();
  figma.notify(`Black Soil Water Erosion Intelligent Prediction and Evidence-Based Evaluation Platform rebuild kit generated with native styles and variables: ${styleSummary.paintCreated} paint, ${styleSummary.textCreated} text, ${styleSummary.effectCreated} effect, ${variableSummary.colorVariablesCreated} variables.`);
  figma.closePlugin('Created editable Figma reconstruction assets, native paint/text/effect styles, optional Figma variables, design spec, interactive flow, motion system, handoff pages, and native inspection checklist. Native .fig export still depends on inspecting and saving this Figma file.');
}

main().catch(error => {
  figma.notify(`Rebuild failed: ${error.message}`);
  figma.closePlugin(`Error: ${error.message}`);
});
