cmake_minimum_required(VERSION 3.22)
project(audioplugin_unit_tests LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/unit_tests_artefacts/Release")

# Fetch Catch2
include(FetchContent)
FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.5.0
)
FetchContent_MakeAvailable(Catch2)

# Add JUCE (modules only mode for lighter build)
set(JUCE_MODULES_ONLY ON CACHE BOOL "" FORCE)
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/JUCE juce_build EXCLUDE_FROM_ALL)

# Path to project source
set(PROJECT_SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../src)

# Create test executable
add_executable(unit_tests
    test_parameters.cpp
    ${PROJECT_SRC_DIR}/PluginProcessor.cpp
)

target_include_directories(unit_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${PROJECT_SRC_DIR}
)

target_link_libraries(unit_tests PRIVATE
    juce_audio_basics
    juce_audio_processors
    juce_core
    juce_data_structures
    Catch2::Catch2WithMain
)

# JUCE needs some compile definitions
target_compile_definitions(unit_tests PRIVATE
    JUCE_GLOBAL_MODULE_SETTINGS_INCLUDED=1
    JUCE_STANDALONE_APPLICATION=1
    JUCE_USE_CURL=0
    JUCE_WEB_BROWSER=0
    JucePlugin_Name="AudioPlugin"
    JucePlugin_Build_VST3=0
    JucePlugin_Build_AU=0
)

# macOS-specific settings
if(APPLE)
    find_library(FOUNDATION_FRAMEWORK Foundation)
    find_library(COCOA_FRAMEWORK Cocoa)
    find_library(ACCELERATE_FRAMEWORK Accelerate)
    target_link_libraries(unit_tests PRIVATE
        ${FOUNDATION_FRAMEWORK}
        ${COCOA_FRAMEWORK}
        ${ACCELERATE_FRAMEWORK}
    )
endif()

# Enable CTest integration
include(CTest)
include(Catch)
catch_discover_tests(unit_tests)
