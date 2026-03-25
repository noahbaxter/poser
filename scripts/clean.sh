#!/bin/bash
# Clean build artifacts
#
# Usage:
#   ./scripts/clean.sh         # Clean build artifacts
#   ./scripts/clean.sh --all   # Also clean venv and caches

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/_common.sh"

CLEAN_ALL=false

for arg in "$@"; do
    case $arg in
        --all|-a)
            CLEAN_ALL=true
            ;;
        --help|-h)
            echo "Usage: ./scripts/clean.sh [options]"
            echo ""
            echo "Options:"
            echo "  --all, -a  Also clean venv and caches"
            exit 0
            ;;
    esac
done

echo -e "${YELLOW}=== Cleaning AudioPlugin ===${NC}"

# Clean main build directory
if [ -d "$BUILD_DIR" ]; then
    echo "Removing build/"
    rm -rf "$BUILD_DIR"
fi

# Clean unit test build
if [ -d "$TESTS_DIR/unit/build" ]; then
    echo "Removing tests/unit/build/"
    rm -rf "$TESTS_DIR/unit/build"
fi

# Clean test output
if [ -d "$TESTS_DIR/output" ]; then
    echo "Removing tests/output/"
    rm -rf "$TESTS_DIR/output"
fi

# Clean Python caches
echo "Removing __pycache__ directories"
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_ROOT" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true

# Clean release directory
if [ -d "$PROJECT_ROOT/releases" ]; then
    echo "Removing releases/"
    rm -rf "$PROJECT_ROOT/releases"
fi

if [ "$CLEAN_ALL" = true ]; then
    echo ""
    echo -e "${YELLOW}Deep clean...${NC}"

    # Clean venv
    if [ -d "$VENV_DIR" ]; then
        echo "Removing .venv/"
        rm -rf "$VENV_DIR"
    fi

    # Clean CMake user presets
    if [ -f "$PROJECT_ROOT/CMakeUserPresets.json" ]; then
        echo "Removing CMakeUserPresets.json"
        rm -f "$PROJECT_ROOT/CMakeUserPresets.json"
    fi
fi

echo ""
echo -e "${GREEN}✓ Clean complete${NC}"
