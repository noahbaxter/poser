# UI Redesign Implementation Plan

Full spec in memory: `project_ui_redesign.md`

## Phase 1 — Data Layer ✓

- [x] **1.1** Multi-group mics, compile.py multi-group support
- [x] **1.2** Param defaults (SM57, cab/spk/pos OFF)
- [x] **1.3** Regenerate CurveData.h

## Phase 2 — CSS Foundation ✓

- [x] **2.1** CSS custom properties refactor
- [x] **2.2** Plugin window 560×560

## Phase 3 — Layout Rebuild ✓

- [x] **3.1** 2-tab MIC/CAB, blend panel, scale in right panel
- [x] **3.2** MIC ring + DRUM/VOX/INST groups with scroll wheel
- [x] **3.3** Blend panel: toggle + label + knob, selector greying
- [x] **3.4** Bottom controls split: LO HI FLT | CMP TRIM
- [x] **3.5** Toggle redesign, sub-group arcs, Flat removal

## Phase 4 — Position Slider + Polish

- [x] **4.1** Horizontal position slider on CAB tab: notches for 0-10, EDGE, FRED.
  Click or drag to select. Snap points. Scroll wheel support.
- [x] **4.2** Small CAB ring selectors: tighten label radius

## Phase 5 — EQ Curve Viewer

- [ ] **5.1** Canvas/SVG magnitude response display component
- [ ] **5.2** Data: composite of all active curves × blend × scale + cab filter if on.
  No gain compensation in the display.
- [ ] **5.3** Window resize: toggle button extends plugin window taller. Close shrinks it back.
  Main content stays in place, curve appears below.

## Deferred — CAB Visual Preview

- [ ] **D.1** Split view layout: selector lists (left) + visual preview (right)
- [ ] **D.2** Cab preview: SVG wireframe cabinet outline + speaker cone
- [ ] **D.3** Color-coded cab accents (Orange=orange, Mesa=black, etc.)
- [ ] **D.4** Position slider integrated into speaker cone visualization
- [ ] **D.5** Components toggle OFF → visual elements disappear

## Key Files

- `tools/curves/registry.py` — mic definitions and groups
- `tools/curves/compile.py` — header generation, group handling
- `src/CurveData.h` — generated curve data
- `src/PluginProcessor.cpp` / `.h` — params, defaults
- `src/PluginEditor.cpp` / `.h` — init payload, relays, window size
- `web/main.js` — UI entry point, tab building, controls
- `web/main.css` — all styling
- `web/components/controls/selector.js` — ring selector
- `web/components/controls/knob.js` — knob component
- `web/components/controls/toggle.js` — toggle component
- `web/index.html` — DOM structure
