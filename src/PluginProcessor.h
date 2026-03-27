#pragma once

#include <JuceHeader.h>
#include <unordered_map>
#include "dsp/EqProcessor.h"

class PoserProcessor : public juce::AudioProcessor
{
public:
    PoserProcessor();
    ~PoserProcessor() override;

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

private:
    juce::AudioProcessorValueTreeState apvts;
    double currentSampleRate = 44100.0;

    static juce::AudioProcessorValueTreeState::ParameterLayout createParameterLayout();

    // DSP
    EqProcessor eq;
    bool needsResponseUpdate = true;
    float prevParams[14] = {};

    void updateEqIfNeeded();

    // Output trim smoothing
    juce::SmoothedValue<float, juce::ValueSmoothingTypes::Linear> trimSmoother;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PoserProcessor)
};
