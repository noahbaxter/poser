#include "PluginProcessor.h"

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

PoserProcessor::~PoserProcessor()
{
}

juce::AudioProcessorValueTreeState::ParameterLayout PoserProcessor::createParameterLayout()
{
    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID{"gain", 1},
        "Gain",
        juce::NormalisableRange<float>(-60.0f, 12.0f, 0.1f),
        0.0f,
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
    if (param == nullptr)
        return 0.0f;

    auto& smoother = smoothers[paramId];
    smoother.setTargetValue(param->load());
    return smoother.getNextValue();
}

const juce::String PoserProcessor::getName() const
{
    return JucePlugin_Name;
}

bool PoserProcessor::acceptsMidi() const
{
#if JucePlugin_WantsMidiInput
    return true;
#else
    return false;
#endif
}

bool PoserProcessor::producesMidi() const
{
#if JucePlugin_ProducesMidiOutput
    return true;
#else
    return false;
#endif
}

bool PoserProcessor::isMidiEffect() const
{
#if JucePlugin_IsMidiEffect
    return true;
#else
    return false;
#endif
}

double PoserProcessor::getTailLengthSeconds() const
{
    return 0.0;
}

int PoserProcessor::getNumPrograms()
{
    return 1;
}

int PoserProcessor::getCurrentProgram()
{
    return 0;
}

void PoserProcessor::setCurrentProgram(int index)
{
    juce::ignoreUnused(index);
}

const juce::String PoserProcessor::getProgramName(int index)
{
    juce::ignoreUnused(index);
    return {};
}

void PoserProcessor::changeProgramName(int index, const juce::String& newName)
{
    juce::ignoreUnused(index, newName);
}

void PoserProcessor::prepareToPlay(double sampleRate, int samplesPerBlock)
{
    juce::ignoreUnused(samplesPerBlock);
    currentSampleRate = sampleRate;

    // Enable smoothing for parameters that need it
    enableSmoothing("gain", 0.02); // 20ms smoothing
}

void PoserProcessor::releaseResources()
{
}

#ifndef JucePlugin_PreferredChannelConfigurations
bool PoserProcessor::isBusesLayoutSupported(const juce::AudioProcessor::BusesLayout& layouts) const
{
#if JucePlugin_IsMidiEffect
    juce::ignoreUnused(layouts);
    return true;
#else
    if (layouts.getMainOutputChannelSet() != juce::AudioChannelSet::mono() &&
        layouts.getMainOutputChannelSet() != juce::AudioChannelSet::stereo())
        return false;

#if ! JucePlugin_IsSynth
    if (layouts.getMainOutputChannelSet() != layouts.getMainInputChannelSet())
        return false;
#endif

    return true;
#endif
}
#endif

void PoserProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
{
    juce::ignoreUnused(midiMessages);
    juce::ScopedNoDenormals noDenormals;

    auto totalNumInputChannels = getTotalNumInputChannels();
    auto totalNumOutputChannels = getTotalNumOutputChannels();

    for (auto i = totalNumInputChannels; i < totalNumOutputChannels; ++i)
        buffer.clear(i, 0, buffer.getNumSamples());

    // Process audio with smoothed parameters
    for (int sample = 0; sample < buffer.getNumSamples(); ++sample)
    {
        float gainDb = getSmoothedParam("gain");
        float gain = juce::Decibels::decibelsToGain(gainDb);

        for (int channel = 0; channel < totalNumInputChannels; ++channel)
        {
            auto* channelData = buffer.getWritePointer(channel);
            channelData[sample] *= gain;
        }
    }

    // Sanitize output: replace NaN/Inf with 0.0f
    for (int channel = 0; channel < totalNumOutputChannels; ++channel)
    {
        auto* channelData = buffer.getWritePointer(channel);
        for (int sample = 0; sample < buffer.getNumSamples(); ++sample)
        {
            if (!std::isfinite(channelData[sample]))
                channelData[sample] = 0.0f;
        }
    }
}

bool PoserProcessor::hasEditor() const
{
    return true;
}

// createEditor() lives in PluginEditor.cpp to avoid pulling WebView
// dependencies into headless builds (unit tests with JUCE_WEB_BROWSER=0)

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
    {
        apvts.replaceState(juce::ValueTree::fromXml(*xml));
    }
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new PoserProcessor();
}
