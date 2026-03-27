# UI Redesign Implementation Plan

Full spec in memory: `project_ui_redesign.md`

## Phase 1 — Data Layer (no UI)

- [x] **1.1** Multi-group mics: registry.py `group` → `groups` list. Update compile.py
  to handle multi-group membership (mic appears in multiple group index arrays).
  3 groups: Drum, Vocal, Instrument.
- [x] **1.2** Update param defaults in PluginProcessor.cpp:
  - mic_select default = SM57 index 11
  - cab_blend, speaker_blend, position_blend defaults = 0.0 (OFF)
  - cab_select, speaker_select defaults = 0 (Flat)
  - position_select default = 0 (center)
- [x] **1.3** Regenerate CurveData.h (`manage.py build`)

## Phase 2 — CSS Foundation

- [x] **2.1** CSS custom properties refactor: all pixel sizes into `:root` variables
  (ring size, knob sizes, font sizes, gaps, etc.)
- [x] **2.2** Plugin window size: 560×560 in PluginEditor.cpp

## Phase 3 — Layout Rebuild

- [ ] **3.1** 2-tab structure: MIC and CAB. Remove old 4-tab / cabinet dual-selector code.
  CAB tab grayed out (not hidden) when all cab components OFF.
- [ ] **3.2** MIC tab: big ring selector + 3 group buttons (Drum/Vocal/Instrument)
- [ ] **3.3** Blend panel component: 4 rows (MIC/CAB/SPK/POS), each with toggle square
  + label + small blend knob. Always visible at bottom-right. Clicking label switches
  the active view to that component. Toggle OFF = blend forced to 0, ON = restore to
  saved value (default 100%).
- [ ] **3.4** Bottom-left controls: LO CUT, TRIM, HI CUT knobs + FILTER and COMP toggles
- [ ] **3.5** Scale knob: centered, fixed position above bottom controls, always visible

## Phase 4 — CAB Tab

- [ ] **4.1** Split view layout: selector lists (left) + visual preview (right)
- [ ] **4.2** Cab preview visualization: SVG wireframe — cabinet outline (rounded rect)
  + speaker cone (circle with concentric rings + speaker name label)
- [ ] **4.3** Color-coded cab accents: Orange=orange, Mesa=black, Marshall=gray, Diesel=TBD.
  Subtle trim/highlight, not full recolor.
- [ ] **4.4** Position slider: interactive mic icon on horizontal track across speaker cone.
  0=center, 1-10=smooth motion to edge, EDGE=discrete past-edge, FRED=discrete special.
  Snap points. Click or drag to move.
- [ ] **4.5** Components toggle OFF → their visual element disappears from preview.
  All OFF → preview empty, CAB tab grayed out.

## Phase 5 — EQ Curve Viewer

- [ ] **5.1** Canvas/SVG magnitude response display component
- [ ] **5.2** Data: composite of all active curves × blend × scale + cab filter if on.
  No gain compensation in the display.
- [ ] **5.3** Window resize: toggle button extends plugin window taller. Close shrinks it back.
  Main content stays in place, curve appears below.

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

## Notes

- Position has no Flat option. OFF via blend panel toggle.
- Mic groups allow overlap (mic in multiple groups).
- Scale knob is 2nd most important control after the ring.
- The PluginEditor.cpp init payload needs restructuring for the new layout.
- Existing compact/small selector modes in selector.js can be removed or reused for cab lists.
