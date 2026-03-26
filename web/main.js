import { setParameterNormalized, getParameterNormalized, onParameterChange, parameterDragStarted, parameterDragEnded } from './lib/juce-bridge.js';

// ---- Parameter helpers ----
// Selectors: int 0-N mapped to normalized 0-1
// Blends: -5.0 to 5.0 mapped to normalized 0-1 (UI shows -500% to 500%)
// Dry/wet: 0-1 normalized directly
// Trim: -24 to 24 mapped to normalized 0-1

function selectToNorm(index, max) { return index / max; }
function normToSelect(norm, max) { return Math.round(norm * max); }
function blendToNorm(v) { return (v + 500) / 1000; }  // -500..500 → 0..1
function normToBlend(n) { return n * 1000 - 500; }      // 0..1 → -500..500
function trimToNorm(v) { return (v + 24) / 48; }
function normToTrim(n) { return n * 48 - 24; }

// ---- Data ----

const COMPONENTS = {
    mic: {
        label: 'MIC',
        options: ['C414', 'M160', 'MD421', 'MD441', 'R121', 'SM57'],
        defaultIndex: 5,
    },
    cab: {
        label: 'CAB',
        options: ['DZL', 'MAR', 'MES', 'ORN'],
        defaultIndex: 2,
    },
    speaker: {
        label: 'SPEAKER',
        options: ['12K', 'EDVH', 'G80', 'GOV', 'H30', 'M25', 'T75', 'V30'],
        defaultIndex: 7,
    },
    position: {
        label: 'POSITION',
        options: ['00', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', 'EDGE', 'FRED'],
        defaultIndex: 5,
    },
};

const state = {};
for (const [id, comp] of Object.entries(COMPONENTS)) {
    state[id] = { selected: comp.defaultIndex, enabled: true };
}
state.masterDryWet = 100;
state.outputTrim = 0;

// ---- Tooltip ----

const tooltip = document.getElementById('knob-tooltip');
let tooltipAnchor = null;

function showTooltip(anchorEl, text, above = false) {
    if (!tooltipAnchor) {
        const rect = anchorEl.getBoundingClientRect();
        tooltip.style.left = `${rect.left + rect.width / 2}px`;
        if (above) {
            tooltip.style.top = `${rect.top - 22}px`;
        } else {
            tooltip.style.top = `${rect.bottom + 6}px`;
        }
        tooltip.style.transform = 'translateX(-50%)';
        tooltipAnchor = anchorEl;
    }
    tooltip.textContent = text;
    tooltip.classList.add('visible');
}

function hideTooltip() {
    tooltip.classList.remove('visible');
    tooltipAnchor = null;
}

// ---- Master knob (continuous, vertical drag) ----

function createMasterKnob(container, opts) {
    const wrap = document.createElement('div');
    wrap.className = 'master-knob';

    const visual = document.createElement('div');
    visual.className = 'knob-visual';

    const body = document.createElement('div');
    body.className = 'knob-body';
    visual.appendChild(body);

    const indicator = document.createElement('div');
    indicator.className = 'knob-indicator';
    visual.appendChild(indicator);

    wrap.appendChild(visual);

    let currentValue = opts.value;
    const range = opts.max - opts.min;
    const fmt = opts.formatValue || ((v) => `${v}`);

    function render() {
        const norm = (currentValue - opts.min) / range;
        visual.style.transform = `rotate(${-150 + norm * 300}deg)`;
    }

    function setValue(v) {
        currentValue = Math.max(opts.min, Math.min(opts.max, Math.round(v / opts.step) * opts.step));
        render();
        if (opts.onChange) opts.onChange(currentValue);
    }

    let dragging = false;
    let dragStartY = 0;
    let dragStartValue = 0;

    wrap.addEventListener('mousedown', (e) => {
        dragging = true;
        dragStartY = e.clientY;
        dragStartValue = currentValue;
        showTooltip(wrap, fmt(currentValue), true);
        e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const dy = dragStartY - e.clientY;
        setValue(dragStartValue + dy * (range / 200));
        showTooltip(wrap, fmt(currentValue), true);
    });

    window.addEventListener('mouseup', () => {
        if (dragging) hideTooltip();
        dragging = false;
    });

    wrap.addEventListener('dblclick', () => setValue(opts.value));

    render();
    container.appendChild(wrap);
    return { setValue, getValue: () => currentValue };
}

// ---- Selector knob (big, discrete, 360deg, vertical drag) ----

function createSelector(container, { options, defaultIndex, onChange }) {
    const wrap = document.createElement('div');
    wrap.className = 'selector-wrap';

    const ring = document.createElement('div');
    ring.className = 'selector-ring';
    wrap.appendChild(ring);

    const n = options.length;
    const optionElements = [];
    const ringRadius = 120;
    const cx = 190, cy = 190;

    options.forEach((label, i) => {
        const el = document.createElement('div');
        el.className = 'selector-option';
        el.textContent = label;

        const angle = (i / n) * 360 - 90;
        const rad = angle * Math.PI / 180;
        const x = cx + ringRadius * Math.cos(rad);
        const y = cy + ringRadius * Math.sin(rad);

        el.style.top = `${y}px`;

        // Right half: left-align (anchor left edge near knob)
        // Left half: right-align (anchor right edge near knob)
        // Top/bottom: center
        const cosVal = Math.cos(rad);
        if (cosVal > 0.3) {
            // Right side
            el.style.left = `${x}px`;
            el.style.transform = 'translateY(-50%)';
        } else if (cosVal < -0.3) {
            // Left side
            el.style.right = `${(cx * 2) - x}px`;
            el.style.transform = 'translateY(-50%)';
        } else {
            // Top or bottom center
            el.style.left = `${x}px`;
            el.style.transform = 'translate(-50%, -50%)';
        }

        el.addEventListener('click', () => selectIndex(i));
        ring.appendChild(el);
        optionElements.push(el);
    });

    const center = document.createElement('div');
    center.className = 'selector-knob-center';
    const indicator = document.createElement('div');
    indicator.className = 'selector-indicator';
    center.appendChild(indicator);
    wrap.appendChild(center);

    let currentIndex = defaultIndex;

    function selectIndex(i) {
        currentIndex = ((i % n) + n) % n;
        center.style.transform = `translate(-50%, -50%) rotate(${(currentIndex / n) * 360}deg)`;
        optionElements.forEach((el, j) => el.classList.toggle('active', j === currentIndex));
        if (onChange) onChange(currentIndex, options[currentIndex]);
    }

    let dragging = false;
    let dragStartY = 0;
    let dragAccum = 0;

    center.addEventListener('mousedown', (e) => {
        dragging = true;
        dragStartY = e.clientY;
        dragAccum = 0;
        e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const dy = dragStartY - e.clientY;
        dragStartY = e.clientY;
        dragAccum += dy;
        const threshold = 25;
        if (Math.abs(dragAccum) >= threshold) {
            selectIndex(currentIndex + Math.sign(dragAccum));
            dragAccum = 0;
        }
    });

    window.addEventListener('mouseup', () => { dragging = false; });

    wrap.addEventListener('wheel', (e) => {
        e.preventDefault();
        selectIndex(currentIndex + (e.deltaY > 0 ? 1 : -1));
    });

    selectIndex(defaultIndex);
    container.appendChild(wrap);
    return { getIndex: () => currentIndex, selectIndex };
}

// ---- Build blend knobs ----

function createBlendKnob(container, opts) {
    const wrap = document.createElement('div');
    wrap.className = 'blend-knob';

    const visual = document.createElement('div');
    visual.className = 'knob-visual';

    const body = document.createElement('div');
    body.className = 'knob-body';
    visual.appendChild(body);

    const indicator = document.createElement('div');
    indicator.className = 'knob-indicator';
    visual.appendChild(indicator);

    wrap.appendChild(visual);

    let currentValue = opts.value;
    const range = opts.max - opts.min;
    const fmt = opts.formatValue || ((v) => `${v}`);

    function render() {
        const norm = (currentValue - opts.min) / range;
        visual.style.transform = `rotate(${-150 + norm * 300}deg)`;
    }

    function setValue(v) {
        currentValue = Math.max(opts.min, Math.min(opts.max, Math.round(v / opts.step) * opts.step));
        render();
        if (opts.onChange) opts.onChange(currentValue);
    }

    let dragging = false;
    let dragStartY = 0;
    let dragStartValue = 0;

    wrap.addEventListener('mousedown', (e) => {
        if (wrap.classList.contains('disabled')) {
            e.preventDefault();
            e.stopPropagation();
            return;
        }
        dragging = true;
        dragStartY = e.clientY;
        dragStartValue = currentValue;
        showTooltip(wrap, fmt(currentValue));
        e.preventDefault();
        e.stopPropagation();
    });

    window.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const dy = dragStartY - e.clientY;
        setValue(dragStartValue + dy * (range / 200));
        showTooltip(wrap, fmt(currentValue));
    });

    window.addEventListener('mouseup', () => {
        if (dragging) hideTooltip();
        dragging = false;
    });

    wrap.addEventListener('dblclick', (e) => {
        setValue(opts.value);
        e.stopPropagation();
    });

    render();
    container.appendChild(wrap);
    return { setValue, getValue: () => currentValue };
}

