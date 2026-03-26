#pragma once

#include <JuceHeader.h>
#include "PluginProcessor.h"

class PoserEditor : public juce::AudioProcessorEditor, private juce::Timer
{
public:
    explicit PoserEditor(PoserProcessor&);
    ~PoserEditor() override;

    void paint(juce::Graphics&) override;
    void resized() override;

private:
    void timerCallback() override;
    std::optional<juce::WebBrowserComponent::Resource> getResource(const juce::String& url);
    void pushVersionOnce();

    PoserProcessor& audioProcessor;
    bool versionPushed = false;
    int timerTicks = 0;

    // WebView relay objects (bridge between WebView and parameters)
    juce::WebSliderRelay gainRelay;

    // WebView component (must be declared after relays)
    juce::WebBrowserComponent webView;

    // Parameter attachments (connect relays to APVTS parameters)
    juce::WebSliderParameterAttachment gainAttachment;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PoserEditor)
};
