#include "PluginProcessor.h"
#include "PluginEditor.h"
#include "BinaryData.h"
#include "CurveData.h"

juce::AudioProcessorEditor* PoserProcessor::createEditor()
{
    return new PoserEditor(*this);
}

PoserEditor::PoserEditor(PoserProcessor& p)
    : AudioProcessorEditor(&p),
      audioProcessor(p),
      micSelectRelay{"mic_select"},
      cabSelectRelay{"cab_select"},
      speakerSelectRelay{"speaker_select"},
      positionSelectRelay{"position_select"},
      micBlendRelay{"mic_blend"},
      cabBlendRelay{"cab_blend"},
      speakerBlendRelay{"speaker_blend"},
      positionBlendRelay{"position_blend"},
      masterPushRelay{"master_push"},
      outputTrimRelay{"output_trim"},
      curveLowCutRelay{"curve_low_cut"},
      curveHighCutRelay{"curve_high_cut"},
      curveModeRelay{"curve_mode"},
      cabFilterRelay{"cab_filter"},
      gainCompRelay{"gain_comp"},
      webView{
          juce::WebBrowserComponent::Options{}
              .withBackend(juce::WebBrowserComponent::Options::Backend::webview2)
              .withWinWebView2Options(
                  juce::WebBrowserComponent::Options::WinWebView2{}
                      .withUserDataFolder(juce::File::getSpecialLocation(
                          juce::File::SpecialLocationType::tempDirectory)))
              .withNativeIntegrationEnabled()
              .withResourceProvider(
                  [this](const auto& url) { return getResource(url); })
              .withOptionsFrom(micSelectRelay)
              .withOptionsFrom(cabSelectRelay)
              .withOptionsFrom(speakerSelectRelay)
              .withOptionsFrom(positionSelectRelay)
              .withOptionsFrom(micBlendRelay)
              .withOptionsFrom(cabBlendRelay)
              .withOptionsFrom(speakerBlendRelay)
              .withOptionsFrom(positionBlendRelay)
              .withOptionsFrom(masterPushRelay)
              .withOptionsFrom(outputTrimRelay)
              .withOptionsFrom(curveLowCutRelay)
              .withOptionsFrom(curveHighCutRelay)
              .withOptionsFrom(curveModeRelay)
              .withOptionsFrom(cabFilterRelay)
              .withOptionsFrom(gainCompRelay)
      },
      micSelectAttach{*audioProcessor.getAPVTS().getParameter("mic_select"), micSelectRelay, nullptr},
      cabSelectAttach{*audioProcessor.getAPVTS().getParameter("cab_select"), cabSelectRelay, nullptr},
      speakerSelectAttach{*audioProcessor.getAPVTS().getParameter("speaker_select"), speakerSelectRelay, nullptr},
      positionSelectAttach{*audioProcessor.getAPVTS().getParameter("position_select"), positionSelectRelay, nullptr},
      micBlendAttach{*audioProcessor.getAPVTS().getParameter("mic_blend"), micBlendRelay, nullptr},
      cabBlendAttach{*audioProcessor.getAPVTS().getParameter("cab_blend"), cabBlendRelay, nullptr},
      speakerBlendAttach{*audioProcessor.getAPVTS().getParameter("speaker_blend"), speakerBlendRelay, nullptr},
      positionBlendAttach{*audioProcessor.getAPVTS().getParameter("position_blend"), positionBlendRelay, nullptr},
      masterPushAttach{*audioProcessor.getAPVTS().getParameter("master_push"), masterPushRelay, nullptr},
      outputTrimAttach{*audioProcessor.getAPVTS().getParameter("output_trim"), outputTrimRelay, nullptr},
      curveLowCutAttach{*audioProcessor.getAPVTS().getParameter("curve_low_cut"), curveLowCutRelay, nullptr},
      curveHighCutAttach{*audioProcessor.getAPVTS().getParameter("curve_high_cut"), curveHighCutRelay, nullptr},
      curveModeAttach{*audioProcessor.getAPVTS().getParameter("curve_mode"), curveModeRelay, nullptr},
      cabFilterAttach{*audioProcessor.getAPVTS().getParameter("cab_filter"), cabFilterRelay, nullptr},
      gainCompAttach{*audioProcessor.getAPVTS().getParameter("gain_comp"), gainCompRelay, nullptr}
{
    addAndMakeVisible(webView);
    webView.setWantsKeyboardFocus(false);
    webView.setOpaque(false);

    setResizable(false, false);
    setSize(560, 560);

    juce::MessageManager::callAsync([safeThis = juce::Component::SafePointer<PoserEditor>(this)]() {
        if (safeThis != nullptr)
            safeThis->webView.goToURL(juce::WebBrowserComponent::getResourceProviderRoot());
    });

    startTimerHz(60);
}

PoserEditor::~PoserEditor()
{
    stopTimer();
}

void PoserEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xffffffff));
}

void PoserEditor::resized()
{
    webView.setBounds(getLocalBounds());
}

void PoserEditor::timerCallback()
{
    ++timerTicks;
    pushInitData();
}

// --- Init payload: push component names + mic groups to JS ---

