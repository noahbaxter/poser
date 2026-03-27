import {
    getParameterNormalized,
    setParameterNormalized,
    onParameterChange,
} from './lib/juce-bridge.js';
import { Knob } from './components/controls/knob.js';
import { Selector } from './components/controls/selector.js';
import { Toggle } from './components/controls/toggle.js';

// ---- Init: called by C++ with component data ----

window.__poser_init__ = function(config) {
    if (window.__poser_initialized__) return;
    window.__poser_initialized__ = true;

    // Version
    const verEl = document.getElementById('version-num');
    if (verEl) verEl.textContent = 'v' + config.version;

    buildUI(config);
};

function buildUI(config) {
    const componentIds = Object.keys(config.components);
    const state = {};
    const blendKnobs = {};
    const selectors = {};

    // ---- Tabs ----
    const tabRow = document.getElementById('tab-row');
    const blendRow = document.getElementById('blend-row');
    const selectorArea = document.getElementById('selector-area');

    for (const id of componentIds) {
        const comp = config.components[id];
        state[id] = { enabled: true };

        // Tab
        const tab = document.createElement('div');
        tab.className = 'tab';
        tab.dataset.tab = id;
        tab.textContent = comp.label;
        tabRow.appendChild(tab);

        // Blend knob slot
        const blendSlot = document.createElement('div');
        blendSlot.className = 'blend-slot';
        blendRow.appendChild(blendSlot);

        blendKnobs[id] = new Knob(blendSlot, {
            param: comp.blendId,
            min: 0, max: 100, step: 1,
            defaultValue: 100,
            className: 'blend-knob',
            formatValue: (v) => `${v}%`,
            toNorm: (v) => v / 100,
            fromNorm: (n) => n * 100,
        });

        // Selector panel
        const panel = document.createElement('div');
        panel.className = 'selector-panel';
        panel.id = `panel-${id}`;
        selectorArea.appendChild(panel);

        const selectorOpts = {
            options: comp.options,
            paramId: comp.paramId,
            onChange: (index, name) => { state[id].selected = index; },
        };

        // Mic gets group support
        if (id === 'mic' && config.micGroups) {
            selectorOpts.groups = config.micGroups;
        }

        selectors[id] = new Selector(panel, selectorOpts);
    }

    // Activate first tab
    const tabs = tabRow.querySelectorAll('.tab');
    const panels = selectorArea.querySelectorAll('.selector-panel');
    tabs[0]?.classList.add('active');
    panels[0]?.classList.add('active');

    function switchTab(tabId) {
        tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
        panels.forEach(p => p.classList.toggle('active', p.id === `panel-${tabId}`));
    }

    tabs.forEach(t => {
        t.addEventListener('click', (e) => {
            if (e.shiftKey) {
                toggleComponent(t.dataset.tab);
                e.stopPropagation();
                e.preventDefault();
            } else {
                switchTab(t.dataset.tab);
            }
        });
    });

    // ---- Shift+click to toggle enable/disable ----

    function toggleComponent(id) {
        state[id].enabled = !state[id].enabled;
        const knob = blendKnobs[id];
        knob.setDisabled(!state[id].enabled);

        if (!state[id].enabled) {
            state[id]._savedBlend = knob.getValue();
            setParameterNormalized(config.components[id].blendId, 0);
        } else {
            const restore = state[id]._savedBlend ?? 100;
            setParameterNormalized(config.components[id].blendId, restore / 100);
        }
    }

    for (const [id, knob] of Object.entries(blendKnobs)) {
        knob.el.addEventListener('click', (e) => {
            if (e.shiftKey) {
                toggleComponent(id);
                e.stopPropagation();
            }
        });
    }

    // ---- Master knobs ----

    new Knob(document.getElementById('master-push'), {
        param: 'master_push',
        min: -500, max: 500, step: 1,
        defaultValue: 100,
        className: 'master-knob push-knob',
        formatValue: (v) => `${v > 0 ? '+' : ''}${v}%`,
        tooltipAbove: true,
        toNorm: (v) => (v + 500) / 1000,
        fromNorm: (n) => n * 1000 - 500,
    });

    new Knob(document.getElementById('master-trim'), {
        param: 'output_trim',
        min: -24, max: 24, step: 0.1,
        defaultValue: 0,
        className: 'master-knob',
        formatValue: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} dB`,
        tooltipAbove: true,
        toNorm: (v) => (v + 24) / 48,
        fromNorm: (n) => n * 48 - 24,
    });

    new Knob(document.getElementById('knob-low-cut'), {
        param: 'curve_low_cut',
        min: 0, max: 1, step: 0.001,
        defaultValue: 0,
        className: 'master-knob',
        formatValue: (v) => {
            const hz = 20 + (2000 - 20) * Math.pow(v, 1.0 / 0.3);
            return hz >= 1000 ? `${(hz/1000).toFixed(1)}kHz` : `${Math.round(hz)}Hz`;
        },
        tooltipAbove: true,
        toNorm: (v) => v,
        fromNorm: (n) => n,
    });

    new Knob(document.getElementById('knob-high-cut'), {
        param: 'curve_high_cut',
        min: 0, max: 1, step: 0.001,
        defaultValue: 1,
        className: 'master-knob',
        formatValue: (v) => {
            const hz = 1000 + (20000 - 1000) * Math.pow(v, 1.0 / 0.3);
            return hz >= 1000 ? `${(hz/1000).toFixed(1)}kHz` : `${Math.round(hz)}Hz`;
        },
        tooltipAbove: true,
        toNorm: (v) => v,
        fromNorm: (n) => n,
    });

    // ---- Cab LPF toggle ----

    new Toggle(document.getElementById('cab-lpf-slot'), {
        param: 'cab_lpf',
        label: 'ON',
    });
}
