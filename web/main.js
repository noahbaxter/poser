import {
    getParameterNormalized,
    setParameterNormalized,
    onParameterChange,
} from './lib/juce-bridge.js';
import { Knob } from './components/controls/knob.js';
import { Selector } from './components/controls/selector.js';
import { Toggle } from './components/controls/toggle.js';
import { PositionSlider } from './components/controls/position-slider.js';

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
    const tabRow = document.getElementById('tab-row');
    const groupBarSlot = document.getElementById('group-bar-slot');
    const selectorArea = document.getElementById('selector-area');
    const blendPanel = document.getElementById('blend-panel');

    const state = {};
    const blendKnobs = {};
    const selectors = {};

    // ---- MIC tab ----

    const micComp = config.components.mic;
    const micTab = makeTab('MIC', 'mic');
    micTab.classList.add('active');
    tabRow.appendChild(micTab);

    const micPanel = document.createElement('div');
    micPanel.className = 'selector-panel active';
    micPanel.id = 'panel-mic';
    selectorArea.appendChild(micPanel);

    selectors.mic = new Selector(micPanel, {
        options: micComp.options,
        paramId: micComp.paramId,
        groups: config.micGroups,
        entries: config.micEntries,
        groupBarContainer: groupBarSlot,
        label: 'MIC',
        onChange: (index, name) => { state.mic.selected = index; },
    });

    // ---- CAB tab ----

    const cabinet = config.components.cabinet;
    const cabTab = makeTab('CAB', 'cab');
    tabRow.appendChild(cabTab);

    const cabPanel = document.createElement('div');
    cabPanel.className = 'selector-panel';
    cabPanel.id = 'panel-cab';
    selectorArea.appendChild(cabPanel);

    const cabLayout = document.createElement('div');
    cabLayout.className = 'cabinet-layout';
    cabPanel.appendChild(cabLayout);

    const cabinetDiv = document.createElement('div');
    cabinetDiv.className = 'cabinet-panel';
    cabLayout.appendChild(cabinetDiv);

    for (const subId of ['cab', 'speaker']) {
        const sub = cabinet[subId];
        const col = document.createElement('div');
        col.className = 'cabinet-col';


        selectors[subId] = new Selector(col, {
            options: sub.options,
            paramId: sub.paramId,
            small: true,
            label: sub.label,
            onChange: (index, name) => { state[subId].selected = index; },
        });

        cabinetDiv.appendChild(col);
    }

    // Position label + slider below cab/speaker selectors
    const posHeader = document.createElement('div');
    posHeader.className = 'cabinet-col-label pos-header';
    posHeader.textContent = 'POS';
    cabLayout.appendChild(posHeader);

    const posComp = config.components.position;
    const posSlider = new PositionSlider(cabLayout, {
        options: posComp.options,
        paramId: posComp.paramId,
        onChange: (index, name) => { state.position.selected = index; },
    });
    selectors.position = posSlider;

    // ---- Tab switching ----

    const tabs = [micTab, cabTab];
    const panels = [micPanel, cabPanel];

    function switchTab(tabId) {
        tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
        panels.forEach(p => p.classList.toggle('active', p.id === `panel-${tabId}`));
        groupBarSlot.style.display = tabId === 'mic' ? '' : 'none';
    }

    tabs.forEach(t => {
        t.addEventListener('click', () => switchTab(t.dataset.tab));
    });

    // ---- Blend panel ----

    const blendConfig = [
        { id: 'mic',      label: 'MIC', blendId: micComp.blendId,                     tab: 'mic' },
        { id: 'cab',      label: 'CAB', blendId: cabinet.cab.blendId,                 tab: 'cab' },
        { id: 'speaker',  label: 'SPK', blendId: cabinet.speaker.blendId,             tab: 'cab' },
        { id: 'position', label: 'POS', blendId: config.components.position.blendId,  tab: 'cab' },
    ];

    for (const bc of blendConfig) {
        const row = document.createElement('div');
        row.className = 'blend-panel-row';

        // Toggle square
        const toggle = document.createElement('div');
        toggle.className = 'blend-toggle';

        // Label (clickable → switches tab)
        const lbl = document.createElement('div');
        lbl.className = 'blend-panel-label';
        lbl.textContent = bc.label;

        // Blend knob
        const knobSlot = document.createElement('div');
        knobSlot.className = 'blend-slot';

        blendKnobs[bc.id] = new Knob(knobSlot, {
            param: bc.blendId,
            min: -100, max: 100, step: 1,
            defaultValue: 100,
            className: 'blend-knob',
            formatValue: (v) => `${v > 0 ? '+' : ''}${v}%`,
            toNorm: (v) => (v + 100) / 200,
            fromNorm: (n) => n * 200 - 100,
        });

        const toggleGroup = document.createElement('div');
        toggleGroup.className = 'blend-toggle-group';
        toggleGroup.appendChild(toggle);
        toggleGroup.appendChild(lbl);
        row.appendChild(toggleGroup);
        row.appendChild(knobSlot);
        blendPanel.appendChild(row);

        // Init enabled state from current blend value
        const initBlend = blendKnobs[bc.id].getValue();
        const enabled = initBlend !== 0;
        state[bc.id] = { enabled, _savedBlend: 100, selected: 0 };
        toggle.classList.toggle('active', enabled);
        blendKnobs[bc.id].setDisabled(!enabled);
        if (selectors[bc.id]) selectors[bc.id].setDisabled(!enabled);
        if (bc.id === 'position') posHeader.classList.toggle('disabled', !enabled);

        // Toggle group handler (toggle + label act as one)
        toggleGroup.addEventListener('click', () => {
            state[bc.id].enabled = !state[bc.id].enabled;
            toggle.classList.toggle('active', state[bc.id].enabled);

            const knob = blendKnobs[bc.id];
            knob.setDisabled(!state[bc.id].enabled);
            if (selectors[bc.id]) selectors[bc.id].setDisabled(!state[bc.id].enabled);
            if (bc.id === 'position') posHeader.classList.toggle('disabled', !state[bc.id].enabled);

            if (!state[bc.id].enabled) {
                state[bc.id]._savedBlend = knob.getValue();
                setParameterNormalized(bc.blendId, (0 + 100) / 200); // display 0 = no effect
            } else {
                const restore = state[bc.id]._savedBlend ?? 100;
                setParameterNormalized(bc.blendId, (restore + 100) / 200);
            }

            updateTabStates();
            switchTab(bc.tab);
        });
    }

    function updateTabStates() {
        micTab.classList.toggle('disabled', !state.mic.enabled);
        const cabAllOff = !state.cab.enabled && !state.speaker.enabled && !state.position.enabled;
        cabTab.classList.toggle('disabled', cabAllOff);
    }
    updateTabStates();

    // ---- Master knobs ----

    new Knob(document.getElementById('master-push'), {
        param: 'master_push',
        min: 0, max: 500, step: 1,
        defaultValue: 100,
        className: 'master-knob push-knob',
        formatValue: (v) => `${v}%`,
        tooltipAbove: true,
        toNorm: (v) => v / 500,
        fromNorm: (n) => n * 500,
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

    new Toggle(document.getElementById('cab-filter-slot'), {
        param: 'cab_filter',
    });

    new Toggle(document.getElementById('gain-comp-slot'), {
        param: 'gain_comp',
    });
}

function makeTab(label, id) {
    const tab = document.createElement('div');
    tab.className = 'tab';
    tab.dataset.tab = id;
    tab.textContent = label;
    return tab;
}
