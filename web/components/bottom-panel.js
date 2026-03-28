// Bottom panel: builds master knobs, toggles, and blend panel DOM.

import { setParameterNormalized } from '../lib/juce-bridge.js';
import { Knob } from './controls/knob.js';
import { Toggle } from './controls/toggle.js';
import { buildKnobOpts, MASTER_CONTROLS, TOGGLE_CONTROLS } from '../utils/control-config.js';

export function buildMasterControls(params) {
    for (const mc of MASTER_CONTROLS) {
        new Knob(document.getElementById(mc.elementId), {
            param: mc.paramId,
            ...buildKnobOpts(mc.knobType, params[mc.paramId]),
        });
    }

    for (const tc of TOGGLE_CONTROLS) {
        new Toggle(document.getElementById(tc.elementId), {
            param: tc.paramId,
        });
    }
}

export function buildBlendPanel(blendPanelEl, blendConfig, params, selectors, switchTab, onStateChange) {
    const blendKnobs = {};
    const state = {};

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

    return { blendKnobs, state };
}
