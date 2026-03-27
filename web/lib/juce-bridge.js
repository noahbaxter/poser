// JUCE WebView Bridge — dynamic parameter state management
import * as Juce from './juce/index.js';

const sliderStates = {};

function getOrCreateState(id) {
    if (!sliderStates[id])
        sliderStates[id] = Juce.getSliderState(id);
    return sliderStates[id];
}

export function setParameterNormalized(id, normalizedValue) {
    getOrCreateState(id).setNormalisedValue(normalizedValue);
}

export function getParameterNormalized(id) {
    return getOrCreateState(id)?.getNormalisedValue() ?? 0;
}

export function getParameterScaled(id) {
    return getOrCreateState(id)?.getScaledValue() ?? 0;
}

export function getParameterProperties(id) {
    return getOrCreateState(id)?.properties ?? null;
}

export function onParameterChange(id, callback) {
    getOrCreateState(id).valueChangedEvent.addListener(callback);
}

export function parameterDragStarted(id) {
    getOrCreateState(id).sliderDragStarted();
}

export function parameterDragEnded(id) {
    getOrCreateState(id).sliderDragEnded();
}

export function registerCallback(name, callback) {
    window[name] = callback;
}

export const getNativeFunction = Juce.getNativeFunction;
export { Juce };
