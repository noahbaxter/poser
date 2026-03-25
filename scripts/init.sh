#!/bin/bash
# =============================================================================
# Plugin Template Initialization Script
# Run this ONCE after cloning the template to rename everything.
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# -----------------------------------------------------------------------------
# Initialize JUCE submodule
# -----------------------------------------------------------------------------

echo -e "${BLUE}=== JUCE Plugin Template Initialization ===${NC}"
echo ""
echo -e "${YELLOW}Initializing JUCE submodule...${NC}"

if [ ! -f "third_party/JUCE/README.md" ]; then
    git submodule update --init --recursive
    echo -e "${GREEN}✓ JUCE submodule initialized${NC}"
else
    echo -e "${GREEN}✓ JUCE submodule already initialized${NC}"
fi

# -----------------------------------------------------------------------------
# Initialize Git LFS
# -----------------------------------------------------------------------------

echo -e "${YELLOW}Setting up Git LFS...${NC}"
if command -v git-lfs &>/dev/null; then
    git lfs install
    echo -e "${GREEN}✓ Git LFS initialized${NC}"
else
    echo -e "${YELLOW}⚠ git-lfs not installed. Install it for binary asset support (images, fonts).${NC}"
    echo -e "${YELLOW}  brew install git-lfs  (macOS)${NC}"
    echo -e "${YELLOW}  apt install git-lfs   (Linux)${NC}"
fi

# -----------------------------------------------------------------------------
# Prompt for values
# -----------------------------------------------------------------------------
echo ""
echo "This script will rename all template placeholders in the codebase."
echo ""

# Plugin name (e.g., "Guillotine", "SuperDelay")
read -p "Plugin name (PascalCase, e.g., Guillotine): " PLUGIN_NAME
if [[ -z "$PLUGIN_NAME" ]]; then
    echo -e "${RED}Error: Plugin name required${NC}"
    exit 1
fi

# Display name (e.g., "Guillotine", "Super Delay")
read -p "Plugin display name (shown in DAW, e.g., Guillotine) [$PLUGIN_NAME]: " PLUGIN_DISPLAY_NAME
PLUGIN_DISPLAY_NAME="${PLUGIN_DISPLAY_NAME:-$PLUGIN_NAME}"

# Description
read -p "Plugin description (short): " PLUGIN_DESC
PLUGIN_DESC="${PLUGIN_DESC:-A JUCE audio plugin}"

# Company/manufacturer name
read -p "Company/manufacturer name [Dichotic Studios]: " COMPANY_NAME
COMPANY_NAME="${COMPANY_NAME:-Dichotic Studios}"

# Bundle ID domain (e.g., com.dichoticstudios)
read -p "Bundle ID domain [com.dichoticstudios]: " BUNDLE_DOMAIN
BUNDLE_DOMAIN="${BUNDLE_DOMAIN:-com.dichoticstudios}"

# Plugin codes (4 characters each)
echo ""
echo -e "${YELLOW}Plugin codes must be exactly 4 characters (e.g., 'Gltn', 'Manu')${NC}"

