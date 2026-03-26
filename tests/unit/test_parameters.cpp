#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>
#include "PluginProcessor.h"

// Stub — PluginEditor.cpp is excluded from test builds (pulls in WebView)
juce::AudioProcessorEditor* PoserProcessor::createEditor() { return nullptr; }

TEST_CASE("Parameter creation and ranges", "[parameters]")
{
    PoserProcessor processor;
    auto& apvts = processor.getAPVTS();

    auto* gainParam = apvts.getParameter("gain");
    REQUIRE(gainParam != nullptr);

    auto range = gainParam->getNormalisableRange();
    REQUIRE_THAT(range.start, Catch::Matchers::WithinAbs(-60.0f, 0.01f));
    REQUIRE_THAT(range.end, Catch::Matchers::WithinAbs(12.0f, 0.01f));

    float defaultNormalized = gainParam->getDefaultValue();
    float defaultValue = range.convertFrom0to1(defaultNormalized);
    REQUIRE_THAT(defaultValue, Catch::Matchers::WithinAbs(0.0f, 0.1f));
}

TEST_CASE("State save/load roundtrip", "[state]")
{
    juce::MemoryBlock stateData;
    float testGainValue = -6.0f;

    SECTION("save state")
    {
        PoserProcessor processor;
        auto* gainParam = processor.getAPVTS().getParameter("gain");
        gainParam->setValueNotifyingHost(
            gainParam->getNormalisableRange().convertTo0to1(testGainValue));
        processor.getStateInformation(stateData);
    }

    SECTION("load and verify state")
    {
        // Save first
        {
            PoserProcessor processor;
            auto* gainParam = processor.getAPVTS().getParameter("gain");
            gainParam->setValueNotifyingHost(
                gainParam->getNormalisableRange().convertTo0to1(testGainValue));
            processor.getStateInformation(stateData);
        }

        // Load and verify
        PoserProcessor processor;
        processor.setStateInformation(stateData.getData(),
                                      static_cast<int>(stateData.getSize()));

        auto* gainParam = processor.getAPVTS().getParameter("gain");
        float loadedValue = gainParam->getNormalisableRange().convertFrom0to1(
            gainParam->getValue());
        REQUIRE_THAT(loadedValue,
                     Catch::Matchers::WithinAbs(testGainValue, 0.1f));
    }
}
