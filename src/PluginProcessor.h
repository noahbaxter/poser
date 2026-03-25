#pragma once

#include <JuceHeader.h>
#include <unordered_map>

class AudioPluginProcessor : public juce::AudioProcessor
{
public:
    AudioPluginProcessor();
    ~AudioPluginProcessor() override;

    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override;

    const juce::String getName() const override;

    bool acceptsMidi() const override;
    bool producesMidi() const override;
    bool isMidiEffect() const override;
    double getTailLengthSeconds() const override;

    int getNumPrograms() override;
    int getCurrentProgram() override;
    void setCurrentProgram(int index) override;
    const juce::String getProgramName(int index) override;
    void changeProgramName(int index, const juce::String& newName) override;

    void getStateInformation(juce::MemoryBlock& destData) override;
    void setStateInformation(const void* data, int sizeInBytes) override;

#ifndef JucePlugin_PreferredChannelConfigurations
    bool isBusesLayoutSupported(const juce::AudioProcessor::BusesLayout& layouts) const override;
#endif

    juce::AudioProcessorValueTreeState& getAPVTS() { return apvts; }

protected:
    // Call in prepareToPlay to enable smoothing for a parameter
    void enableSmoothing(const juce::String& paramId, double smoothingTimeSeconds = 0.02);

    // Call per-sample in processBlock to get smoothed value
    float getSmoothedParam(const juce::String& paramId);

private:
    juce::AudioProcessorValueTreeState apvts;
    std::unordered_map<juce::String, juce::SmoothedValue<float, juce::ValueSmoothingTypes::Linear>> smoothers;
    double currentSampleRate = 44100.0;

    static juce::AudioProcessorValueTreeState::ParameterLayout createParameterLayout();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AudioPluginProcessor)
};
