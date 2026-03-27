#!/bin/bash
# Build script for AudioPlugin (CMake-based)
#
# Usage:
#   ./scripts/build.sh                 # Build Release (default)
#   ./scripts/build.sh debug           # Build Debug
#   ./scripts/build.sh standalone      # Build and launch standalone app
#   ./scripts/build.sh curves          # Regenerate curve data only
#   ./scripts/build.sh clean           # Clean build artifacts
#   ./scripts/build.sh uninstall       # Remove installed plugins
#
# Options:
#   --install                          # Install to user library (default: on)
#   --no-install                       # Skip installation
#   --no-launch                        # (standalone) Build but don't launch
#   --fg                               # (standalone) Launch in foreground

set -e

source "$(dirname "$0")/_common.sh"

RELEASE_DIR="$PROJECT_ROOT/releases"
STANDALONE_BUILD_DIR="$PROJECT_ROOT/build-standalone"

# Parse arguments
MODE="Release"
INSTALL=true
LAUNCH=true
FOREGROUND=false

for arg in "$@"; do
    case $arg in
        debug|Debug|DEBUG)
            MODE="Debug"
            ;;
        clean|Clean|CLEAN)
            MODE="Clean"
            ;;
        uninstall|Uninstall|UNINSTALL)
            MODE="Uninstall"
            ;;
        release|Release|RELEASE)
            MODE="Release"
            ;;
        curves|Curves|CURVES)
            MODE="Curves"
            ;;
        standalone|Standalone|STANDALONE)
            MODE="Standalone"
            ;;
        --install)
            INSTALL=true
            ;;
        --no-install)
            INSTALL=false
            ;;
        --no-launch)
            LAUNCH=false
            ;;
        --fg|--foreground)
            FOREGROUND=true
            ;;
        --help|-h)
            echo "Usage: ./scripts/build.sh [mode] [options]"
            echo ""
            echo "Modes:"
            echo "  debug       Build Debug configuration"
            echo "  release     Build Release configuration (default)"
            echo "  standalone  Build and launch standalone app"
            echo "  curves      Regenerate curve data only"
            echo "  clean       Clean build artifacts"
            echo "  uninstall   Remove installed plugins"
            echo ""
            echo "Options:"
            echo "  --install      Install plugins to user library (default)"
            echo "  --no-install   Skip installation"
            echo "  --no-launch    (standalone) Build without launching"
            echo "  --fg           (standalone) Launch in foreground"
            exit 0
            ;;
    esac
done

echo -e "${YELLOW}=== $PLUGIN_NAME Build Script (CMake) ===${NC}"
echo "Project root: $PROJECT_ROOT"
echo "Mode: $MODE"

install_plugins() {
    local src_dir="$1"
    local vst3_dest="$HOME/Library/Audio/Plug-Ins/VST3"
    local au_dest="$HOME/Library/Audio/Plug-Ins/Components"

    echo -e "\n${YELLOW}Installing plugins to user library...${NC}"
    mkdir -p "$vst3_dest" "$au_dest"

    # VST3 has a space in the name from CMake
    local vst3_name="Poser EQ.vst3"
    local au_name="Poser EQ.component"

    if [ -d "$src_dir/VST3/$vst3_name" ]; then
        rm -rf "$vst3_dest/$PLUGIN_NAME.vst3"
        cp -R "$src_dir/VST3/$vst3_name" "$vst3_dest/$PLUGIN_NAME.vst3"
        echo -e "${GREEN}✓ Installed VST3 to $vst3_dest${NC}"
    fi

    if [ -d "$src_dir/AU/$au_name" ]; then
        rm -rf "$au_dest/$PLUGIN_NAME.component"
        cp -R "$src_dir/AU/$au_name" "$au_dest/$PLUGIN_NAME.component"
        echo -e "${GREEN}✓ Installed AU to $au_dest${NC}"
    fi
}

needs_reconfigure() {
    local build_dir="$1"
    if [ ! -f "$build_dir/CMakeCache.txt" ]; then
        return 0
    fi
    if ! grep -q "CMAKE_HOME_DIRECTORY:INTERNAL=$PROJECT_ROOT" "$build_dir/CMakeCache.txt" 2>/dev/null; then
        echo -e "${YELLOW}Project path changed, reconfiguring...${NC}"
        rm -rf "$build_dir"
        return 0
    fi
    if [ "$PROJECT_ROOT/CMakeLists.txt" -nt "$build_dir/CMakeCache.txt" ]; then
        echo -e "${YELLOW}CMakeLists.txt changed, reconfiguring...${NC}"
        return 0
    fi
    if [ -f "$PROJECT_ROOT/VERSION" ]; then
        local current_version cached_version
        current_version=$(cat "$PROJECT_ROOT/VERSION" | tr -d '[:space:]')
        cached_version=$(grep "^CMAKE_PROJECT_VERSION:STATIC=" "$build_dir/CMakeCache.txt" 2>/dev/null | cut -d= -f2)
        if [ "$current_version" != "$cached_version" ]; then
            echo -e "${YELLOW}VERSION changed ($cached_version → $current_version), reconfiguring...${NC}"
            rm -rf "$build_dir"
            return 0
        fi
    fi
    return 1
}

