// Toggle Component
// Simple on/off button bound to a JUCE boolean parameter.

import {
    getParameterNormalized,
    setParameterNormalized,
    onParameterChange,
    parameterDragStarted,
    parameterDragEnded,
} from '../../lib/juce-bridge.js';

export class Toggle {
    constructor(container, { param, label }) {
        this.param = param;

        this.el = document.createElement('div');
        this.el.className = 'toggle-btn';
        if (label) {
            this.el.textContent = label;
        }

        this.el.addEventListener('click', () => {
            const current = getParameterNormalized(this.param);
            const next = current >= 0.5 ? 0.0 : 1.0;
            parameterDragStarted(this.param);
            setParameterNormalized(this.param, next);
            parameterDragEnded(this.param);
            this.el.classList.toggle('active', next >= 0.5);
        });

        onParameterChange(this.param, () => {
            this.el.classList.toggle('active', getParameterNormalized(this.param) >= 0.5);
        });

        // Read initial state
        this.el.classList.toggle('active', getParameterNormalized(this.param) >= 0.5);

        container.appendChild(this.el);
    }
}
