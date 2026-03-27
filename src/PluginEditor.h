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
    void pushInitData();

    PoserProcessor& audioProcessor;
    bool initDataPushed = false;
    int timerTicks = 0;

    // WebView relay objects — one per parameter
    juce::WebSliderRelay micSelectRelay;
    juce::WebSliderRelay cabSelectRelay;
    juce::WebSliderRelay speakerSelectRelay;
    juce::WebSliderRelay positionSelectRelay;
    juce::WebSliderRelay micBlendRelay;
    juce::WebSliderRelay cabBlendRelay;
    juce::WebSliderRelay speakerBlendRelay;
    juce::WebSliderRelay positionBlendRelay;
    juce::WebSliderRelay masterPushRelay;
    juce::WebSliderRelay outputTrimRelay;
    juce::WebSliderRelay curveLowCutRelay;
    juce::WebSliderRelay curveHighCutRelay;
    juce::WebSliderRelay curveModeRelay;
    juce::WebSliderRelay cabLpfRelay;

    // WebView component (must be after relays)
    juce::WebBrowserComponent webView;

    // Parameter attachments
    juce::WebSliderParameterAttachment micSelectAttach;
    juce::WebSliderParameterAttachment cabSelectAttach;
    juce::WebSliderParameterAttachment speakerSelectAttach;
    juce::WebSliderParameterAttachment positionSelectAttach;
    juce::WebSliderParameterAttachment micBlendAttach;
    juce::WebSliderParameterAttachment cabBlendAttach;
    juce::WebSliderParameterAttachment speakerBlendAttach;
    juce::WebSliderParameterAttachment positionBlendAttach;
    juce::WebSliderParameterAttachment masterPushAttach;
    juce::WebSliderParameterAttachment outputTrimAttach;
    juce::WebSliderParameterAttachment curveLowCutAttach;
    juce::WebSliderParameterAttachment curveHighCutAttach;
    juce::WebSliderParameterAttachment curveModeAttach;
    juce::WebSliderParameterAttachment cabLpfAttach;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PoserEditor)
};
