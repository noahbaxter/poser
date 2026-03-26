#pragma once

#include <JuceHeader.h>
#include <unordered_map>
#include "AudioFFT.h"

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

protected:
    void enableSmoothing(const juce::String& paramId, double smoothingTimeSeconds = 0.02);
    float getSmoothedParam(const juce::String& paramId);

private:
    juce::AudioProcessorValueTreeState apvts;
    std::unordered_map<juce::String, juce::SmoothedValue<float, juce::ValueSmoothingTypes::Linear>> smoothers;
    double currentSampleRate = 44100.0;

    static juce::AudioProcessorValueTreeState::ParameterLayout createParameterLayout();

    // FFT with overlap-add (50% overlap, Hann window)
    static constexpr int fftSize = 1024;
    static constexpr int hopSize = fftSize / 2;
    static constexpr int complexSize = fftSize / 2 + 1;
    audiofft::AudioFFT fft;

    // Hann window
    float window[fftSize] = {};

    // Per-channel input FIFO
    float inputFifo[2][fftSize] = {};

    // Per-channel output accumulator (2x for overlap)
    float outputAccum[2][fftSize * 2] = {};

    int fifoPos = 0;
    int outReadPos = 0;

    // Split-complex FFT buffers
    float fftRe[complexSize] = {};
    float fftIm[complexSize] = {};
    float fftOut[fftSize] = {};

    // Magnitude response
    float magnitudeResponse[complexSize] = {};
    bool needsResponseUpdate = true;

    // Bin mapping
    int binMapping[complexSize] = {};

    // Parameter change detection
    float prevParams[13] = {};

    void recomputeMagnitudeResponse();
    void processFFTFrame(int channel);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PoserProcessor)
};
