// Position Slider Component
// Horizontal slider with notched positions bound to a JUCE parameter.
// Visual order: EDGE | 10 09 08 ... 00 | FRED
// Data order: 00(0) 01(1) ... 10(10) EDGE(11) FRED(12)

import {
    getParameterNormalized,
    setParameterNormalized,
    onParameterChange,
    parameterDragStarted,
    parameterDragEnded,
} from '../../lib/juce-bridge.js';
import { scrollDelta } from '../../lib/scroll.js';

function selectToNorm(index, max) { return index / max; }
function normToSelect(norm, max) { return Math.round(norm * max); }

export class PositionSlider {
    constructor(container, { options, paramId, onChange }) {
        this.options = options;
        this.paramId = paramId;
        this.onChange = onChange || null;
        this.maxVal = options.length - 1;
        this.currentDataIndex = 0;
        this.dragging = false;

        // Visual order: EDGE, 10, 09, 08, ..., 00, FRED
        // Maps visual slot → data index
        this.visualOrder = this._buildVisualOrder();

        this._build(container);
        this._bindEvents();
        this._readFromBackend();
        this._listenToBackend();

        // Initial position uses percentage fallback (panel may be hidden)
        this._updateThumb();
    }

    _buildVisualOrder() {
        // Find EDGE/FRED indices, rest are numeric 00-10
        let edgeIdx = -1, fredIdx = -1;
        const numeric = [];
        for (let i = 0; i < this.options.length; i++) {
            if (this.options[i] === 'EDGE') edgeIdx = i;
            else if (this.options[i] === 'FRED') fredIdx = i;
            else numeric.push(i);
        }
        // Numeric reversed (10→0 left to right), EDGE on far left, FRED on far right
        const order = [];
        if (edgeIdx >= 0) order.push(edgeIdx);
        for (let i = numeric.length - 1; i >= 0; i--) order.push(numeric[i]);
        if (fredIdx >= 0) order.push(fredIdx);
        return order;
    }

    _visualToData(visualIdx) { return this.visualOrder[visualIdx]; }
    _dataToVisual(dataIdx) { return this.visualOrder.indexOf(dataIdx); }

    _build(container) {
        this.el = document.createElement('div');
        this.el.className = 'pos-slider';

        // Track
        this.track = document.createElement('div');
        this.track.className = 'pos-track';
        this.el.appendChild(this.track);

        // Notches in visual order, absolutely positioned at same % as thumb
        this.notchEls = [];
        const n = this.visualOrder.length;
        for (let v = 0; v < n; v++) {
            const dataIdx = this.visualOrder[v];
            const name = this.options[dataIdx];
            const isSpecial = (name === 'EDGE' || name === 'FRED');

            const notch = document.createElement('div');
            notch.className = 'pos-notch';
            if (isSpecial) notch.classList.add('special');
            notch.style.left = `${(v / (n - 1)) * 100}%`;

            const tick = document.createElement('div');
            tick.className = 'pos-tick';
            notch.appendChild(tick);

            const label = document.createElement('div');
            label.className = 'pos-label';
            label.textContent = name;
            notch.appendChild(label);

            notch.addEventListener('click', () => this._selectFromUser(dataIdx));
            this.track.appendChild(notch);
            this.notchEls.push(notch);
        }

        // Thumb
        this.thumb = document.createElement('div');
        this.thumb.className = 'pos-thumb';
        this.track.appendChild(this.thumb);

        container.appendChild(this.el);
        this._updateThumb();
    }

    _bindEvents() {
        this.thumb.addEventListener('mousedown', (e) => {
            this.dragging = true;
            parameterDragStarted(this.paramId);
            e.preventDefault();
        });

        window.addEventListener('mousemove', (e) => {
            if (!this.dragging) return;
            const rect = this.track.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const visualIdx = Math.round(x * (this.visualOrder.length - 1));
            const clamped = Math.max(0, Math.min(this.visualOrder.length - 1, visualIdx));
            const dataIdx = this._visualToData(clamped);
            if (dataIdx !== this.currentDataIndex) {
                this.currentDataIndex = dataIdx;
                this._updateThumb();
                setParameterNormalized(this.paramId, selectToNorm(dataIdx, this.maxVal));
                if (this.onChange) this.onChange(dataIdx, this.options[dataIdx]);
            }
        });

        window.addEventListener('mouseup', () => {
            if (!this.dragging) return;
            this.dragging = false;
            parameterDragEnded(this.paramId);
        });

        // Scroll wheel: moves in visual order
        this.el.addEventListener('wheel', (e) => {
            e.preventDefault();
            const curVisual = this._dataToVisual(this.currentDataIndex);
            const nextVisual = curVisual + (scrollDelta(e) < 0 ? 1 : -1);
            if (nextVisual >= 0 && nextVisual < this.visualOrder.length) {
                this._selectFromUser(this._visualToData(nextVisual));
            }
        });
    }

    _selectFromUser(dataIdx) {
        this.currentDataIndex = dataIdx;
        this._updateThumb();
        parameterDragStarted(this.paramId);
        setParameterNormalized(this.paramId, selectToNorm(dataIdx, this.maxVal));
        parameterDragEnded(this.paramId);
        if (this.onChange) this.onChange(dataIdx, this.options[dataIdx]);
    }

    _updateThumb() {
        const visualIdx = this._dataToVisual(this.currentDataIndex);
        const pct = (visualIdx / (this.visualOrder.length - 1)) * 100;
        this.thumb.style.left = `${pct}%`;

        this.notchEls.forEach((el, v) => {
            el.classList.toggle('active', this.visualOrder[v] === this.currentDataIndex);
        });
    }

    _readFromBackend() {
        const norm = getParameterNormalized(this.paramId);
        this.currentDataIndex = normToSelect(norm, this.maxVal);
        this._updateThumb();
    }

    _listenToBackend() {
        onParameterChange(this.paramId, () => {
            if (this.dragging) return;
            const norm = getParameterNormalized(this.paramId);
            this.currentDataIndex = normToSelect(norm, this.maxVal);
            this._updateThumb();
        });
    }

    setDisabled(disabled) {
        this.el.classList.toggle('disabled', disabled);
    }
}
