// Selector Component
// Circular discrete selector with optional group paging (left/right arrows).
//
// Usage:
//   const sel = new Selector(container, {
//       options: ['SM57', 'SM58', ...],     // display names
//       paramId: 'mic_select',              // JUCE parameter ID
//       groups: [{ name: 'Vocal', indices: [12, 13] }, ...],  // optional
//       onChange: (globalIndex, name) => {},
//   });

import {
    getParameterNormalized,
    setParameterNormalized,
    onParameterChange,
    parameterDragStarted,
    parameterDragEnded,
} from '../../lib/juce-bridge.js';

function selectToNorm(index, max) { return index / max; }
function normToSelect(norm, max) { return Math.round(norm * max); }

export class Selector {
    constructor(container, opts) {
        this.allOptions = opts.options;
        this.paramId = opts.paramId;
        this.groups = opts.groups || null;
        this.onChange = opts.onChange || null;
        this.compact = opts.compact || false;
        this.small = opts.small || false;
        this.maxVal = this.allOptions.length - 1;

        this.currentGlobalIndex = 0;
        this.currentGroupIdx = 0;
        this.dragging = false;

        this._build(container);
        this._bindDrag();
        this._readFromBackend();
        this._listenToBackend();
    }

    _build(container) {
        this.wrap = document.createElement('div');
        const cls = ['selector-wrap'];
        if (this.compact) cls.push('compact');
        if (this.small) cls.push('small');
        this.wrap.className = cls.join(' ');

        // Group buttons — only if groups exist
        if (this.groups) {
            this.groupBar = document.createElement('div');
            this.groupBar.className = 'selector-group-bar';

            this.groupButtons = [];
            this.groups.forEach((group, i) => {
                const btn = document.createElement('div');
                btn.className = 'selector-group-btn';
                btn.textContent = group.name;
                btn.addEventListener('click', () => this._switchToGroup(i));
                this.groupBar.appendChild(btn);
                this.groupButtons.push(btn);
            });

            this.wrap.appendChild(this.groupBar);
        }

        this.ring = document.createElement('div');
        this.ring.className = 'selector-ring';
        this.wrap.appendChild(this.ring);

        if (!this.compact) {
            this.center = document.createElement('div');
            this.center.className = 'selector-knob-center';
            const indicator = document.createElement('div');
            indicator.className = 'selector-indicator';
            this.center.appendChild(indicator);
            this.wrap.appendChild(this.center);
        }

        container.appendChild(this.wrap);

        // Build the ring for current group or all options
        this._buildRing();
    }

