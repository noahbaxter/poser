import { Selector } from './components/controls/selector.js';
import { PositionSlider } from './components/controls/position-slider.js';
import { buildBlendPanel, buildMasterControls, buildSwapMicSelect } from './components/bottom-panel.js';
import { FreqResponse } from './components/freq-response.js';

// ---- Theme toggle ----

document.getElementById('theme-toggle').addEventListener('click', () => {
    const html = document.documentElement;
    const dark = html.getAttribute('data-theme') === 'dark';
    html.setAttribute('data-theme', dark ? '' : 'dark');
});

// ---- Init: called by C++ with component data ----

window.__poser_init__ = function(config) {
    if (window.__poser_initialized__) return;
    window.__poser_initialized__ = true;

    const verEl = document.getElementById('version-num');
    if (verEl) verEl.textContent = 'v' + config.version;

    buildUI(config);
};

function buildUI(config) {
    const tabRow = document.getElementById('tab-row');
    const groupBarSlot = document.getElementById('group-bar-slot');
    const selectorArea = document.getElementById('selector-area');

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
        onChange: (index) => { state.mic.selected = index; },
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
            onChange: (index) => { state[subId].selected = index; },
        });

        cabinetDiv.appendChild(col);
    }

    const posHeader = document.createElement('div');
    posHeader.className = 'cabinet-col-label pos-header';
    posHeader.textContent = 'POS';
    cabLayout.appendChild(posHeader);

    const posComp = config.components.position;
    selectors.position = new PositionSlider(cabLayout, {
        options: posComp.options,
        paramId: posComp.paramId,
        onChange: (index) => { state.position.selected = index; },
    });

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

    // ---- Bottom controls ----

    const blendConfig = [
        { id: 'mic',      label: 'MIC', blendId: micComp.blendId,                    tab: 'mic' },
        { id: 'cab',      label: 'CAB', blendId: cabinet.cab.blendId,                tab: 'cab' },
        { id: 'speaker',  label: 'SPK', blendId: cabinet.speaker.blendId,            tab: 'cab' },
        { id: 'position', label: 'POS', blendId: config.components.position.blendId, tab: 'cab' },
    ];

    function onBlendStateChange(s) {
        micTab.classList.toggle('disabled', !s.mic.enabled);
        // CAB tab never fades — it's always accessible
        posHeader.classList.toggle('disabled', !s.position.enabled);
    }

    const { state, rows } = buildBlendPanel(
        document.getElementById('blend-panel'), blendConfig, config.params,
        selectors, switchTab, onBlendStateChange,
    );
    onBlendStateChange(state);

    const masterKnobs = buildMasterControls(config.params);

    // Swap mic controls — toggle + dropdown in SCALE box
    buildSwapMicSelect(
        document.getElementById('swap-row'),
        micComp.options,
        'swap_mic_select',
        config.params['swap_mic_select'],
    );

    // EQ viewer
    const eqViewer = new FreqResponse(
        document.getElementById('eq-viewer'),
        document.getElementById('eq-toggle'),
        {
            sampleRate: config.sampleRate,
            fftSize: config.fftSize,
            spectrumSize: config.spectrumSize,
        },
    );
    eqViewer.setCutKnobs(masterKnobs['curve_low_cut'], masterKnobs['curve_high_cut']);
}

function makeTab(label, id) {
    const tab = document.createElement('div');
    tab.className = 'tab';
    tab.dataset.tab = id;
    tab.textContent = label;
    return tab;
}
