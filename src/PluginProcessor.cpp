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
        juce::ParameterID{"mic_select", 1}, "Mic Select", 0, 4, 1));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"cab_select", 1}, "Cab Select", 0, 3, 2));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"speaker_select", 1}, "Speaker Select", 0, 7, 7));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"position_select", 1}, "Position Select", 0, 12, 5));

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"mic_blend", 1}, "Mic Blend",
        juce::NormalisableRange<float>(0.0f, 1.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"cab_blend", 1}, "Cab Blend",
        juce::NormalisableRange<float>(0.0f, 1.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"speaker_blend", 1}, "Speaker Blend",
        juce::NormalisableRange<float>(0.0f, 1.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"position_blend", 1}, "Position Blend",
        juce::NormalisableRange<float>(0.0f, 1.0f, 0.01f), 1.0f));

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"master_push", 1}, "Master Push",
        juce::NormalisableRange<float>(-5.0f, 5.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"output_trim", 1}, "Output Trim",
        juce::NormalisableRange<float>(-24.0f, 24.0f, 0.1f), 0.0f,
        juce::AudioParameterFloatAttributes().withLabel("dB")));

    // Curve shaping: low/high cut on the EQ curve (not the audio)
    // These fade the magnitude curve to 0dB below/above the cutoff frequency
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"curve_low_cut", 1}, "Curve Low Cut",
        juce::NormalisableRange<float>(20.0f, 2000.0f, 1.0f, 0.3f), 20.0f,
        juce::AudioParameterFloatAttributes().withLabel("Hz")));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"curve_high_cut", 1}, "Curve High Cut",
        juce::NormalisableRange<float>(1000.0f, 20000.0f, 1.0f, 0.3f), 20000.0f,
        juce::AudioParameterFloatAttributes().withLabel("Hz")));

    // Mode: 0 = both (boost + cut), 1 = boost only, 2 = cut only
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"curve_mode", 1}, "Curve Mode", 0, 2, 0));

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

    // Init AudioFFT
    fft.init(static_cast<size_t>(fftSize));

    // Sqrt-Hann window (analysis * synthesis = Hann, which sums to 1.0 at 50% overlap)
    for (int i = 0; i < fftSize; ++i)
    {
        float hann = 0.5f * (1.0f - std::cos(2.0f * juce::MathConstants<float>::pi
                                               * static_cast<float>(i) / static_cast<float>(fftSize)));
        window[i] = std::sqrt(hann);
    }

    // Clear buffers
    std::memset(inputFifo, 0, sizeof(inputFifo));
    std::memset(outputAccum, 0, sizeof(outputAccum));
    std::memset(fftRe, 0, sizeof(fftRe));
    std::memset(fftIm, 0, sizeof(fftIm));
    std::memset(fftOut, 0, sizeof(fftOut));
    fifoPos = 0;
    outReadPos = 0;

    // Init magnitude response to flat
    for (int i = 0; i < complexSize; ++i)
        magnitudeResponse[i] = 1.0f;

    // Bin mapping: linear FFT bins → nearest CurveData log-spaced bin
    for (int i = 0; i < complexSize; ++i)
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
    float masterPush    = apvts.getRawParameterValue("master_push")->load();
    float lowCutHz      = apvts.getRawParameterValue("curve_low_cut")->load();
    float highCutHz     = apvts.getRawParameterValue("curve_high_cut")->load();
    int   curveMode     = static_cast<int>(apvts.getRawParameterValue("curve_mode")->load());


    for (int i = 0; i < complexSize; ++i)
    {
        int cb = binMapping[i];
        float totalDb = 0.0f;
        if (micBlend > 0.0f && micSel >= 0 && micSel < ::CurveData::kNumMics)
            totalDb += ::CurveData::kMics[micSel].data[cb] * micBlend;
        if (cabBlend > 0.0f && cabSel >= 0 && cabSel < ::CurveData::kNumCabs)
            totalDb += ::CurveData::kCabs[cabSel].data[cb] * cabBlend;
        if (speakerBlend > 0.0f && speakerSel >= 0 && speakerSel < ::CurveData::kNumSpeakers)
            totalDb += ::CurveData::kSpeakers[speakerSel].data[cb] * speakerBlend;
        if (positionBlend > 0.0f && positionSel >= 0 && positionSel < ::CurveData::kNumPositions)
            totalDb += ::CurveData::kPositions[positionSel].data[cb] * positionBlend;

        // Master push scales the entire composite curve
        totalDb *= masterPush;

        // Curve mode: boost only / cut only
        if (curveMode == 1 && totalDb < 0.0f) totalDb = 0.0f;  // boost only
        if (curveMode == 2 && totalDb > 0.0f) totalDb = 0.0f;  // cut only

        // Low/high cut: fade the curve to 0dB outside the frequency range
        // Uses ~6dB/octave rolloff (one octave of fade)
        float fftFreq = static_cast<float>(i) * static_cast<float>(currentSampleRate) / static_cast<float>(fftSize);

        if (fftFreq < lowCutHz && lowCutHz > 20.0f)
        {
            // Fade from 0 at lowCutHz/2 to 1 at lowCutHz (one octave below)
            float fadeStart = lowCutHz * 0.5f;
            if (fftFreq <= fadeStart)
                totalDb = 0.0f;
            else
                totalDb *= (fftFreq - fadeStart) / (lowCutHz - fadeStart);
        }

        if (fftFreq > highCutHz && highCutHz < 20000.0f)
        {
            // Fade from 1 at highCutHz to 0 at highCutHz*2 (one octave above)
            float fadeEnd = highCutHz * 2.0f;
            if (fftFreq >= fadeEnd)
                totalDb = 0.0f;
            else
                totalDb *= 1.0f - (fftFreq - highCutHz) / (fadeEnd - highCutHz);
        }

        magnitudeResponse[i] = std::pow(10.0f, totalDb / 20.0f);
    }

    // Auto-gain compensation: normalize so average gain ≈ 1.0
    // This prevents volume spikes when switching presets
    float avgGain = 0.0f;
    for (int i = 0; i < complexSize; ++i)
        avgGain += magnitudeResponse[i];
    avgGain /= static_cast<float>(complexSize);

    if (avgGain > 0.001f)
    {
        float compensation = 1.0f / avgGain;
        for (int i = 0; i < complexSize; ++i)
            magnitudeResponse[i] *= compensation;
    }

    needsResponseUpdate = false;
}

