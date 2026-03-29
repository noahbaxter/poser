// Control configuration — tuning, wiring, and display for every control.
// No DOM here — just data and utility functions.

// step = fine (shift+scroll), coarseStep = normal scroll
// display: 'pct' | 'pctSigned' | 'hz' | 'db'
// norm: 'linear' | 'skewed' | 'percent' (percent = C++ 0-1 → display 0-100%)
// className: CSS class applied to the knob element

export const KNOBS = {
    blend:  { step: 1,    coarseStep: 5,    display: 'pctSigned', norm: 'percent', className: 'blend-knob'          },
    scale:  { step: 1,    coarseStep: 10,   display: 'pct',       norm: 'percent', className: 'push-knob'             },
    trim:   { step: 0.1,  coarseStep: 1,    display: 'db',        norm: 'linear',  className: 'master-knob'         },
    loCut:  { step: 2,    coarseStep: 10,   display: 'hz',        norm: 'skewed',  className: 'master-knob'         },
    hiCut:  { step: 50,   coarseStep: 250,  display: 'hz',        norm: 'skewed',  className: 'master-knob'         },
};

// Master knob wiring: DOM element → JUCE param → knob type
export const MASTER_CONTROLS = [
    { elementId: 'master-push',   paramId: 'master_push',    knobType: 'scale' },
    { elementId: 'master-trim',   paramId: 'output_trim',    knobType: 'trim'  },
    { elementId: 'knob-low-cut',  paramId: 'curve_low_cut',  knobType: 'loCut' },
    { elementId: 'knob-high-cut', paramId: 'curve_high_cut', knobType: 'hiCut' },
];

// Toggle wiring: DOM element → JUCE param
export const TOGGLE_CONTROLS = [
    { elementId: 'cab-filter-slot', paramId: 'cab_filter',      title: 'Cab filter — apply per-cab HPF + per-speaker LPF' },
    { elementId: 'gain-comp-slot',  paramId: 'gain_comp',       title: 'Gain compensation — normalize loudness across curves' },
    { elementId: 'mic-curve-mode-slot', paramId: 'mic_curve_mode', title: 'Full mode — use raw mic response (dramatic) vs character only (subtle)' },
];

// ---- Utility: build Knob constructor opts from KNOBS entry + C++ param ----

const FORMATTERS = {
    hz:        (hz) => hz >= 1000 ? `${(hz / 1000).toFixed(1)}kHz` : `${Math.round(hz)}Hz`,
    pct:       (v) => `${Math.round(v)}%`,
    pctSigned: (v) => `${v > 0 ? '+' : ''}${Math.round(v)}%`,
    db:        (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} dB`,
};

const NORMS = {
    skewed: (p) => ({
        toNorm: (v) => Math.pow((v - p.min) / (p.max - p.min), p.skew),
        fromNorm: (n) => p.min + (p.max - p.min) * Math.pow(n, 1.0 / p.skew),
    }),
    linear: (p) => ({
        toNorm: (v) => (v - p.min) / (p.max - p.min),
        fromNorm: (n) => p.min + n * (p.max - p.min),
    }),
    percent: (p) => ({
        toNorm: (v) => (v / 100 - p.min) / (p.max - p.min),
        fromNorm: (n) => (p.min + n * (p.max - p.min)) * 100,
    }),
};

export function buildKnobOpts(knobType, param) {
    const k = KNOBS[knobType];
    const isPercent = k.norm === 'percent';
    return {
        min: isPercent ? param.min * 100 : param.min,
        max: isPercent ? param.max * 100 : param.max,
        step: k.step,
        coarseStep: k.coarseStep,
        defaultValue: isPercent ? param.defaultValue * 100 : param.defaultValue,
        className: k.className,
        formatValue: FORMATTERS[k.display],
        tooltipAbove: knobType !== 'blend',
        ...NORMS[k.norm](param),
    };
}
