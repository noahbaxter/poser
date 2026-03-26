// JUCE WebView Bridge - uses official JUCE frontend library
import * as Juce from './juce/index.js';

// All parameter slider states
const sliderStates = {
    mic_select: Juce.getSliderState("mic_select"),
    cab_select: Juce.getSliderState("cab_select"),
    speaker_select: Juce.getSliderState("speaker_select"),
    position_select: Juce.getSliderState("position_select"),
    mic_blend: Juce.getSliderState("mic_blend"),
    cab_blend: Juce.getSliderState("cab_blend"),
    speaker_blend: Juce.getSliderState("speaker_blend"),
    position_blend: Juce.getSliderState("position_blend"),
    master_push: Juce.getSliderState("master_push"),
    output_trim: Juce.getSliderState("output_trim"),
};

export function setParameterNormalized(id, normalizedValue) {
    const state = sliderStates[id];
    if (state) {
        state.setNormalisedValue(normalizedValue);
    }
}

export function getParameterNormalized(id) {
    const state = sliderStates[id];
    return state?.getNormalisedValue() ?? 0;
}

export function getParameterProperties(id) {
    const state = sliderStates[id];
    return state?.properties ?? null;
}

export function onParameterChange(id, callback) {
    const state = sliderStates[id];
    if (state) {
        state.valueChangedEvent.addListener(callback);
    }
}

export function parameterDragStarted(id) {
    const state = sliderStates[id];
    if (state) state.sliderDragStarted();
}

export function parameterDragEnded(id) {
    const state = sliderStates[id];
    if (state) state.sliderDragEnded();
}

export function registerCallback(name, callback) {
    window[name] = callback;
}

export const getNativeFunction = Juce.getNativeFunction;
export { Juce };