const blendKnobElements = {};
const blendKnobs = {};

for (const [id, comp] of Object.entries(COMPONENTS)) {
    const slot = document.getElementById(`blend-${id}`);
    state[id].blend = 100;

    blendKnobs[id] = createBlendKnob(slot, {
        min: -500,
        max: 500,
        value: 100,
        step: 1,
        formatValue: (v) => `${v > 0 ? '+' : ''}${v}%`,
        onChange: (v) => {
            state[id].blend = v;
            setParameterNormalized(`${id}_blend`, blendToNorm(v));
        },
    });
    blendKnobElements[id] = slot.querySelector('.blend-knob');
}

// ---- Build master knobs ----

const dryWetKnob = createMasterKnob(document.getElementById('master-drywet'), {
    min: 0,
    max: 100,
    value: 100,
    step: 1,
    formatValue: (v) => `${v}%`,
    onChange: (v) => {
        state.masterDryWet = v;
        setParameterNormalized('dry_wet', v / 100);
    },
});

const trimKnob = createMasterKnob(document.getElementById('master-trim'), {
    min: -24,
    max: 24,
    value: 0,
    step: 0.1,
    formatValue: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} dB`,
    onChange: (v) => {
        state.outputTrim = v;
        setParameterNormalized('output_trim', trimToNorm(v));
    },
});

// ---- Build selector panels ----

const selectors = {};

for (const [id, comp] of Object.entries(COMPONENTS)) {
    const panel = document.getElementById(`panel-${id}`);

    selectors[id] = createSelector(panel, {
        options: comp.options,
        defaultIndex: comp.defaultIndex,
        onChange: (index, name) => {
            state[id].selected = index;
            const paramId = `${id}_select`;
            const maxVal = comp.options.length - 1;
            parameterDragStarted(paramId);
            setParameterNormalized(paramId, selectToNorm(index, maxVal));
            parameterDragEnded(paramId);
        },
    });
}

// ---- Tab switching ----

const tabs = document.querySelectorAll('.tab');
const panels = document.querySelectorAll('.selector-panel');

function switchTab(tabId) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
    panels.forEach(p => p.classList.toggle('active', p.id === `panel-${tabId}`));
}

tabs.forEach(t => {
    t.addEventListener('click', () => switchTab(t.dataset.tab));
});

switchTab('mic');

// ---- Shift+click to toggle enable/disable ----

function toggleComponent(id) {
    state[id].enabled = !state[id].enabled;
    const knobEl = blendKnobElements[id];
    if (knobEl) knobEl.classList.toggle('disabled', !state[id].enabled);

    // Set blend to 0 in C++ when disabled, restore when enabled
    if (!state[id].enabled) {
        state[id]._savedBlend = state[id].blend;
        setParameterNormalized(`${id}_blend`, blendToNorm(0));
    } else {
        const restore = state[id]._savedBlend ?? 100;
        setParameterNormalized(`${id}_blend`, blendToNorm(restore));
    }
}

// Shift+click on blend knobs
for (const [id, knobEl] of Object.entries(blendKnobElements)) {
    knobEl.addEventListener('click', (e) => {
        if (e.shiftKey) {
            toggleComponent(id);
            e.stopPropagation();
        }
    });
}

// Shift+click on tabs
tabs.forEach(t => {
    t.addEventListener('click', (e) => {
        if (e.shiftKey) {
            toggleComponent(t.dataset.tab);
            e.stopPropagation();
            e.preventDefault();
        }
    });
});

// ---- Sync initial state: push all JS defaults to C++ on load ----

// Read initial state from C++ backend and sync UI to match
function syncFromBackend() {
    for (const [id, comp] of Object.entries(COMPONENTS)) {
        // Read and apply selector
        const selectNorm = getParameterNormalized(`${id}_select`);
        const maxVal = comp.options.length - 1;
        const index = normToSelect(selectNorm, maxVal);
        state[id].selected = index;
        if (selectors[id]) selectors[id].selectIndex(index);

        // Read and apply blend
        const blendNorm = getParameterNormalized(`${id}_blend`);
        const blendVal = normToBlend(blendNorm);
        state[id].blend = blendVal;
        if (blendKnobs[id]) blendKnobs[id].setValue(blendVal);
    }

    // Read and apply dry/wet
    const dryWetVal = getParameterNormalized('dry_wet') * 100;
    state.masterDryWet = dryWetVal;
    if (dryWetKnob) dryWetKnob.setValue(dryWetVal);

    // Read and apply trim
    const trimVal = normToTrim(getParameterNormalized('output_trim'));
    state.outputTrim = trimVal;
    if (trimKnob) trimKnob.setValue(trimVal);
}

// Sync once bridge is ready
function trySyncFromBackend() {
    try {
        syncFromBackend();
    } catch {
        setTimeout(trySyncFromBackend, 50);
    }
}
trySyncFromBackend();
