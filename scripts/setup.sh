#!/bin/bash
# Environment setup for AudioPlugin development
#
# Usage:
#   ./scripts/setup.sh              # Full setup
#   ./scripts/setup.sh --skip-venv  # Skip Python venv setup

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/_common.sh"

SKIP_VENV=false

for arg in "$@"; do
    case $arg in
        --skip-venv)
            SKIP_VENV=true
            ;;
        --help|-h)
            echo "Usage: ./scripts/setup.sh [options]"
            echo ""
            echo "Options:"
            echo "  --skip-venv  Skip Python virtual environment setup"
            exit 0
            ;;
    esac
done

echo -e "${YELLOW}=== Poser Environment Setup ===${NC}"

# Initialize JUCE submodule
echo -e "\n${BLUE}Checking JUCE submodule...${NC}"
if [ ! -f "$PROJECT_ROOT/third_party/JUCE/CMakeLists.txt" ]; then
    echo -e "${YELLOW}Initializing JUCE submodule...${NC}"
    git -C "$PROJECT_ROOT" submodule update --init --recursive
    echo -e "${GREEN}✓ JUCE submodule initialized${NC}"
else
    echo -e "${GREEN}✓ JUCE submodule already initialized${NC}"
fi

# Setup Python venv
if [ "$SKIP_VENV" = false ]; then
    echo -e "\n${BLUE}Setting up Python environment...${NC}"
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        python3 -m venv "$VENV_DIR"
    fi

    source "$VENV_DIR/bin/activate"

    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        echo -e "${YELLOW}Installing Python dependencies...${NC}"
        pip install -q --upgrade pip
        pip install -q -r "$PROJECT_ROOT/requirements.txt"
    fi
    echo -e "${GREEN}✓ Python environment ready${NC}"
fi

# Download pluginval for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "\n${BLUE}Checking pluginval...${NC}"
    PLUGINVAL_APP="/usr/local/bin/pluginval.app"

    if [ ! -d "$PLUGINVAL_APP" ]; then
        echo -e "${YELLOW}Downloading pluginval...${NC}"
        curl -L -o /tmp/pluginval.zip https://github.com/Tracktion/pluginval/releases/latest/download/pluginval_macOS.zip
        sudo unzip -o /tmp/pluginval.zip -d /usr/local/bin
        sudo chmod +x "$PLUGINVAL_APP/Contents/MacOS/pluginval"
        rm /tmp/pluginval.zip
        echo -e "${GREEN}✓ pluginval installed${NC}"
    else
        echo -e "${GREEN}✓ pluginval already installed${NC}"
    fi
fi

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Build: ./scripts/build.sh"
echo "  2. Test:  ./scripts/test.sh"
