cmake_minimum_required(VERSION 3.22)

# Read version from VERSION file
file(READ "${CMAKE_SOURCE_DIR}/VERSION" VERSION_STRING)
string(STRIP "${VERSION_STRING}" VERSION_STRING)

project(Poser VERSION ${VERSION_STRING} LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Suppress warnings from JUCE (third-party code we can't control)
set(_saved_cxx_flags "${CMAKE_CXX_FLAGS}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -w")
add_subdirectory(third_party/JUCE)
set(CMAKE_CXX_FLAGS "${_saved_cxx_flags}")

# CLAP support via clap-juce-extensions
add_subdirectory(third_party/clap-juce-extensions EXCLUDE_FROM_ALL)

# On Windows with MSVC, install WebView2 if not present
if(MSVC)
    set(WEBVIEW2_VERSION "1.0.3485.44")
    set(WEBVIEW2_PACKAGE_DIR "${CMAKE_SOURCE_DIR}/packages/Microsoft.Web.WebView2.${WEBVIEW2_VERSION}")

    if(NOT EXISTS "${WEBVIEW2_PACKAGE_DIR}")
        message(STATUS "Installing WebView2 NuGet package...")
        execute_process(
            COMMAND powershell -ExecutionPolicy Bypass -NoProfile -File
                "${CMAKE_SOURCE_DIR}/scripts/DownloadWebView2.ps1"
            WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
            RESULT_VARIABLE WEBVIEW2_RESULT
        )
        if(NOT WEBVIEW2_RESULT EQUAL 0)
            message(FATAL_ERROR "Failed to install WebView2 package. Result: ${WEBVIEW2_RESULT}")
        endif()
    endif()

    # Point JUCE's FindWebView2 to our local package
    set(JUCE_WEBVIEW2_PACKAGE_LOCATION "${CMAKE_SOURCE_DIR}/packages" CACHE PATH "" FORCE)
endif()

juce_add_plugin(Poser
    VERSION ${PROJECT_VERSION}
    COMPANY_NAME "Dichotic Studios"
    BUNDLE_ID "com.dichoticstudios.poser"
    PLUGIN_MANUFACTURER_CODE Dcht
    PLUGIN_CODE Posr
    FORMATS VST3 AU LV2 Standalone
    PRODUCT_NAME "Poser EQ"
    PLUGIN_DESC "A JUCE audio plugin"

    # WebView requirements
    NEEDS_WEB_BROWSER TRUE
    NEEDS_WEBVIEW2 TRUE

    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT FALSE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS FALSE
    COPY_PLUGIN_AFTER_BUILD FALSE

    VST3_CATEGORIES Fx
    LV2URI https://dichoticstudios/plugins/poser
)

# CLAP plugin wrapper
clap_juce_extensions_plugin(
    TARGET Poser
    CLAP_ID "com.dichoticstudios.poser"
    CLAP_FEATURES audio-effect utility
)

juce_generate_juce_header(Poser)

target_sources(Poser
    PRIVATE
        src/PluginProcessor.cpp
        src/PluginEditor.cpp
        third_party/AudioFFT/AudioFFT.cpp
)

target_include_directories(Poser PRIVATE third_party/AudioFFT)

# Enable Apple Accelerate backend for AudioFFT on macOS
if(APPLE)
    target_compile_definitions(Poser PRIVATE AUDIOFFT_APPLE_ACCELERATE)
    target_link_libraries(Poser PRIVATE "-framework Accelerate")
endif()

# Binary data for web files
juce_add_binary_data(PoserData
    NAMESPACE BinaryData
    SOURCES
        web/index.html
        web/main.js
        web/components/knob.js
        web/main.css
        web/lib/juce-bridge.js
        web/lib/juce/index.js
        web/lib/juce/check_native_interop.js
)

target_compile_definitions(Poser
    PUBLIC
        JUCE_STRICT_REFCOUNTEDPOINTER=1
        JUCE_VST3_CAN_REPLACE_VST2=0
        JUCE_USE_WIN_WEBVIEW2_WITH_STATIC_LINKING=1
        JUCE_WEB_BROWSER=1
        JUCE_USE_CURL=0
    PRIVATE
        DONT_SET_USING_JUCE_NAMESPACE=1
)

target_link_libraries(Poser
    PRIVATE
        PoserData
        juce::juce_audio_basics
        juce::juce_audio_devices
        juce::juce_audio_formats
        juce::juce_audio_plugin_client
        juce::juce_audio_processors
        juce::juce_audio_utils
        juce::juce_core
        juce::juce_data_structures
        juce::juce_dsp
        juce::juce_events
        juce::juce_graphics
        juce::juce_gui_basics
        juce::juce_gui_extra
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags
)
