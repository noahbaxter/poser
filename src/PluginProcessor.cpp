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

// --- Parameters ---

static int findCurveIndex(const CurveData::Curve* curves, int count, const char* name)
{
    for (int i = 0; i < count; ++i)
        if (juce::CharacterFunctions::compareIgnoreCase(
                juce::CharPointer_ASCII(curves[i].name),
                juce::CharPointer_ASCII(name)) == 0)
            return i;
    return 0;
}

juce::AudioProcessorValueTreeState::ParameterLayout PoserProcessor::createParameterLayout()
{
    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;

    // Component selectors (max derived from CurveData.h array sizes)
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"mic_select", 1}, "Mic Select", 0, ::CurveData::kNumMics - 1,
        findCurveIndex(::CurveData::kMics, ::CurveData::kNumMics, "SM57")));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"cab_select", 1}, "Cab Select", 0, ::CurveData::kNumCabs - 1, 0));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"speaker_select", 1}, "Speaker Select", 0, ::CurveData::kNumSpeakers - 1, 0));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"position_select", 1}, "Position Select", 0, ::CurveData::kNumPositions - 1, 0));

    // Component blends (-100% to +100%, negative inverts the curve)
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"mic_blend", 1}, "Mic Blend",
        juce::NormalisableRange<float>(-1.0f, 1.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"cab_blend", 1}, "Cab Blend",
        juce::NormalisableRange<float>(-1.0f, 1.0f, 0.01f), 0.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"speaker_blend", 1}, "Speaker Blend",
        juce::NormalisableRange<float>(-1.0f, 1.0f, 0.01f), 0.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"position_blend", 1}, "Position Blend",
        juce::NormalisableRange<float>(-1.0f, 1.0f, 0.01f), 0.0f));

    // Master controls
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"master_push", 1}, "Scale",
        juce::NormalisableRange<float>(0.0f, 5.0f, 0.01f), 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"output_trim", 1}, "Output Trim",
        juce::NormalisableRange<float>(-24.0f, 24.0f, 0.1f), 0.0f,
        juce::AudioParameterFloatAttributes().withLabel("dB")));

    // Curve shaping
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"curve_low_cut", 1}, "Curve Low Cut",
        juce::NormalisableRange<float>(20.0f, 1000.0f, 1.0f, 0.3f), 20.0f,
        juce::AudioParameterFloatAttributes().withLabel("Hz")));
    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"curve_high_cut", 1}, "Curve High Cut",
        juce::NormalisableRange<float>(2000.0f, 20000.0f, 1.0f, 0.3f), 20000.0f,
        juce::AudioParameterFloatAttributes().withLabel("Hz")));
    params.push_back(std::make_unique<juce::AudioParameterInt>(
        juce::ParameterID{"curve_mode", 1}, "Curve Mode", 0, 2, 0));
    params.push_back(std::make_unique<juce::AudioParameterBool>(
        juce::ParameterID{"cab_filter", 1}, "Cab Filter", false));
    params.push_back(std::make_unique<juce::AudioParameterBool>(
        juce::ParameterID{"gain_comp", 1}, "Gain Comp", true));

    return {params.begin(), params.end()};
}

// --- Lifecycle ---

void PoserProcessor::prepareToPlay(double sampleRate, int samplesPerBlock)
{
    juce::ignoreUnused(samplesPerBlock);
    currentSampleRate = sampleRate;
    eq.prepare(sampleRate);
    trimSmoother.reset(sampleRate, 0.02);
    needsResponseUpdate = true;
    setLatencySamples(eq.getLatencySamples());
}

void PoserProcessor::releaseResources() {}

// --- Processing ---

void PoserProcessor::updateEqIfNeeded()
{
    float params[15] = {
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
        apvts.getRawParameterValue("cab_filter")->load(),
        apvts.getRawParameterValue("gain_comp")->load(),
    };

    if (!needsResponseUpdate && std::memcmp(params, prevParams, sizeof(params)) == 0)
        return;

    std::memcpy(prevParams, params, sizeof(params));
    needsResponseUpdate = false;

    eq.updateResponse({
        .micSel      = static_cast<int>(params[0]),
        .cabSel      = static_cast<int>(params[1]),
        .speakerSel  = static_cast<int>(params[2]),
        .positionSel = static_cast<int>(params[3]),
        .micBlend    = params[4],
        .cabBlend    = params[5],
        .speakerBlend = params[6],
        .positionBlend = params[7],
        .masterPush  = params[8],
        .lowCutHz    = params[10],
        .highCutHz   = params[11],
        .curveMode   = static_cast<int>(params[12]),
        .cabFilter   = params[13] >= 0.5f,
        .gainComp    = params[14] >= 0.5f,
        .sampleRate  = currentSampleRate,
    });
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
        float noiseGain = juce::Decibels::decibelsToGain(-27.0f);
        for (int ch = 0; ch < numChannels; ++ch)
        {
            auto* data = buffer.getWritePointer(ch);
            for (int i = 0; i < numSamples; ++i)
                data[i] = (rng.nextFloat() * 2.0f - 1.0f) * noiseGain;
        }
    }
#endif

    updateEqIfNeeded();

    float trimDb = apvts.getRawParameterValue("output_trim")->load();
    trimSmoother.setTargetValue(juce::Decibels::decibelsToGain(trimDb));

    for (int sample = 0; sample < numSamples; ++sample)
    {
        float trim = trimSmoother.getNextValue();

        for (int ch = 0; ch < numChannels; ++ch)
        {
            float in = buffer.getSample(ch, sample);
            float out = eq.processSample(ch, in) * trim;
            buffer.setSample(ch, sample, out);
        }

        eq.advance(numChannels);
    }
}

// --- JUCE boilerplate ---

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
bool PoserProcessor::hasEditor() const { return true; }

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
