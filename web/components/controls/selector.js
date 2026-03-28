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
        this.groupBarContainer = opts.groupBarContainer || null;
        this.entries = opts.entries || null; // MicEntry[] for variant support
        this.onChange = opts.onChange || null;
        this.compact = opts.compact || false;
        this.small = opts.small || false;
        this.maxVal = this.allOptions.length - 1;

        this.currentGlobalIndex = 0;
        this.currentGroupIdx = 0;
        this.dragging = false;

        this.label = opts.label || null;
        this.labelFixed = opts.labelFixed !== false; // default: doesn't rotate
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

            // Scroll wheel on group bar: up = right, down = left, block at edges
            this.groupBar.addEventListener('wheel', (e) => {
                e.preventDefault();
                const next = this.currentGroupIdx + (e.deltaY < 0 ? 1 : -1);
                if (next >= 0 && next < this.groups.length) {
                    this._switchToGroup(next);
                }
            });

            // Render group bar externally if container provided, otherwise inside wrap
            (this.groupBarContainer || this.wrap).appendChild(this.groupBar);
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
            if (this.label && !this.labelFixed) {
                const lbl = document.createElement('div');
                lbl.className = 'selector-knob-label';
                lbl.textContent = this.label;
                this.center.appendChild(lbl);
            }
            this.wrap.appendChild(this.center);
            if (this.label && this.labelFixed) {
                const lbl = document.createElement('div');
                lbl.className = 'selector-knob-label';
                lbl.textContent = this.label;
                this.wrap.appendChild(lbl);
            }
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
            // Small ring: all sizing derived from --knob-size
            const style = getComputedStyle(this.wrap);
            const knobSize = parseInt(style.getPropertyValue('--knob-size')) || 100;
            const labelGapRatio = parseFloat(style.getPropertyValue('--sel-label-gap')) || 0.31;
            const ringRadius = knobSize * (0.5 + labelGapRatio);
            const wrapW = parseInt(style.getPropertyValue('width')) || 210;
            const cx = wrapW / 2;
            const cy = cx;
            options.forEach((label, i) => {
                const el = document.createElement('div');
                el.className = 'selector-option';
                el.textContent = label;

                const angle = (i / n) * 360 - 90;
                const rad = angle * Math.PI / 180;
                const x = cx + ringRadius * Math.cos(rad);
                const y = cy + ringRadius * Math.sin(rad);

                el.style.left = `${x}px`;
                el.style.top = `${y}px`;
                el.style.transform = 'translate(-50%, -50%)';

                el.addEventListener('click', (e) => {
                    this._selectLocalFromUser(i);
                    e.stopPropagation();
                });

                this.ring.appendChild(el);
                this.optionElements.push(el);
            });
        } else {
            // Ring mode: all sizing derived from --knob-size
            const style = getComputedStyle(this.wrap);
            const knobSize = parseInt(style.getPropertyValue('--knob-size')) || 130;
            const labelGapRatio = parseFloat(style.getPropertyValue('--sel-label-gap')) || 0.31;
            const ringRadius = knobSize * (0.5 + labelGapRatio);
            const wrapW = parseInt(style.getPropertyValue('width')) || 340;
            const cx = wrapW / 2;
            const cy = cx;

            const indices = this._currentIndices();
            options.forEach((label, i) => {
                const el = document.createElement('div');
                el.className = 'selector-option';
                el.textContent = label;

                // Variant badge for multi-variant entries
                if (this.entries) {
                    const ent = this.entries[indices[i]];
                    if (ent && ent.numVariants > 1) {
                        const badge = document.createElement('span');
                        badge.className = 'variant-badge';
                        badge.textContent = `1/${ent.numVariants}`;
                        el.appendChild(badge);
                    }
                }

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

                // Scroll on a label = cycle that mic's variants
                if (this.entries) {
                    const entIdx = indices[i];
                    el.addEventListener('wheel', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const ent = this.entries[entIdx];
                        if (!ent || ent.numVariants <= 1) return;
                        // Select this mic first if not already selected
                        if (this._entryForGlobal(this.currentGlobalIndex) !== entIdx) {
                            this._selectLocalFromUser(i);
                        }
                        this._cycleVariant(e.deltaY > 0 ? -1 : 1);
                    });
                }

                this.ring.appendChild(el);
                this.optionElements.push(el);
            });
        }

        if (this.groups) {
            this.groupButtons.forEach((btn, i) =>
                btn.classList.toggle('active', i === this.currentGroupIdx));

            // Draw sub-group arcs behind tagged items
            this._drawTagArcs(options.length);
        }

        // Update highlight for current selection
        this._highlightCurrent();
    }

    _drawTagArcs(n) {
        // Remove old arcs
        this.wrap.querySelectorAll('.tag-arc').forEach(el => el.remove());

        if (this.compact || this.small) return;
        const group = this.groups[this.currentGroupIdx];
        if (!group.tags || group.tags.length === 0) return;

        const style = getComputedStyle(this.wrap);
        const knobSize = parseInt(style.getPropertyValue('--knob-size')) || 130;
        const labelGapRatio = parseFloat(style.getPropertyValue('--sel-label-gap')) || 0.31;
        const ringRadius = knobSize * (0.5 + labelGapRatio);
        const wrapW = parseInt(style.getPropertyValue('width')) || 340;
        const cx = wrapW / 2;
        const cy = cx;
        const arcRadius = ringRadius + 22;

        const TAG_COLORS = { kick: 'rgba(0,0,0,0.15)' };
        const sliceAngle = 360 / n; // degrees per item

        for (const tag of group.tags) {
            const color = TAG_COLORS[tag.name] || 'rgba(0,0,0,0.04)';
            // Arc starts halfway before first item and ends halfway after last item
            const startAngle = ((tag.start * sliceAngle) - sliceAngle / 2 - 90) * Math.PI / 180;
            const endAngle = ((tag.end * sliceAngle) + sliceAngle / 2 - 90) * Math.PI / 180;

            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.classList.add('tag-arc');
            svg.setAttribute('width', wrapW);
            svg.setAttribute('height', wrapW);
            svg.style.cssText = 'position:absolute;inset:0;pointer-events:none;';

            const x1 = cx + arcRadius * Math.cos(startAngle);
            const y1 = cy + arcRadius * Math.sin(startAngle);
            const x2 = cx + arcRadius * Math.cos(endAngle);
            const y2 = cy + arcRadius * Math.sin(endAngle);
            const largeArc = (endAngle - startAngle) > Math.PI ? 1 : 0;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d',
                `M ${cx} ${cy} L ${x1} ${y1} A ${arcRadius} ${arcRadius} 0 ${largeArc} 1 ${x2} ${y2} Z`);
            path.setAttribute('fill', color);
            svg.appendChild(path);
            this.wrap.appendChild(svg);
        }
    }

    // --- Entry/variant helpers ---

    // Which entry index owns a given flat global index?
    _entryForGlobal(globalIdx) {
        if (!this.entries) return globalIdx;
        for (let e = 0; e < this.entries.length; e++) {
            const ent = this.entries[e];
            if (globalIdx >= ent.firstIndex && globalIdx < ent.firstIndex + ent.numVariants)
                return e;
        }
        return 0;
    }

    // Current variant offset within the selected entry
    _currentVariantOffset() {
        if (!this.entries) return 0;
        const ent = this.entries[this._entryForGlobal(this.currentGlobalIndex)];
        return this.currentGlobalIndex - ent.firstIndex;
    }

    _currentOptions() {
        if (this.entries) {
            // Ring shows entry names
            if (!this.groups) return this.entries.map(e => e.name);
            const group = this.groups[this.currentGroupIdx];
            return group.indices.map(i => this.entries[i].name);
        }
        if (!this.groups) return this.allOptions;
        const group = this.groups[this.currentGroupIdx];
        return group.indices.map(i => this.allOptions[i]);
    }

    // Returns entry indices (when entries exist) or flat indices
    _currentIndices() {
        if (this.entries) {
            if (!this.groups) return this.entries.map((_, i) => i);
            return this.groups[this.currentGroupIdx].indices;
        }
        if (!this.groups) return this.allOptions.map((_, i) => i);
        return this.groups[this.currentGroupIdx].indices;
    }

    _selectLocalFromUser(localIdx) {
        const indices = this._currentIndices();
        const n = indices.length;
        localIdx = ((localIdx % n) + n) % n;
        const idx = indices[localIdx];

        // Map entry index → flat parameter index (use firstIndex)
        const globalIdx = this.entries ? this.entries[idx].firstIndex : idx;

        this.currentGlobalIndex = globalIdx;
        this._highlightCurrent();

        parameterDragStarted(this.paramId);
        setParameterNormalized(this.paramId, selectToNorm(globalIdx, this.maxVal));
        parameterDragEnded(this.paramId);

        if (this.onChange) this.onChange(globalIdx, this.allOptions[globalIdx]);
    }

    // Cycle variant within the currently selected entry
    _cycleVariant(direction) {
        if (!this.entries) return;
        const entryIdx = this._entryForGlobal(this.currentGlobalIndex);
        const ent = this.entries[entryIdx];
        if (ent.numVariants <= 1) return;

        const offset = this.currentGlobalIndex - ent.firstIndex;
        const newOffset = offset + direction;
        if (newOffset < 0 || newOffset >= ent.numVariants) return;

        this.currentGlobalIndex = ent.firstIndex + newOffset;
        this._highlightCurrent();

        parameterDragStarted(this.paramId);
        setParameterNormalized(this.paramId, selectToNorm(this.currentGlobalIndex, this.maxVal));
        parameterDragEnded(this.paramId);

        if (this.onChange) this.onChange(this.currentGlobalIndex, this.allOptions[this.currentGlobalIndex]);
    }

    _highlightCurrent() {
        const indices = this._currentIndices();
        // Find which local slot is active
        let localIdx;
        if (this.entries) {
            const entryIdx = this._entryForGlobal(this.currentGlobalIndex);
            localIdx = indices.indexOf(entryIdx);
        } else {
            localIdx = indices.indexOf(this.currentGlobalIndex);
        }
        const n = indices.length;

        this.optionElements.forEach((el, j) => {
            el.classList.toggle('active', j === localIdx);
            // Show variant indicator for multi-variant entries
            if (this.entries && j < indices.length) {
                const ent = this.entries[indices[j]];
                const badge = el.querySelector('.variant-badge');
                if (ent && ent.numVariants > 1) {
                    const offset = (j === localIdx) ? this._currentVariantOffset() : 0;
                    if (badge) {
                        badge.textContent = `${offset + 1}/${ent.numVariants}`;
                    }
                }
            }
        });

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
                    const entryIdx = this.entries
                        ? this._entryForGlobal(this.currentGlobalIndex)
                        : this.currentGlobalIndex;
                    const localIdx = indices.indexOf(entryIdx);
                    this._selectLocalFromUser(localIdx + Math.sign(dragAccum));
                    dragAccum = 0;
                }
            });

            window.addEventListener('mouseup', () => { this.dragging = false; });
        }

        this.wrap.addEventListener('wheel', (e) => {
            e.preventDefault();
            const direction = e.deltaY > 0 ? -1 : 1;

            // Shift+scroll = cycle variants within current mic
            if (e.shiftKey && this.entries) {
                this._cycleVariant(direction);
                return;
            }

            // Normal scroll = cycle mics
            const indices = this._currentIndices();
            const entryIdx = this.entries
                ? this._entryForGlobal(this.currentGlobalIndex)
                : this.currentGlobalIndex;
            const localIdx = indices.indexOf(entryIdx);
            this._selectLocalFromUser(localIdx + direction);
        });
    }

    // Find which group contains the current selection (prefer staying in current group)
    _findGroupForCurrent() {
        const lookupIdx = this.entries
            ? this._entryForGlobal(this.currentGlobalIndex)
            : this.currentGlobalIndex;
        // Stay in current group if it contains this mic
        if (this.groups[this.currentGroupIdx].indices.includes(lookupIdx))
            return this.currentGroupIdx;
        // Otherwise find first matching group
        for (let g = 0; g < this.groups.length; g++) {
            if (this.groups[g].indices.includes(lookupIdx)) return g;
        }
        return 0;
    }

    _readFromBackend() {
        const norm = getParameterNormalized(this.paramId);
        this.currentGlobalIndex = normToSelect(norm, this.maxVal);

        if (this.groups) {
            this.currentGroupIdx = this._findGroupForCurrent();
            this._buildRing();
        }

        this._highlightCurrent();
    }

    _listenToBackend() {
        onParameterChange(this.paramId, () => {
            if (this.dragging) return;
            const norm = getParameterNormalized(this.paramId);
            this.currentGlobalIndex = normToSelect(norm, this.maxVal);

            if (this.groups) {
                const newGroup = this._findGroupForCurrent();
                if (newGroup !== this.currentGroupIdx) {
                    this.currentGroupIdx = newGroup;
                    this._buildRing();
                }
            }

            this._highlightCurrent();
        });
    }

    getIndex() { return this.currentGlobalIndex; }

    setDisabled(disabled) {
        this.wrap.classList.toggle('disabled', disabled);
    }
}
