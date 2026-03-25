import { getParameterNormalized, setParameterNormalized, onParameterChange, parameterDragStarted, parameterDragEnded } from './lib/juce-bridge.js';

const gainSlider = document.getElementById('gain-slider');
const gainValue = document.getElementById('gain-value');

function formatGainDb(normalized) {
    if (normalized <= 0) return '-inf dB';
    const db = 20 * Math.log10(normalized * 2);
    return `${db >= 0 ? '+' : ''}${db.toFixed(1)} dB`;
}

function updateDisplay() {
    const norm = getParameterNormalized('gain');
    gainSlider.value = norm;
    gainValue.textContent = formatGainDb(norm);
}

gainSlider.addEventListener('mousedown', () => parameterDragStarted('gain'));
gainSlider.addEventListener('mouseup', () => parameterDragEnded('gain'));
gainSlider.addEventListener('touchstart', () => parameterDragStarted('gain'));
gainSlider.addEventListener('touchend', () => parameterDragEnded('gain'));

gainSlider.addEventListener('input', () => {
    const norm = parseFloat(gainSlider.value);
    setParameterNormalized('gain', norm);
    gainValue.textContent = formatGainDb(norm);
});

onParameterChange('gain', updateDisplay);
updateDisplay();