void PoserEditor::pushInitData()
{
    if (initDataPushed) return;

    auto* root = new juce::DynamicObject();
    root->setProperty("version", juce::String(JucePlugin_VersionString) + " (" + __DATE__ + " " + __TIME__ + ")");

    // Component options: iterate CurveData arrays for names
    auto* comps = new juce::DynamicObject();

    auto buildOptions = [](const auto* curves, int count) {
        juce::Array<juce::var> arr;
        for (int i = 0; i < count; ++i)
            arr.add(juce::String(curves[i].name));
        return arr;
    };

    auto makeComp = [](const char* label, const char* paramId, const char* blendId, juce::Array<juce::var> options) {
        auto* c = new juce::DynamicObject();
        c->setProperty("label", juce::String(label));
        c->setProperty("paramId", juce::String(paramId));
        c->setProperty("blendId", juce::String(blendId));
        c->setProperty("options", options);
        return c;
    };

    comps->setProperty("mic", makeComp("MIC", "mic_select", "mic_blend",
        buildOptions(CurveData::kMics, CurveData::kNumMics)));

    // Cabinet: combined cab + speaker as sub-components
    {
        auto* cabinet = new juce::DynamicObject();
        cabinet->setProperty("label", "CAB");
        cabinet->setProperty("type", "cabinet");
        cabinet->setProperty("cab", makeComp("CAB", "cab_select", "cab_blend",
            buildOptions(CurveData::kCabs, CurveData::kNumCabs)));
        cabinet->setProperty("speaker", makeComp("SPK", "speaker_select", "speaker_blend",
            buildOptions(CurveData::kSpeakers, CurveData::kNumSpeakers)));
        comps->setProperty("cabinet", cabinet);
    }

    comps->setProperty("position", makeComp("POS", "position_select", "position_blend",
        buildOptions(CurveData::kPositions, CurveData::kNumPositions)));
    root->setProperty("components", comps);

    // Mic groups
    juce::Array<juce::var> groups;
    for (int g = 0; g < ::CurveData::kNumMicGroups; ++g)
    {
        auto* group = new juce::DynamicObject();
        group->setProperty("name", juce::String(::CurveData::kMicGroups[g].name));
        juce::Array<juce::var> indices;
        for (int i = 0; i < ::CurveData::kMicGroups[g].count; ++i)
            indices.add(::CurveData::kMicGroups[g].indices[i]);
        group->setProperty("indices", indices);

        // Sub-group tags (e.g. "kick" mics grouped together)
        if (::CurveData::kMicGroups[g].numTags > 0)
        {
            juce::Array<juce::var> tags;
            for (int t = 0; t < ::CurveData::kMicGroups[g].numTags; ++t)
            {
                auto* tag = new juce::DynamicObject();
                tag->setProperty("name", juce::String(::CurveData::kMicGroups[g].tags[t].name));
                tag->setProperty("start", ::CurveData::kMicGroups[g].tags[t].start);
                tag->setProperty("end", ::CurveData::kMicGroups[g].tags[t].end);
                tags.add(tag);
            }
            group->setProperty("tags", tags);
        }

        groups.add(group);
    }
    root->setProperty("micGroups", groups);

    juce::String json = juce::JSON::toString(juce::var(root));
    juce::String js = "if (window.__poser_init__ && !window.__poser_initialized__) window.__poser_init__(" + json + ");";
    webView.evaluateJavascript(js, nullptr);

    if (timerTicks >= 300)
        initDataPushed = true;
}

// --- Resource provider ---

std::optional<juce::WebBrowserComponent::Resource> PoserEditor::getResource(const juce::String& url)
{
    juce::String urlToRetrieve;

    if (url == "/" || url.endsWithIgnoreCase("juce.backend/") || url.endsWithIgnoreCase("juce.backend"))
        urlToRetrieve = "index.html";
    else if (url.contains("juce.backend/"))
        urlToRetrieve = url.fromLastOccurrenceOf("juce.backend/", false, true);
    else if (url.startsWith("/"))
        urlToRetrieve = url.substring(1);
    else
        urlToRetrieve = url;

    if (urlToRetrieve.isEmpty())
        urlToRetrieve = "index.html";

    struct ResourceEntry { const char* path; const void* data; int size; const char* mime; };
    static const ResourceEntry resources[] = {
        { "index.html",                     BinaryData::index_html,             BinaryData::index_htmlSize,              "text/html" },
        { "main.js",                        BinaryData::main_js,                BinaryData::main_jsSize,                 "text/javascript" },
        { "main.css",                       BinaryData::main_css,               BinaryData::main_cssSize,                "text/css" },
        { "components/controls/knob.js",    BinaryData::knob_js,                BinaryData::knob_jsSize,                 "text/javascript" },
        { "components/controls/selector.js",BinaryData::selector_js,            BinaryData::selector_jsSize,             "text/javascript" },
        { "components/controls/toggle.js",  BinaryData::toggle_js,              BinaryData::toggle_jsSize,               "text/javascript" },
        { "lib/juce-bridge.js",             BinaryData::jucebridge_js,          BinaryData::jucebridge_jsSize,           "text/javascript" },
        { "lib/juce/index.js",              BinaryData::index_js,               BinaryData::index_jsSize,                "text/javascript" },
        { "lib/juce/check_native_interop.js", BinaryData::check_native_interop_js, BinaryData::check_native_interop_jsSize, "text/javascript" },
    };

    for (const auto& res : resources)
    {
        if (urlToRetrieve == res.path)
        {
            std::vector<std::byte> bytes(static_cast<size_t>(res.size));
            std::memcpy(bytes.data(), res.data, static_cast<size_t>(res.size));
            return juce::WebBrowserComponent::Resource { std::move(bytes), juce::String(res.mime) };
        }
    }

    return std::nullopt;
}