    _buildRing() {
        this.ring.innerHTML = '';
        this.optionElements = [];

        const options = this._currentOptions();
        const n = options.length;

        if (this.compact) {
            // Compact mode: vertical list
            options.forEach((label, i) => {
                const el = document.createElement('div');
                el.className = 'selector-option';
                el.textContent = label;
                el.addEventListener('click', (e) => {
                    this._selectLocalFromUser(i);
                    e.stopPropagation();
                });
                this.ring.appendChild(el);
                this.optionElements.push(el);
            });
        } else if (this.small) {
            // Small ring: percentage-based centering
            const radiusPct = 38; // % of container width
            options.forEach((label, i) => {
                const el = document.createElement('div');
                el.className = 'selector-option';
                el.textContent = label;

                const angle = (i / n) * 360 - 90;
                const rad = angle * Math.PI / 180;
                const xPct = 50 + radiusPct * Math.cos(rad);
                const yPct = 50 + radiusPct * Math.sin(rad);

                el.style.left = `${xPct}%`;
                el.style.top = `${yPct}%`;
                el.style.transform = 'translate(-50%, -50%)';

                el.addEventListener('click', (e) => {
                    this._selectLocalFromUser(i);
                    e.stopPropagation();
                });

                this.ring.appendChild(el);
                this.optionElements.push(el);
            });
        } else {
            // Ring mode: circular layout
            const ringRadius = 105;
            const wrapW = 340;
            const cx = wrapW / 2;
            const cy = this.groups ? (cx - 15) : cx;

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
                    el.style.right = `${wrapW - x}px`;
                    el.style.transform = 'translateY(-50%)';
                } else {
                    el.style.left = `${x}px`;
                    el.style.transform = 'translate(-50%, -50%)';
                }

                el.addEventListener('click', (e) => {
                    this._selectLocalFromUser(i);
                    e.stopPropagation();
                });

                this.ring.appendChild(el);
                this.optionElements.push(el);
            });
        }

        if (this.groups) {
            this.groupButtons.forEach((btn, i) =>
                btn.classList.toggle('active', i === this.currentGroupIdx));
        }

        // Update highlight for current selection
        this._highlightCurrent();
    }

    _currentOptions() {
        if (!this.groups) return this.allOptions;
        const group = this.groups[this.currentGroupIdx];
        return group.indices.map(i => this.allOptions[i]);
    }

    _currentIndices() {
        if (!this.groups) return this.allOptions.map((_, i) => i);
        return this.groups[this.currentGroupIdx].indices;
    }

    _selectLocalFromUser(localIdx) {
        const indices = this._currentIndices();
        const n = indices.length;
        localIdx = ((localIdx % n) + n) % n;
        const globalIdx = indices[localIdx];

        this.currentGlobalIndex = globalIdx;
        this._highlightCurrent();

        parameterDragStarted(this.paramId);
        setParameterNormalized(this.paramId, selectToNorm(globalIdx, this.maxVal));
        parameterDragEnded(this.paramId);

        if (this.onChange) this.onChange(globalIdx, this.allOptions[globalIdx]);
    }

    _highlightCurrent() {
        const indices = this._currentIndices();
        const localIdx = indices.indexOf(this.currentGlobalIndex);
        const n = indices.length;

        this.optionElements.forEach((el, j) => el.classList.toggle('active', j === localIdx));

        if (!this.compact && localIdx >= 0) {
            this.center.style.transform = `translate(-50%, -50%) rotate(${(localIdx / n) * 360}deg)`;
        }
    }

    _switchToGroup(groupIdx) {
        if (groupIdx === this.currentGroupIdx) return;
        this.currentGroupIdx = groupIdx;
        this._buildRing();

        // Select first item in new group
        const indices = this._currentIndices();
        if (indices.length > 0) {
            this._selectLocalFromUser(0);
        }
    }

    _bindDrag() {
        let dragStartY = 0;
        let dragAccum = 0;

        if (!this.compact) {
            this.center.addEventListener('mousedown', (e) => {
                this.dragging = true;
                dragStartY = e.clientY;
                dragAccum = 0;
                e.preventDefault();
            });

            window.addEventListener('mousemove', (e) => {
                if (!this.dragging) return;
                const dy = dragStartY - e.clientY;
                dragStartY = e.clientY;
                dragAccum += dy;
                if (Math.abs(dragAccum) >= 25) {
                    const indices = this._currentIndices();
                    const localIdx = indices.indexOf(this.currentGlobalIndex);
                    this._selectLocalFromUser(localIdx + Math.sign(dragAccum));
                    dragAccum = 0;
                }
            });

            window.addEventListener('mouseup', () => { this.dragging = false; });
        }

        this.wrap.addEventListener('wheel', (e) => {
            e.preventDefault();
            const indices = this._currentIndices();
            const localIdx = indices.indexOf(this.currentGlobalIndex);
            this._selectLocalFromUser(localIdx + (e.deltaY > 0 ? 1 : -1));
        });
    }

    _readFromBackend() {
        const norm = getParameterNormalized(this.paramId);
        this.currentGlobalIndex = normToSelect(norm, this.maxVal);

        // If grouped, switch to the group containing this mic
        if (this.groups) {
            for (let g = 0; g < this.groups.length; g++) {
                if (this.groups[g].indices.includes(this.currentGlobalIndex)) {
                    this.currentGroupIdx = g;
                    break;
                }
            }
            this._buildRing();
        }

        this._highlightCurrent();
    }

    _listenToBackend() {
        onParameterChange(this.paramId, () => {
            if (this.dragging) return;
            const norm = getParameterNormalized(this.paramId);
            this.currentGlobalIndex = normToSelect(norm, this.maxVal);

            // Switch group if needed
            if (this.groups) {
                const indices = this._currentIndices();
                if (!indices.includes(this.currentGlobalIndex)) {
                    for (let g = 0; g < this.groups.length; g++) {
                        if (this.groups[g].indices.includes(this.currentGlobalIndex)) {
                            this.currentGroupIdx = g;
                            this._buildRing();
                            break;
                        }
                    }
                }
            }

            this._highlightCurrent();
        });
    }

    getIndex() { return this.currentGlobalIndex; }
}
