#include "PluginProcessor.h"
#include "CurveData.h"

PoserProcessor::PoserProcessor()
#ifndef JucePlugin_PreferredChannelConfigurations
    : AudioProcessor(BusesProperties()
#if ! JucePlugin_IsMidiEffect
#if ! JucePlugin_IsSynth
                         .withInput("Input", juce::AudioChannelSet::stereo(), true)
#endif
                         .withOutput("Output", juce::AudioChannelSet::stereo(), true)
#endif
                         ),
      apvts(*this, nullptr, "Parameters", createParameterLayout())
#endif
{
}

PoserProcessor::~PoserProcessor() {}

juce::AudioProcessorValueTreeState::ParameterLayout PoserProcessor::createParameterLayout()
{
    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;

    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"mic_select", 1}, "Mic Select", 0, 5, 5));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"cab_select", 1}, "Cab Select", 0, 3, 2));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"speaker_select", 1}, "Speaker Select", 0, 7, 7));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"position_select", 1}, "Position Select", 0, 12, 5));

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"mic_blend", 1}, "Mic Blend",
        juce::NormalisableRange<float>(-5.0f, 5.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"cab_blend", 1}, "Cab Blend",
        juce::NormalisableRange<float>(-5.0f, 5.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"speaker_blend", 1}, "Speaker Blend",
        juce::NormalisableRange<float>(-5.0f, 5.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"position_blend", 1}, "Position Blend",
        juce::NormalisableRange<float>(-5.0f, 5.0f, 0.01f), 1.0f));

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"dry_wet", 1}, "Dry/Wet",
        juce::NormalisableRange<float>(0.0f, 1.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"output_trim", 1}, "Output Trim",
        juce::NormalisableRange<float>(-24.0f, 24.0f, 0.1f), 0.0f,
        juce::AudioParameterFloatAttributes().withLabel("dB")));

    return {params.begin(), params.end()};
}

void PoserProcessor::enableSmoothing(const juce::String& paramId, double smoothingTimeSeconds)
{
    smoothers[paramId].reset(currentSampleRate, smoothingTimeSeconds);
}

float PoserProcessor::getSmoothedParam(const juce::String& paramId)
{
    auto* param = apvts.getRawParameterValue(paramId);
    if (param == nullptr) return 0.0f;
    auto& smoother = smoothers[paramId];
    smoother.setTargetValue(param->load());
    return smoother.getNextValue();
}

const juce::String PoserProcessor::getName() const { return JucePlugin_Name; }
bool PoserProcessor::acceptsMidi() const { return false; }
bool PoserProcessor::producesMidi() const { return false; }
bool PoserProcessor::isMidiEffect() const { return false; }
double PoserProcessor::getTailLengthSeconds() const { return 0.0; }
int PoserProcessor::getNumPrograms() { return 1; }
int PoserProcessor::getCurrentProgram() { return 0; }
void PoserProcessor::setCurrentProgram(int) {}
const juce::String PoserProcessor::getProgramName(int) { return {}; }
void PoserProcessor::changeProgramName(int, const juce::String&) {}

void PoserProcessor::prepareToPlay(double sampleRate, int samplesPerBlock)
{
    juce::ignoreUnused(samplesPerBlock);
    currentSampleRate = sampleRate;

    // Hann window
    for (int i = 0; i < fftSize; ++i)
        window[i] = 0.5f * (1.0f - std::cos(2.0f * juce::MathConstants<float>::pi
                                              * static_cast<float>(i) / static_cast<float>(fftSize)));

    // Clear buffers
    std::memset(inputFifo, 0, sizeof(inputFifo));
    std::memset(outputAccum, 0, sizeof(outputAccum));
    fifoPos = 0;
    outReadPos = 0;

    // Init magnitude response to flat
    for (int i = 0; i < fftSize / 2 + 1; ++i)
        magnitudeResponse[i] = 1.0f;

    // Bin mapping
    int numBins = fftSize / 2 + 1;
    for (int i = 0; i < numBins; ++i)
    {
        float fftFreq = static_cast<float>(i) * static_cast<float>(sampleRate) / static_cast<float>(fftSize);
        int bestIdx = 0;
        float bestDist = std::abs(fftFreq - ::CurveData::kFrequencies[0]);
        for (int j = 1; j < ::CurveData::kNumBins; ++j)
        {
            float dist = std::abs(fftFreq - ::CurveData::kFrequencies[static_cast<size_t>(j)]);
            if (dist < bestDist) { bestDist = dist; bestIdx = j; }
        }
        binMapping[i] = bestIdx;
    }

    needsResponseUpdate = true;
    setLatencySamples(fftSize);
    enableSmoothing("output_trim", 0.02);
}

