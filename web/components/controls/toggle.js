// Toggle Component
// On/off button with horizontal strip indicator, bound to a JUCE boolean parameter.

import {
    getParameterNormalized,
    setParameterNormalized,
    onParameterChange,
    parameterDragStarted,
    parameterDragEnded,
} from '../../lib/juce-bridge.js';

export class Toggle {
    constructor(container, { param, title }) {
        this.param = param;

        this.el = document.createElement('div');
        this.el.className = 'toggle-btn';
        if (title) this.el.title = title;

        // Horizontal strip indicator
        this.strip = document.createElement('div');
        this.strip.className = 'toggle-strip';
        this.el.appendChild(this.strip);

        // ON/OFF text
        this.text = document.createElement('div');
        this.text.className = 'toggle-text';
        this.el.appendChild(this.text);

        this.el.addEventListener('click', () => {
            const current = getParameterNormalized(this.param);
            const next = current >= 0.5 ? 0.0 : 1.0;
            parameterDragStarted(this.param);
            setParameterNormalized(this.param, next);
            parameterDragEnded(this.param);
            this._update(next >= 0.5);
        });

        onParameterChange(this.param, () => {
            this._update(getParameterNormalized(this.param) >= 0.5);
        });

        this._update(getParameterNormalized(this.param) >= 0.5);
        container.appendChild(this.el);
    }

    _update(active) {
        this.el.classList.toggle('active', active);
        this.text.textContent = active ? 'ON' : 'OFF';
    }
}