# Always regenerate curve data — deterministic, ~2s, cmake skips if unchanged
if [ "$MODE" != "Clean" ] && [ "$MODE" != "Uninstall" ]; then
    echo -e "${YELLOW}Regenerating curve data...${NC}"
    python3 "$PROJECT_ROOT/tools/curves/manage.py" build
fi

if [ "$MODE" = "Curves" ]; then
    echo -e "${GREEN}Done (curves only)${NC}"
    exit 0
fi

case "$MODE" in
    Clean)
        echo -e "\n${YELLOW}Cleaning build artifacts...${NC}"
        rm -rf "$BUILD_DIR" "$STANDALONE_BUILD_DIR"
        echo -e "${GREEN}✓ Cleaned${NC}"
        ;;

    Uninstall)
        echo -e "\n${YELLOW}Removing installed plugins...${NC}"
        rm -rf "$HOME/Library/Audio/Plug-Ins/VST3/$PLUGIN_NAME.vst3"
        rm -rf "$HOME/Library/Audio/Plug-Ins/Components/$PLUGIN_NAME.component"
        echo -e "${GREEN}✓ Uninstalled${NC}"
        ;;

    Standalone)
        # Kill any running instance (prevents WebView caching issues)
        pkill -f "Poser EQ.app" 2>/dev/null || true
        sleep 0.5

        if needs_reconfigure "$STANDALONE_BUILD_DIR"; then
            echo -e "${YELLOW}Configuring CMake...${NC}"
            CMAKE_OUTPUT=$(cmake -B "$STANDALONE_BUILD_DIR" -G Xcode \
                -DCMAKE_OSX_ARCHITECTURES="arm64" \
                -DCMAKE_OSX_DEPLOYMENT_TARGET=10.15 \
                "$PROJECT_ROOT" 2>&1) || {
                echo "$CMAKE_OUTPUT"
                echo -e "${RED}CMake configuration failed${NC}"
                exit 1
            }
            fix_ownership "$STANDALONE_BUILD_DIR"
            echo -e "${GREEN}✓ CMake configured${NC}"
        fi

        echo -e "${YELLOW}Building standalone app...${NC}"
        BUILD_OUTPUT=$(cmake --build "$STANDALONE_BUILD_DIR" --config Debug --target ${PLUGIN_NAME}_Standalone --parallel -- -quiet 2>&1) || {
            echo "$BUILD_OUTPUT"
            echo -e "${RED}Build failed${NC}"
            exit 1
        }
        fix_ownership "$STANDALONE_BUILD_DIR"

        APP_PATH="$STANDALONE_BUILD_DIR/${PLUGIN_NAME}_artefacts/Debug/Standalone/Poser EQ.app"
        if [ ! -d "$APP_PATH" ]; then
            echo -e "${RED}Build failed - app not found at $APP_PATH${NC}"
            exit 1
        fi

        if [ "$LAUNCH" = true ]; then
            if [ "$FOREGROUND" = true ]; then
                echo -e "${GREEN}✓ Built. Launching in foreground (Ctrl+C to quit)...${NC}"
                exec "$APP_PATH/Contents/MacOS/Poser EQ"
            fi
            echo -e "${GREEN}✓ Built. Launching...${NC}"
            open "$APP_PATH"
        else
            echo -e "${GREEN}✓ Built.${NC}"
        fi
        ;;

    Debug)
        check_stale_cache

        if needs_reconfigure "$BUILD_DIR"; then
            echo -e "\n${YELLOW}Configuring Debug build...${NC}"
        fi
        cmake -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Debug -DCMAKE_OSX_ARCHITECTURES="arm64"

        echo -e "\n${YELLOW}Building Debug...${NC}"
        cmake --build "$BUILD_DIR" --config Debug -j$(cpu_count)

        echo -e "${GREEN}✓ Debug build complete${NC}"

        if [ "$INSTALL" = true ]; then
            install_plugins "$BUILD_DIR/${PLUGIN_NAME}_artefacts/Debug"
        fi
        ;;

    Release)
        check_stale_cache

        if needs_reconfigure "$BUILD_DIR"; then
            echo -e "\n${YELLOW}Configuring Release build (Universal Binary)...${NC}"
        fi
        cmake -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64"

        echo -e "\n${YELLOW}Building Release...${NC}"
        cmake --build "$BUILD_DIR" --config Release -j$(cpu_count)

        ARTEFACTS_DIR="$BUILD_DIR/${PLUGIN_NAME}_artefacts/Release"
        VST3_PATH="$ARTEFACTS_DIR/VST3/Poser EQ.vst3"
        AU_PATH="$ARTEFACTS_DIR/AU/Poser EQ.component"

        if [ ! -d "$VST3_PATH" ] || [ ! -d "$AU_PATH" ]; then
            echo -e "${RED}Error: Build artifacts missing${NC}"
            exit 1
        fi

        # Check Universal Binary
        echo "Checking architectures..."
        VST3_ARCHS=$(lipo -archs "$VST3_PATH/Contents/MacOS/Poser EQ" 2>/dev/null || echo "unknown")

        if [[ "$VST3_ARCHS" == *"arm64"* ]] && [[ "$VST3_ARCHS" == *"x86_64"* ]]; then
            echo -e "${GREEN}✓ VST3 is Universal Binary: $VST3_ARCHS${NC}"
        else
            echo -e "${YELLOW}Warning: VST3 is not universal: $VST3_ARCHS${NC}"
        fi

        echo -e "${GREEN}✓ Release build complete${NC}"

        if [ "$INSTALL" = true ]; then
            install_plugins "$ARTEFACTS_DIR"
        fi

        # Create Release Package
        echo -e "\n${YELLOW}Creating release package...${NC}"
        VERSION=$(cat "$PROJECT_ROOT/VERSION" 2>/dev/null || echo "0.1.0")
        RELEASE_NAME="$PLUGIN_NAME-v${VERSION}-macOS"
        TEMP_DIR="/tmp/$RELEASE_NAME"

        rm -rf "$TEMP_DIR"
        mkdir -p "$TEMP_DIR"

        cp -R "$VST3_PATH" "$TEMP_DIR/$PLUGIN_NAME.vst3"
        cp -R "$AU_PATH" "$TEMP_DIR/$PLUGIN_NAME.component"

        cat > "$TEMP_DIR/Install.command" << 'INSTALL_SCRIPT'
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLUGIN_NAME="Poser"
echo "Installing $PLUGIN_NAME..."
mkdir -p "$HOME/Library/Audio/Plug-Ins/VST3"
mkdir -p "$HOME/Library/Audio/Plug-Ins/Components"
cp -R "$DIR/$PLUGIN_NAME.vst3" "$HOME/Library/Audio/Plug-Ins/VST3/"
cp -R "$DIR/$PLUGIN_NAME.component" "$HOME/Library/Audio/Plug-Ins/Components/"
echo ""
echo "Removing Gatekeeper quarantine attributes (may require password)..."
sudo xattr -cr "$HOME/Library/Audio/Plug-Ins/VST3/$PLUGIN_NAME.vst3"
sudo xattr -cr "$HOME/Library/Audio/Plug-Ins/Components/$PLUGIN_NAME.component"
echo ""
echo "Done! Please restart your DAW."
read -p "Press any key to exit..."
INSTALL_SCRIPT
        chmod +x "$TEMP_DIR/Install.command"

        cat > "$TEMP_DIR/README.txt" << EOF
$PLUGIN_NAME v${VERSION} - macOS Release

This bundle contains:
- $PLUGIN_NAME.vst3 (VST3 plugin)
- $PLUGIN_NAME.component (Audio Unit plugin)
- Install.command (automatic installer script)

Installation:
1. Double-click Install.command for automatic installation
2. Or manually copy plugins to:
   - VST3: ~/Library/Audio/Plug-Ins/VST3/
   - AU: ~/Library/Audio/Plug-Ins/Components/

Requirements: macOS 10.15 or later
Built: $(date)
EOF

        mkdir -p "$RELEASE_DIR"
        cd /tmp
        zip -r "$RELEASE_DIR/${RELEASE_NAME}.zip" "$RELEASE_NAME" -x "*.DS_Store"
        rm -rf "$TEMP_DIR"

        echo -e "${GREEN}✓ Release package created: $RELEASE_DIR/${RELEASE_NAME}.zip${NC}"
        ;;
esac

echo ""
echo -e "${GREEN}Done!${NC}"
