#include "PluginProcessor.h"
#include "PluginEditor.h"
#include "BinaryData.h"

juce::AudioProcessorEditor* PoserProcessor::createEditor()
{
    return new PoserEditor(*this);
}

PoserEditor::PoserEditor(PoserProcessor& p)
    : AudioProcessorEditor(&p),
      audioProcessor(p),
      gainRelay{"gain"},
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
              .withOptionsFrom(gainRelay)
      },
      gainAttachment{
          *audioProcessor.getAPVTS().getParameter("gain"),
          gainRelay, nullptr}
{
    addAndMakeVisible(webView);
    webView.setWantsKeyboardFocus(false);
    webView.setOpaque(false);

    setResizable(true, true);
    setResizeLimits(300, 200, 800, 600);
    setSize(500, 400);

    // Delay navigation for WebView2 async initialization on Windows
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
    g.fillAll(juce::Colour(0xff1e1e1e));
}

void PoserEditor::resized()
{
    webView.setBounds(getLocalBounds());
}

void PoserEditor::timerCallback()
{
    ++timerTicks;
    pushVersionOnce();
}

void PoserEditor::pushVersionOnce()
{
    if (versionPushed) return;

    juce::String js = "(() => { "
                      "const el = document.getElementById('version-num'); "
                      "if (!el) return false; "
                      "el.textContent = 'v" JucePlugin_VersionString "'; "
                      "return true; })()";
    webView.evaluateJavascript(js, nullptr);

    if (timerTicks >= 120)
        versionPushed = true;
}

std::optional<juce::WebBrowserComponent::Resource> PoserEditor::getResource(const juce::String& url)
{
    juce::String urlToRetrieve;

    if (url == "/" || url.endsWithIgnoreCase("juce.backend/") || url.endsWithIgnoreCase("juce.backend"))
    {
        urlToRetrieve = "index.html";
    }
    else if (url.contains("juce.backend/"))
    {
        urlToRetrieve = url.fromLastOccurrenceOf("juce.backend/", false, true);
    }
    else if (url.startsWith("/"))
    {
        urlToRetrieve = url.substring(1);
    }
    else
    {
        urlToRetrieve = url;
    }

    if (urlToRetrieve.isEmpty())
        urlToRetrieve = "index.html";

    struct ResourceEntry { const char* path; const void* data; int size; const char* mime; };
    static const ResourceEntry resources[] = {
        { "index.html",              BinaryData::index_html,      BinaryData::index_htmlSize,      "text/html" },
        { "main.js",                 BinaryData::main_js,         BinaryData::main_jsSize,         "text/javascript" },
        { "main.css",                BinaryData::main_css,        BinaryData::main_cssSize,        "text/css" },
        { "lib/juce-bridge.js",      BinaryData::jucebridge_js,   BinaryData::jucebridge_jsSize,   "text/javascript" },
        { "lib/juce/index.js",       BinaryData::index_js,        BinaryData::index_jsSize,        "text/javascript" },
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
