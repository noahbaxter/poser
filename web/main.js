import {
    getParameterNormalized,
    setParameterNormalized,
    onParameterChange,
    parameterDragStarted,
    parameterDragEnded,
} from './lib/juce-bridge.js';
import { Knob } from './components/knob.js';

// ---- Parameter mapping helpers ----
function selectToNorm(index, max) { return index / max; }
function normToSelect(norm, max) { return Math.round(norm * max); }

// ---- Component definitions ----
const COMPONENTS = {
    mic:      { label: 'MIC',  options: ['C414', 'SM57', 'SM58', 'SM7B', 'U87'] },
    cab:      { label: 'CAB',  options: ['DZL', 'MAR', 'MES', 'ORN'] },
    speaker:  { label: 'SPK',  options: ['12K', 'EDVH', 'G80', 'GOV', 'H30', 'M25', 'T75', 'V30'] },
    position: { label: 'POS',  options: ['00', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', 'EDGE', 'FRED'] },
};

const state = {};
for (const id of Object.keys(COMPONENTS)) {
    state[id] = { enabled: true };
}

// ---- Selector knob (big, discrete, 360deg, vertical drag) ----

function createSelector(container, { options, paramId, onChange }) {
    const wrap = document.createElement('div');
    wrap.className = 'selector-wrap';

    const ring = document.createElement('div');
    ring.className = 'selector-ring';
    wrap.appendChild(ring);

    const n = options.length;
    const maxVal = n - 1;
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
        const cosVal = Math.cos(rad);
        if (cosVal > 0.3) {
            el.style.left = `${x}px`;
            el.style.transform = 'translateY(-50%)';
        } else if (cosVal < -0.3) {
            el.style.right = `${(cx * 2) - x}px`;
            el.style.transform = 'translateY(-50%)';
        } else {
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

    let currentIndex = 0;
    let dragging = false;
    let dragStartY = 0;
    let dragAccum = 0;

    function selectIndex(i) {
        currentIndex = ((i % n) + n) % n;
        center.style.transform = `translate(-50%, -50%) rotate(${(currentIndex / n) * 360}deg)`;
        optionElements.forEach((el, j) => el.classList.toggle('active', j === currentIndex));
    }

    function selectIndexFromUser(i) {
        selectIndex(i);
        parameterDragStarted(paramId);
        setParameterNormalized(paramId, selectToNorm(currentIndex, maxVal));
        parameterDragEnded(paramId);
        if (onChange) onChange(currentIndex, options[currentIndex]);
    }

    // Click on labels
    optionElements.forEach((el, i) => {
        el.removeEventListener('click', () => {});  // remove the basic one
    });
    // Re-bind with user version
    ring.querySelectorAll('.selector-option').forEach((el, i) => {
        el.addEventListener('click', (e) => {
            selectIndexFromUser(i);
            e.stopPropagation();
        });
    });

    // Vertical drag
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
        if (Math.abs(dragAccum) >= 25) {
            selectIndexFromUser(currentIndex + Math.sign(dragAccum));
            dragAccum = 0;
        }
    });

    window.addEventListener('mouseup', () => { dragging = false; });

    wrap.addEventListener('wheel', (e) => {
        e.preventDefault();
        selectIndexFromUser(currentIndex + (e.deltaY > 0 ? 1 : -1));
    });

    // Read initial value from C++
    const initNorm = getParameterNormalized(paramId);
    selectIndex(normToSelect(initNorm, maxVal));

    // Listen for C++ changes
    onParameterChange(paramId, () => {
        if (dragging) return;
        const idx = normToSelect(getParameterNormalized(paramId), maxVal);
        selectIndex(idx);
    });

    container.appendChild(wrap);
    return { selectIndex, getIndex: () => currentIndex };
}

// ---- Build blend knobs (one per component, bound to params) ----

const blendKnobs = {};

for (const [id, comp] of Object.entries(COMPONENTS)) {
    const slot = document.getElementById(`blend-${id}`);

    blendKnobs[id] = new Knob(slot, {
        param: `${id}_blend`,
        min: 0, max: 100, step: 1,
        defaultValue: 100,
        className: 'blend-knob',
        formatValue: (v) => `${v}%`,
        toNorm: (v) => v / 100,
        fromNorm: (n) => n * 100,
    });
}

// ---- Build master knobs ----

const pushKnob = new Knob(document.getElementById('master-push'), {
    param: 'master_push',
    min: -500, max: 500, step: 1,
    defaultValue: 100,
    className: 'master-knob push-knob',
    formatValue: (v) => `${v > 0 ? '+' : ''}${v}%`,
    tooltipAbove: true,
    toNorm: (v) => (v + 500) / 1000,
    fromNorm: (n) => n * 1000 - 500,
});

const trimKnob = new Knob(document.getElementById('master-trim'), {
    param: 'output_trim',
    min: -24, max: 24, step: 0.1,
    defaultValue: 0,
    className: 'master-knob',
    formatValue: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} dB`,
    tooltipAbove: true,
    toNorm: (v) => (v + 24) / 48,
    fromNorm: (n) => n * 48 - 24,
});

// ---- Curve shaping knobs ----

// Use getParameterNormalized/setParameterNormalized directly — let JUCE handle the skew.
// The Knob component works in normalized 0-1 space, we just format the display from the
// actual parameter value via getParameterScaled (not yet available) or approximate.

const lowCutKnob = new Knob(document.getElementById('knob-low-cut'), {
    param: 'curve_low_cut',
    min: 0, max: 1, step: 0.001,
    defaultValue: 0,
    className: 'master-knob',
    formatValue: (v) => {
        const hz = 20 + (2000 - 20) * Math.pow(v, 1.0 / 0.3);
        return hz >= 1000 ? `${(hz/1000).toFixed(1)}kHz` : `${Math.round(hz)}Hz`;
    },
    tooltipAbove: true,
    // Already in normalized space, no conversion needed
    toNorm: (v) => v,
    fromNorm: (n) => n,
});

const highCutKnob = new Knob(document.getElementById('knob-high-cut'), {
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

// ---- Build selector panels ----

const selectors = {};

for (const [id, comp] of Object.entries(COMPONENTS)) {
    const panel = document.getElementById(`panel-${id}`);

    selectors[id] = createSelector(panel, {
        options: comp.options,
        paramId: `${id}_select`,
        onChange: (index, name) => {
            state[id].selected = index;
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
    const knob = blendKnobs[id];
    knob.setDisabled(!state[id].enabled);

    if (!state[id].enabled) {
        state[id]._savedBlend = knob.getValue();
        setParameterNormalized(`${id}_blend`, 0);
    } else {
        const restore = state[id]._savedBlend ?? 100;
        setParameterNormalized(`${id}_blend`, restore / 100);
    }
}

// Shift+click on blend knobs
for (const [id, knob] of Object.entries(blendKnobs)) {
    knob.el.addEventListener('click', (e) => {
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