void PoserProcessor::releaseResources() {}

#ifndef JucePlugin_PreferredChannelConfigurations
bool PoserProcessor::isBusesLayoutSupported(const juce::AudioProcessor::BusesLayout& layouts) const
{
    if (layouts.getMainOutputChannelSet() != juce::AudioChannelSet::mono() &&
        layouts.getMainOutputChannelSet() != juce::AudioChannelSet::stereo())
        return false;
#if ! JucePlugin_IsSynth
    if (layouts.getMainOutputChannelSet() != layouts.getMainInputChannelSet())
        return false;
#endif
    return true;
}
#endif

void PoserProcessor::recomputeMagnitudeResponse()
{
    int micSel      = static_cast<int>(apvts.getRawParameterValue("mic_select")->load());
    int cabSel      = static_cast<int>(apvts.getRawParameterValue("cab_select")->load());
    int speakerSel  = static_cast<int>(apvts.getRawParameterValue("speaker_select")->load());
    int positionSel = static_cast<int>(apvts.getRawParameterValue("position_select")->load());
    float micBlend      = apvts.getRawParameterValue("mic_blend")->load();
    float cabBlend      = apvts.getRawParameterValue("cab_blend")->load();
    float speakerBlend  = apvts.getRawParameterValue("speaker_blend")->load();
    float positionBlend = apvts.getRawParameterValue("position_blend")->load();
    float dryWet        = apvts.getRawParameterValue("dry_wet")->load();

    int numBins = fftSize / 2 + 1;
    for (int i = 0; i < numBins; ++i)
    {
        int cb = binMapping[i];
        float totalDb = 0.0f;
        if (micBlend != 0.0f && micSel >= 0 && micSel < ::CurveData::kNumMics)
            totalDb += ::CurveData::kMics[micSel].data[cb] * micBlend;
        if (cabBlend != 0.0f && cabSel >= 0 && cabSel < ::CurveData::kNumCabs)
            totalDb += ::CurveData::kCabs[cabSel].data[cb] * cabBlend;
        if (speakerBlend != 0.0f && speakerSel >= 0 && speakerSel < ::CurveData::kNumSpeakers)
            totalDb += ::CurveData::kSpeakers[speakerSel].data[cb] * speakerBlend;
        if (positionBlend != 0.0f && positionSel >= 0 && positionSel < ::CurveData::kNumPositions)
            totalDb += ::CurveData::kPositions[positionSel].data[cb] * positionBlend;
        totalDb *= dryWet;
        magnitudeResponse[i] = std::pow(10.0f, totalDb / 20.0f);
    }
    needsResponseUpdate = false;
}

void PoserProcessor::processFFTFrame(int channel)
{
    // Copy input FIFO into work buffer, apply window
    for (int i = 0; i < fftSize; ++i)
        fftWork[i] = inputFifo[channel][i] * window[i];

    // Zero imaginary part
    for (int i = fftSize; i < fftSize * 2; ++i)
        fftWork[i] = 0.0f;

    // Forward FFT
    fft.performRealOnlyForwardTransform(fftWork);

    // Apply magnitude response
    int numBins = fftSize / 2 + 1;
    for (int i = 0; i < numBins; ++i)
    {
        fftWork[i * 2]     *= magnitudeResponse[i];
        fftWork[i * 2 + 1] *= magnitudeResponse[i];
    }

    // Inverse FFT
    fft.performRealOnlyInverseTransform(fftWork);

    // Overlap-add into output accumulator (no synthesis window needed)
    // Hann analysis window with 50% overlap sums to exactly 1.0 → perfect reconstruction
    for (int i = 0; i < fftSize; ++i)
    {
        int idx = (outReadPos + i) % (fftSize * 2);
        outputAccum[channel][idx] += fftWork[i];
    }
}

void PoserProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
{
    juce::ignoreUnused(midiMessages);
    juce::ScopedNoDenormals noDenormals;

    auto totalNumInputChannels = getTotalNumInputChannels();
    auto totalNumOutputChannels = getTotalNumOutputChannels();

    for (auto i = totalNumInputChannels; i < totalNumOutputChannels; ++i)
        buffer.clear(i, 0, buffer.getNumSamples());

    int numChannels = juce::jmin(totalNumInputChannels, 2);
    int numSamples = buffer.getNumSamples();

#if JUCE_DEBUG
    if (wrapperType == wrapperType_Standalone)
    {
        static juce::Random rng;
        float noiseGain = juce::Decibels::decibelsToGain(-12.0f);
        for (int ch = 0; ch < numChannels; ++ch)
        {
            auto* data = buffer.getWritePointer(ch);
            for (int i = 0; i < numSamples; ++i)
                data[i] = (rng.nextFloat() * 2.0f - 1.0f) * noiseGain;
        }
    }
#endif

    // Parameter change detection
    {
        float params[10] = {
            apvts.getRawParameterValue("mic_select")->load(),
            apvts.getRawParameterValue("cab_select")->load(),
            apvts.getRawParameterValue("speaker_select")->load(),
            apvts.getRawParameterValue("position_select")->load(),
            apvts.getRawParameterValue("mic_blend")->load(),
            apvts.getRawParameterValue("cab_blend")->load(),
            apvts.getRawParameterValue("speaker_blend")->load(),
            apvts.getRawParameterValue("position_blend")->load(),
            apvts.getRawParameterValue("dry_wet")->load(),
            apvts.getRawParameterValue("output_trim")->load(),
        };
        if (needsResponseUpdate || std::memcmp(params, prevParams, sizeof(params)) != 0)
        {
            std::memcpy(prevParams, params, sizeof(params));
            recomputeMagnitudeResponse();
        }
    }

    int accumSize = fftSize * 2;

    for (int sample = 0; sample < numSamples; ++sample)
    {
        // Push input sample into FIFO for each channel
        for (int ch = 0; ch < numChannels; ++ch)
            inputFifo[ch][fifoPos] = buffer.getSample(ch, sample);

        // Read from output accumulator (delayed by fftSize for latency compensation)
        float trimDb = getSmoothedParam("output_trim");
        float trimGain = juce::Decibels::decibelsToGain(trimDb);

        int readIdx = outReadPos;
        for (int ch = 0; ch < numChannels; ++ch)
        {
            float out = outputAccum[ch][readIdx] * trimGain;
            outputAccum[ch][readIdx] = 0.0f;  // Clear after reading for next overlap cycle
            if (!std::isfinite(out)) out = 0.0f;
            buffer.setSample(ch, sample, out);
        }

        outReadPos = (outReadPos + 1) % accumSize;
        ++fifoPos;

        // When we've collected hopSize new samples, process a frame
        if (fifoPos >= fftSize)
        {
            for (int ch = 0; ch < numChannels; ++ch)
                processFFTFrame(ch);

            // Shift the input FIFO: move the second half to the first half (50% overlap)
            for (int ch = 0; ch < numChannels; ++ch)
                std::memmove(inputFifo[ch], inputFifo[ch] + hopSize, static_cast<size_t>(hopSize) * sizeof(float));

            fifoPos = hopSize;  // Next fill starts from the middle
        }
    }
}

bool PoserProcessor::hasEditor() const { return true; }

void PoserProcessor::getStateInformation(juce::MemoryBlock& destData)
{
    auto state = apvts.copyState();
    std::unique_ptr<juce::XmlElement> xml(state.createXml());
    copyXmlToBinary(*xml, destData);
}

void PoserProcessor::setStateInformation(const void* data, int sizeInBytes)
{
    std::unique_ptr<juce::XmlElement> xml(getXmlFromBinary(data, sizeInBytes));
    if (xml != nullptr && xml->hasTagName(apvts.state.getType()))
        apvts.replaceState(juce::ValueTree::fromXml(*xml));
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new PoserProcessor();
}
