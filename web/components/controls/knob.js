// Knob Component
// Self-contained rotary control that binds to a JUCE parameter.
//
// Usage:
//   const knob = new Knob(container, {
//     param: 'mic_blend',       // JUCE parameter ID
//     min: 0, max: 100,         // Display range (mapped to/from normalized 0-1)
//     step: 1,
//     defaultValue: 100,
//     formatValue: v => `${v}%`,
//     className: 'blend-knob',  // CSS class for the wrapper
//     tooltipAbove: false,      // tooltip direction
//   });
//
// The knob reads its initial value from C++, sends changes on drag,
// and listens for C++ changes (automation, preset load).
// No feedback loops: setValue() is visual-only, user drags fire onChange→C++.

import {
    getParameterNormalized,
    setParameterNormalized,
    onParameterChange,
    parameterDragStarted,
    parameterDragEnded,
} from '../../lib/juce-bridge.js';
import { scrollDelta } from '../../lib/scroll.js';

export class Knob {
    constructor(container, opts) {
        this.opts = opts;
        this.param = opts.param;
        this.min = opts.min ?? 0;
        this.max = opts.max ?? 1;
        this.step = opts.step ?? 0.01;
        this.coarseStep = opts.coarseStep ?? this.step * 5;
        this.defaultValue = opts.defaultValue ?? this.min;
        this.formatValue = opts.formatValue ?? (v => `${v}`);
        this.tooltipAbove = opts.tooltipAbove ?? false;
        this.toNorm = opts.toNorm ?? (v => (v - this.min) / (this.max - this.min));
        this.fromNorm = opts.fromNorm ?? (n => this.min + n * (this.max - this.min));

        this.value = this.defaultValue;
        this.dragging = false;
        this.onChange = null;  // External callback (optional, for non-param side effects)

        this._build(container, opts.className ?? 'knob');
        this._bindEvents();
        this._readFromBackend();
        this._listenToBackend();
        this.render();
    }

    _build(container, className) {
        this.el = document.createElement('div');
        this.el.className = className;

        this.visual = document.createElement('div');
        this.visual.className = 'knob-visual';

        const body = document.createElement('div');
        body.className = 'knob-body';
        this.visual.appendChild(body);

        const indicator = document.createElement('div');
        indicator.className = 'knob-indicator';
        this.visual.appendChild(indicator);

        this.el.appendChild(this.visual);
        container.appendChild(this.el);
    }

    _bindEvents() {
        let startY = 0;
        let startValue = 0;
        const range = this.max - this.min;

        this.el.addEventListener('mousedown', (e) => {
            if (this.el.classList.contains('disabled')) return;
            this.dragging = true;
            startY = e.clientY;
            startValue = this.value;
            if (this.param) parameterDragStarted(this.param);
            this._showTooltip();
            e.preventDefault();
            e.stopPropagation();
        });

        window.addEventListener('mousemove', (e) => {
            if (!this.dragging) return;
            const dy = startY - e.clientY;
            const newVal = startValue + dy * (range / 200);
            this._setFromUser(newVal);
            this._showTooltip();
        });

        window.addEventListener('mouseup', () => {
            if (!this.dragging) return;
            if (this.param) parameterDragEnded(this.param);
            this.dragging = false;
            this._scheduleHideTooltip();
        });

        this.el.addEventListener('dblclick', (e) => {
            this._setFromUser(this.defaultValue);
            this._showTooltip();
            this._scheduleHideTooltip();
            e.stopPropagation();
        });

        this.el.addEventListener('wheel', (e) => {
            if (this.el.classList.contains('disabled')) return;
            e.preventDefault();
            const direction = scrollDelta(e) < 0 ? 1 : -1;
            let newVal;
            if (e.shiftKey) {
                newVal = this.value + direction * this.step;
            } else {
                // Snap to nearest coarse grid, then step in that direction
                const snapped = Math.round(this.value / this.coarseStep) * this.coarseStep;
                newVal = snapped + direction * this.coarseStep;
            }
            this._setFromUser(newVal);
            this._showTooltip();
            this._scheduleHideTooltip();
        });
    }

    // Read initial value from C++ backend (synchronous — available at module load)
    _readFromBackend() {
        if (!this.param) return;
        const norm = getParameterNormalized(this.param);
        this.value = this._clamp(this.fromNorm(norm));
    }

    // Listen for C++ changes (DAW automation, preset recall)
    _listenToBackend() {
        if (!this.param) return;
        onParameterChange(this.param, () => {
            if (this.dragging) return;  // Don't fight the user
            const norm = getParameterNormalized(this.param);
            this.value = this._clamp(this.fromNorm(norm));
            this.render();
            if (this.onChange) this.onChange(this.value);
        });
    }

    // User interaction: update visual + send to C++
    _setFromUser(v) {
        this.value = this._clamp(v);
        this.render();
        if (this.param) setParameterNormalized(this.param, this.toNorm(this.value));
        if (this.onChange) this.onChange(this.value);
    }

    // Programmatic: update visual only (no C++ send, no callback)
    setValue(v) {
        this.value = this._clamp(v);
        this.render();
    }

    getValue() {
        return this.value;
    }

    _clamp(v) {
        v = Math.round(v / this.step) * this.step;
        return Math.max(this.min, Math.min(this.max, v));
    }

    render() {
        const norm = (this.value - this.min) / (this.max - this.min);
        this.visual.style.transform = `rotate(${-150 + norm * 300}deg)`;
    }

    setDisabled(disabled) {
        this.el.classList.toggle('disabled', disabled);
    }

    _scheduleHideTooltip() {
        clearTimeout(Knob._activeTimer);
        Knob._activeTimer = setTimeout(() => this._hideTooltip(), 600);
    }

    static _activeTimer = null;

    // Tooltip (shared static element)
    static _tooltip = null;
    static _tooltipAnchor = null;

    static _getTooltip() {
        if (!Knob._tooltip) {
            Knob._tooltip = document.getElementById('knob-tooltip');
        }
        return Knob._tooltip;
    }

    _showTooltip() {
        const tip = Knob._getTooltip();
        if (!tip) return;
        // Reposition if anchor changed to a different knob
        if (Knob._tooltipAnchor !== this.el) {
            // Clear any pending hide from the previous knob
            if (Knob._tooltipAnchor) {
                clearTimeout(Knob._activeTimer);
            }
            const rect = this.el.getBoundingClientRect();
            tip.style.left = `${rect.left + rect.width / 2}px`;
            tip.style.top = this.tooltipAbove
                ? `${rect.top - 22}px`
                : `${rect.bottom + 6}px`;
            tip.style.transform = 'translateX(-50%)';
            Knob._tooltipAnchor = this.el;
        }
        tip.textContent = this.formatValue(this.value);
        tip.classList.add('visible');
    }

    _hideTooltip() {
        const tip = Knob._getTooltip();
        if (!tip) return;
        tip.classList.remove('visible');
        Knob._tooltipAnchor = null;
    }
}
