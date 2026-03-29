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
 * Build a small "swap mic" dropdown: select which mic the source signal
 * was recorded with. Subtracts that mic's curve before adding the target.
 * Value 0 = Off, 1..N = mic index (stored as 0-based in C++).
 * Inserted after afterRow in the DOM.
 */
export function buildSwapMicSelect(afterRow, micOptions, paramId, param) {
    const row = document.createElement('div');
    row.className = 'swap-mic-row';

    const label = document.createElement('div');
    label.className = 'swap-mic-label';
    label.textContent = 'SWAP';
    row.appendChild(label);

    const select = document.createElement('select');
    select.className = 'swap-mic-select';
    select.title = 'Swap — subtract a source mic before adding the target (for re-mic\'ing cab IRs)';

    // Option 0 = Off
    const offOpt = document.createElement('option');
    offOpt.value = '0';
    offOpt.textContent = '\u2014';  // em dash = "off"
    select.appendChild(offOpt);

    // Deduplicate mic names (variants share the same name)
    const seen = new Set();
    for (let i = 0; i < micOptions.length; i++) {
        const name = micOptions[i];
        if (seen.has(name)) continue;
        seen.add(name);
        const opt = document.createElement('option');
        opt.value = String(i + 1);  // 1-based: 0 = off
        opt.textContent = name;
        select.appendChild(opt);
    }

    // Read initial value from backend
    const range = param.max - param.min;
    const initNorm = getParameterNormalized(paramId);
    const initVal = Math.round(param.min + initNorm * range);
    select.value = String(initVal);

    select.addEventListener('change', () => {
        const val = parseInt(select.value, 10);
        const norm = (val - param.min) / range;
        parameterDragStarted(paramId);
        setParameterNormalized(paramId, norm);
        parameterDragEnded(paramId);
    });

    onParameterChange(paramId, () => {
        const norm = getParameterNormalized(paramId);
        const val = Math.round(param.min + norm * range);
        select.value = String(val);
    });

    row.appendChild(select);
    afterRow.parentNode.insertBefore(row, afterRow);
}