void PoserProcessor::processFFTFrame(int channel)
{
    // Copy input with Hann window into temp buffer
    float windowed[fftSize];
    for (int i = 0; i < fftSize; ++i)
        windowed[i] = inputFifo[channel][i] * window[i];

    // Forward FFT (split-complex, all scaling handled by AudioFFT)
    fft.fft(windowed, fftRe, fftIm);

    // Apply magnitude response (multiply real and imag by gain)
    for (int i = 0; i < complexSize; ++i)
    {
        fftRe[i] *= magnitudeResponse[i];
        fftIm[i] *= magnitudeResponse[i];
    }

    // Inverse FFT
    fft.ifft(fftOut, fftRe, fftIm);

    // Apply synthesis window (sqrt-Hann) and overlap-add
    // sqrt-Hann * sqrt-Hann = Hann, sum of Hann at 50% overlap = 1.0 → perfect reconstruction
    int accumSize = fftSize * 2;
    for (int i = 0; i < fftSize; ++i)
    {
        int idx = (outReadPos + i) % accumSize;
        outputAccum[channel][idx] += fftOut[i] * window[i];
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
        float params[13] = {
            apvts.getRawParameterValue("mic_select")->load(),
            apvts.getRawParameterValue("cab_select")->load(),
            apvts.getRawParameterValue("speaker_select")->load(),
            apvts.getRawParameterValue("position_select")->load(),
            apvts.getRawParameterValue("mic_blend")->load(),
            apvts.getRawParameterValue("cab_blend")->load(),
            apvts.getRawParameterValue("speaker_blend")->load(),
            apvts.getRawParameterValue("position_blend")->load(),
            apvts.getRawParameterValue("master_push")->load(),
            apvts.getRawParameterValue("output_trim")->load(),
            apvts.getRawParameterValue("curve_low_cut")->load(),
            apvts.getRawParameterValue("curve_high_cut")->load(),
            apvts.getRawParameterValue("curve_mode")->load(),
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
        // Push input into FIFO
        for (int ch = 0; ch < numChannels; ++ch)
            inputFifo[ch][fifoPos] = buffer.getSample(ch, sample);

        // Read from output accumulator
        float trimDb = getSmoothedParam("output_trim");
        float trimGain = juce::Decibels::decibelsToGain(trimDb);

        int readIdx = outReadPos;
        for (int ch = 0; ch < numChannels; ++ch)
        {
            float out = outputAccum[ch][readIdx] * trimGain;
            outputAccum[ch][readIdx] = 0.0f;
            if (!std::isfinite(out)) out = 0.0f;
            buffer.setSample(ch, sample, out);
        }

        outReadPos = (outReadPos + 1) % accumSize;
        ++fifoPos;

        // When FIFO is full, process a frame
        if (fifoPos >= fftSize)
        {
            for (int ch = 0; ch < numChannels; ++ch)
                processFFTFrame(ch);

            // Shift: keep second half for 50% overlap
            for (int ch = 0; ch < numChannels; ++ch)
                std::memmove(inputFifo[ch], inputFifo[ch] + hopSize, static_cast<size_t>(hopSize) * sizeof(float));

            fifoPos = hopSize;
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