# Generate default plugin code from name
DEFAULT_CODE=$(echo "$PLUGIN_NAME" | head -c 4)
read -p "Plugin code (4 chars) [$DEFAULT_CODE]: " PLUGIN_CODE
PLUGIN_CODE="${PLUGIN_CODE:-$DEFAULT_CODE}"
if [[ ${#PLUGIN_CODE} -ne 4 ]]; then
    echo -e "${RED}Error: Plugin code must be exactly 4 characters${NC}"
    exit 1
fi

read -p "Manufacturer code (4 chars) [Dcht]: " MANU_CODE
MANU_CODE="${MANU_CODE:-Dcht}"
if [[ ${#MANU_CODE} -ne 4 ]]; then
    echo -e "${RED}Error: Manufacturer code must be exactly 4 characters${NC}"
    exit 1
fi

# Derived values
PLUGIN_NAME_LOWER=$(echo "$PLUGIN_NAME" | tr '[:upper:]' '[:lower:]')
BUNDLE_ID="${BUNDLE_DOMAIN}.${PLUGIN_NAME_LOWER}"
CLAP_ID="${BUNDLE_DOMAIN}.${PLUGIN_NAME_LOWER}"
LV2URI="https://${BUNDLE_DOMAIN#com.}/plugins/${PLUGIN_NAME_LOWER}"

# -----------------------------------------------------------------------------
# Confirm
# -----------------------------------------------------------------------------

echo ""
echo -e "${YELLOW}=== Summary ===${NC}"
echo "  Plugin name:      $PLUGIN_NAME"
echo "  Display name:     $PLUGIN_DISPLAY_NAME"
echo "  Description:      $PLUGIN_DESC"
echo "  Company:          $COMPANY_NAME"
echo "  Bundle ID:        $BUNDLE_ID"
echo "  CLAP ID:          $CLAP_ID"
echo "  LV2 URI:          $LV2URI"
echo "  Plugin code:      $PLUGIN_CODE"
echo "  Manufacturer:     $MANU_CODE"
echo ""
read -p "Proceed? (y/N): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo -e "${BLUE}Renaming...${NC}"

# -----------------------------------------------------------------------------
# Perform replacements
# -----------------------------------------------------------------------------

# Helper: replace in file (works on macOS and Linux)
replace_in_file() {
    local file="$1"
    local search="$2"
    local replace="$3"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|$search|$replace|g" "$file"
    else
        sed -i "s|$search|$replace|g" "$file"
    fi
}

# 1. CMakeLists.txt
echo "  Updating CMakeLists.txt"
replace_in_file "CMakeLists.txt" "juce_add_plugin(AudioPlugin" "juce_add_plugin(${PLUGIN_NAME}"
replace_in_file "CMakeLists.txt" 'COMPANY_NAME ""' "COMPANY_NAME \"${COMPANY_NAME}\""
replace_in_file "CMakeLists.txt" 'BUNDLE_ID "com.example.audioplugin"' "BUNDLE_ID \"${BUNDLE_ID}\""
replace_in_file "CMakeLists.txt" "PLUGIN_MANUFACTURER_CODE Manu" "PLUGIN_MANUFACTURER_CODE ${MANU_CODE}"
replace_in_file "CMakeLists.txt" "PLUGIN_CODE AuPl" "PLUGIN_CODE ${PLUGIN_CODE}"
replace_in_file "CMakeLists.txt" 'PRODUCT_NAME "Audio Plugin"' "PRODUCT_NAME \"${PLUGIN_DISPLAY_NAME}\""
replace_in_file "CMakeLists.txt" 'PLUGIN_DESC "An audio plugin"' "PLUGIN_DESC \"${PLUGIN_DESC}\""
replace_in_file "CMakeLists.txt" 'LV2URI https://example.com/plugins/audioplugin' "LV2URI ${LV2URI}"
replace_in_file "CMakeLists.txt" 'CLAP_ID "com.example.audioplugin"' "CLAP_ID \"${CLAP_ID}\""
replace_in_file "CMakeLists.txt" "TARGET AudioPlugin" "TARGET ${PLUGIN_NAME}"
replace_in_file "CMakeLists.txt" "juce_generate_juce_header(AudioPlugin)" "juce_generate_juce_header(${PLUGIN_NAME})"
replace_in_file "CMakeLists.txt" "target_sources(AudioPlugin" "target_sources(${PLUGIN_NAME}"
replace_in_file "CMakeLists.txt" "juce_add_binary_data(AudioPluginData" "juce_add_binary_data(${PLUGIN_NAME}Data"
replace_in_file "CMakeLists.txt" "target_compile_definitions(AudioPlugin" "target_compile_definitions(${PLUGIN_NAME}"
replace_in_file "CMakeLists.txt" "target_link_libraries(AudioPlugin" "target_link_libraries(${PLUGIN_NAME}"
replace_in_file "CMakeLists.txt" "AudioPluginData" "${PLUGIN_NAME}Data"

# 2. C++ source files
echo "  Updating src files"
for file in src/PluginProcessor.cpp src/PluginProcessor.h src/PluginEditor.cpp src/PluginEditor.h; do
    if [[ -f "$file" ]]; then
        replace_in_file "$file" "AudioPluginProcessor" "${PLUGIN_NAME}Processor"
        replace_in_file "$file" "AudioPluginEditor" "${PLUGIN_NAME}Editor"
        replace_in_file "$file" '"Audio Plugin"' "\"${PLUGIN_DISPLAY_NAME}\""
    fi
done

# 3. Unit test files
echo "  Updating test files"
if [[ -f "tests/unit/test_parameters.cpp" ]]; then
    replace_in_file "tests/unit/test_parameters.cpp" "AudioPluginProcessor" "${PLUGIN_NAME}Processor"
fi
if [[ -f "tests/unit/CMakeLists.txt" ]]; then
    replace_in_file "tests/unit/CMakeLists.txt" "audioplugin_unit_tests" "${PLUGIN_NAME_LOWER}_unit_tests"
    replace_in_file "tests/unit/CMakeLists.txt" 'JucePlugin_Name="AudioPlugin"' "JucePlugin_Name=\"${PLUGIN_NAME}\""
fi

# 4. Python test files
if [[ -f "tests/conftest.py" ]]; then
    replace_in_file "tests/conftest.py" "AudioPlugin.vst3" "${PLUGIN_NAME}.vst3"
fi
if [[ -f "tests/generate_references.py" ]]; then
    replace_in_file "tests/generate_references.py" "AudioPlugin.vst3" "${PLUGIN_NAME}.vst3"
fi

# 5. Scripts
echo "  Updating scripts"
replace_in_file "scripts/_common.sh" 'PLUGIN_NAME="AudioPlugin"' "PLUGIN_NAME=\"${PLUGIN_NAME}\""

if [[ -f "scripts/build-windows.sh" ]]; then
    replace_in_file "scripts/build-windows.sh" 'PLUGIN_NAME="AudioPlugin"' "PLUGIN_NAME=\"${PLUGIN_NAME}\""
fi

replace_in_file "scripts/clean.sh" "Cleaning AudioPlugin" "Cleaning ${PLUGIN_NAME}"
replace_in_file "scripts/setup.sh" "AudioPlugin Environment Setup" "${PLUGIN_NAME} Environment Setup"
replace_in_file "scripts/test.sh" "AudioPlugin Test Runner" "${PLUGIN_NAME} Test Runner"
replace_in_file "scripts/test.sh" 'VST3/AudioPlugin.vst3' "VST3/${PLUGIN_NAME}.vst3"
replace_in_file "scripts/standalone.sh" '"Audio Plugin.app"' "\"${PLUGIN_DISPLAY_NAME}.app\""

if [[ -f "scripts/watch.sh" ]]; then
    replace_in_file "scripts/watch.sh" '"Audio Plugin.app"' "\"${PLUGIN_DISPLAY_NAME}.app\""
    replace_in_file "scripts/watch.sh" '"Audio Plugin"' "\"${PLUGIN_DISPLAY_NAME}\""
fi

# 6. Installers
echo "  Updating installer files"
replace_in_file "installer/macos/build-pkg.sh" 'PLUGIN_NAME="AudioPlugin"' "PLUGIN_NAME=\"${PLUGIN_NAME}\""
replace_in_file "installer/macos/build-pkg.sh" 'BUNDLE_ID="com.example.audioplugin"' "BUNDLE_ID=\"${BUNDLE_ID}\""

replace_in_file "installer/windows/installer.iss" '#define PLUGIN_NAME "AudioPlugin"' "#define PLUGIN_NAME \"${PLUGIN_NAME}\""
replace_in_file "installer/windows/installer.iss" 'AudioPlugin_artefacts' "${PLUGIN_NAME}_artefacts"
replace_in_file "installer/windows/installer.iss" 'Audio Plugin.vst3' "${PLUGIN_DISPLAY_NAME}.vst3"

replace_in_file "installer/linux/README.txt" "Audio Plugin" "${PLUGIN_DISPLAY_NAME}"
replace_in_file "installer/linux/README.txt" "AudioPlugin" "${PLUGIN_NAME}"

# 7. Web UI
echo "  Updating web files"
replace_in_file "web/index.html" '<title>Audio Plugin</title>' "<title>${PLUGIN_DISPLAY_NAME}</title>"
replace_in_file "web/index.html" '<h1>Audio Plugin</h1>' "<h1>${PLUGIN_DISPLAY_NAME}</h1>"

# 8. GitHub workflow
echo "  Updating .github/workflows/build.yml"
if [[ -f ".github/workflows/build.yml" ]]; then
    replace_in_file ".github/workflows/build.yml" 'name: Build AudioPlugin' "name: Build ${PLUGIN_NAME}"
    replace_in_file ".github/workflows/build.yml" "AudioPlugin_artefacts" "${PLUGIN_NAME}_artefacts"
    replace_in_file ".github/workflows/build.yml" 'AudioPlugin-VST3-Windows' "${PLUGIN_NAME}-VST3-Windows"
    replace_in_file ".github/workflows/build.yml" 'AudioPlugin-macOS' "${PLUGIN_NAME}-macOS"
    replace_in_file ".github/workflows/build.yml" 'AudioPlugin-Linux' "${PLUGIN_NAME}-Linux"
    replace_in_file ".github/workflows/build.yml" 'AudioPlugin-Installer' "${PLUGIN_NAME}-Installer"
    replace_in_file ".github/workflows/build.yml" 'AudioPlugin.vst3' "${PLUGIN_NAME}.vst3"
    replace_in_file ".github/workflows/build.yml" 'AudioPlugin.component' "${PLUGIN_NAME}.component"
    replace_in_file ".github/workflows/build.yml" '"Audio Plugin.vst3"' "\"${PLUGIN_DISPLAY_NAME}.vst3\""
    replace_in_file ".github/workflows/build.yml" '"Audio Plugin.component"' "\"${PLUGIN_DISPLAY_NAME}.component\""
    replace_in_file ".github/workflows/build.yml" '"Audio Plugin.lv2"' "\"${PLUGIN_DISPLAY_NAME}.lv2\""
    replace_in_file ".github/workflows/build.yml" '"Audio Plugin.clap"' "\"${PLUGIN_DISPLAY_NAME}.clap\""
    replace_in_file ".github/workflows/build.yml" '"Audio Plugin"' "\"${PLUGIN_DISPLAY_NAME}\""
    replace_in_file ".github/workflows/build.yml" 'PLUGIN_NAME="AudioPlugin"' "PLUGIN_NAME=\"${PLUGIN_NAME}\""
    replace_in_file ".github/workflows/build.yml" '"com.example.audioplugin.pkg"' "\"${BUNDLE_ID}.pkg\""
    replace_in_file ".github/workflows/build.yml" '## AudioPlugin Release' "## ${PLUGIN_NAME} Release"
    replace_in_file ".github/workflows/build.yml" "AudioPlugin v" "${PLUGIN_NAME} v"
    replace_in_file ".github/workflows/build.yml" "AudioPlugin {0}" "${PLUGIN_NAME} {0}"
    replace_in_file ".github/workflows/build.yml" "AudioPlugin-" "${PLUGIN_NAME}-"
fi

# 9. CLAUDE.md
echo "  Updating CLAUDE.md"
if [[ -f "CLAUDE.md" ]]; then
    replace_in_file "CLAUDE.md" "# AudioPlugin" "# ${PLUGIN_NAME}"
    replace_in_file "CLAUDE.md" "AudioPluginData" "${PLUGIN_NAME}Data"
fi

# -----------------------------------------------------------------------------
# Self-destruct
# -----------------------------------------------------------------------------

echo ""
echo -e "${GREEN}=== Initialization complete! ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Update README.md with your plugin's documentation"
echo "  2. Initialize git:  git add -A && git commit -m 'Initialize ${PLUGIN_NAME}'"
echo "  3. Build:           ./scripts/setup.sh && ./scripts/build.sh"
echo ""

# Clean up template files
rm -f "$PROJECT_ROOT/TEMPLATE.md"
rm -f "$SCRIPT_DIR/init.sh"
echo -e "${GREEN}✓ Removed init.sh and TEMPLATE.md${NC}"
