// Bottom panel: builds master knobs, toggles, and blend panel DOM.

import {
    setParameterNormalized,
    getParameterNormalized,
    onParameterChange,
    parameterDragStarted,
    parameterDragEnded,
} from '../lib/juce-bridge.js';
import { Knob } from './controls/knob.js';
import { Toggle } from './controls/toggle.js';
import { buildKnobOpts, MASTER_CONTROLS, TOGGLE_CONTROLS } from '../utils/control-config.js';

export function buildMasterControls(params) {
    const knobs = {};
    for (const mc of MASTER_CONTROLS) {
        knobs[mc.paramId] = new Knob(document.getElementById(mc.elementId), {
            param: mc.paramId,
            ...buildKnobOpts(mc.knobType, params[mc.paramId]),
        });
    }

    for (const tc of TOGGLE_CONTROLS) {
        new Toggle(document.getElementById(tc.elementId), {
            param: tc.paramId,
            title: tc.title,
        });
    }

    return knobs;
}

export function buildBlendPanel(blendPanelEl, blendConfig, params, selectors, switchTab, onStateChange) {
    const blendKnobs = {};
    const state = {};
    const rows = {};

    for (const bc of blendConfig) {
        const row = document.createElement('div');
        row.className = 'blend-panel-row';

        const toggle = document.createElement('div');
        toggle.className = 'blend-toggle';

        const lbl = document.createElement('div');
        lbl.className = 'blend-panel-label';
        lbl.textContent = bc.label;

        const knobSlot = document.createElement('div');
        knobSlot.className = 'blend-slot';

        const knob = new Knob(knobSlot, {
            param: bc.blendId,
            ...buildKnobOpts('blend', params[bc.blendId]),
        });
        blendKnobs[bc.id] = knob;

        const toggleGroup = document.createElement('div');
        toggleGroup.className = 'blend-toggle-group';
        toggleGroup.appendChild(toggle);
        toggleGroup.appendChild(lbl);
        row.appendChild(toggleGroup);
        row.appendChild(knobSlot);
        blendPanelEl.appendChild(row);
        rows[bc.id] = row;

        const enabled = knob.getValue() !== 0;
        state[bc.id] = { enabled, _savedBlend: 100, selected: 0 };
        toggle.classList.toggle('active', enabled);
        knob.setDisabled(!enabled);
        if (selectors[bc.id]) selectors[bc.id].setDisabled(!enabled);

        toggleGroup.addEventListener('click', () => {
            state[bc.id].enabled = !state[bc.id].enabled;
            toggle.classList.toggle('active', state[bc.id].enabled);
            knob.setDisabled(!state[bc.id].enabled);
            if (selectors[bc.id]) selectors[bc.id].setDisabled(!state[bc.id].enabled);

            if (!state[bc.id].enabled) {
                state[bc.id]._savedBlend = knob.getValue();
                setParameterNormalized(bc.blendId, 0.5);
            } else {
                const restore = state[bc.id]._savedBlend ?? 100;
                setParameterNormalized(bc.blendId, knob.opts.toNorm(restore));
            }

            if (onStateChange) onStateChange(state);
            switchTab(bc.tab);
        });
    }

    return { blendKnobs, state, rows };
}

/**
 * Build swap mic controls: a toggle + "SWAP" label + dropdown, placed
 * in the SCALE box below the knob.  Styled to match the blend panel rows.
 * Value 0 = Off, 1..N = mic index (stored as 0-based in C++).
 */
export function buildSwapMicSelect(swapRow, micOptions, paramId, param) {
    // Toggle box (matches .blend-toggle)
    const toggle = document.createElement('div');
    toggle.className = 'blend-toggle';
    toggle.title = 'Swap \u2014 subtract a source mic before adding the target';

    // Label (same class as blend labels for alignment)
    const lbl = document.createElement('div');
    lbl.className = 'blend-panel-label';
    lbl.textContent = 'SWP';

    const toggleGroup = document.createElement('div');
    toggleGroup.className = 'blend-toggle-group';
    toggleGroup.appendChild(toggle);
    toggleGroup.appendChild(lbl);

    // Mic dropdown
    const select = document.createElement('select');
    select.className = 'swap-mic-select';

    // Option 0 = Off (hidden — toggle handles on/off)
    const offOpt = document.createElement('option');
    offOpt.value = '0';
    offOpt.textContent = '\u2014';
    select.appendChild(offOpt);

    // Deduplicate mic names (variants share the same name)
    const seen = new Set();
    for (let i = 0; i < micOptions.length; i++) {
        const name = micOptions[i];
        if (seen.has(name)) continue;
        seen.add(name);
        const opt = document.createElement('option');
        opt.value = String(i + 1);
        opt.textContent = name;
        select.appendChild(opt);
    }

    swapRow.appendChild(toggleGroup);
    swapRow.appendChild(select);

    // --- State ---
    const range = param.max - param.min;
    // Default to SM57 (find its value in the dropdown)
    let lastMic = 1;
    for (const opt of select.options) {
        if (opt.textContent === 'SM57') { lastMic = parseInt(opt.value, 10); break; }
    }

    function readParam() {
        return Math.round(param.min + getParameterNormalized(paramId) * range);
    }
    function writeParam(val) {
        parameterDragStarted(paramId);
        setParameterNormalized(paramId, (val - param.min) / range);
        parameterDragEnded(paramId);
    }
    function updateUI(val) {
        const active = val > 0;
        toggle.classList.toggle('active', active);
        select.value = String(active ? val : lastMic);
        select.classList.toggle('disabled', !active);
    }

    // Init from backend
    const initVal = readParam();
    if (initVal > 0) lastMic = initVal;
    updateUI(initVal);

    // Toggle group click: toggle swap on/off
    toggleGroup.addEventListener('click', () => {
        const current = readParam();
        if (current > 0) {
            lastMic = current;
            writeParam(0);
            updateUI(0);
        } else {
            writeParam(lastMic);
            updateUI(lastMic);
        }
    });

    // Dropdown change: select mic + activate
    select.addEventListener('change', () => {
        const val = parseInt(select.value, 10);
        if (val > 0) lastMic = val;
        writeParam(val);
        updateUI(val);
    });

    // Release focus after interaction so spacebar passes through to DAW transport
    select.addEventListener('change', () => select.blur());
    select.addEventListener('wheel', () => select.blur(), { passive: true });

    // Scroll on dropdown to cycle through mics
    // Collect non-off option values for cycling
    const micValues = Array.from(select.options)
        .map(o => parseInt(o.value, 10))
        .filter(v => v > 0);

    select.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (!micValues.length) return;
        const current = parseInt(select.value, 10);
        const idx = micValues.indexOf(current > 0 ? current : lastMic);
        const dir = e.deltaY > 0 ? 1 : -1;
        const next = micValues[Math.max(0, Math.min(micValues.length - 1, idx + dir))];
        lastMic = next;
        writeParam(next);
        updateUI(next);
    });

    // Sync from backend
    onParameterChange(paramId, () => {
        const val = readParam();
        if (val > 0) lastMic = val;
        updateUI(val);
    });
}
