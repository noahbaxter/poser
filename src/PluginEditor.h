#pragma once

#include <JuceHeader.h>
#include "PluginProcessor.h"

class AudioPluginEditor : public juce::AudioProcessorEditor, private juce::Timer
{
public:
    explicit AudioPluginEditor(AudioPluginProcessor&);
    ~AudioPluginEditor() override;

    void paint(juce::Graphics&) override;
    void resized() override;

private:
    void timerCallback() override;
    std::optional<juce::WebBrowserComponent::Resource> getResource(const juce::String& url);
    void pushVersionOnce();

    AudioPluginProcessor& audioProcessor;
    bool versionPushed = false;
    int timerTicks = 0;

    // WebView relay objects (bridge between WebView and parameters)
    juce::WebSliderRelay gainRelay;

    // WebView component (must be declared after relays)
    juce::WebBrowserComponent webView;

    // Parameter attachments (connect relays to APVTS parameters)
    juce::WebSliderParameterAttachment gainAttachment;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AudioPluginEditor)
};
