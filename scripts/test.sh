#!/bin/bash
# Test runner for AudioPlugin
#
# Usage:
#   ./scripts/test.sh              # Run all tests (unit + integration + compliance)
#   ./scripts/test.sh -v           # Run all tests with verbose output
#   ./scripts/test.sh unit         # Run only unit tests
#   ./scripts/test.sh integration  # Run only integration tests
#   ./scripts/test.sh compliance   # Run only compliance tests
#   ./scripts/test.sh validate     # Run pluginval (default strictness 10)
#   ./scripts/test.sh validate 5   # Run pluginval at strictness 5

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/_common.sh"

# Parse arguments
VERBOSE=""
TEST_TYPE="all"
VALIDATE_STRICTNESS=""

for arg in "$@"; do
    case $arg in
        -v|--verbose)
            VERBOSE="-v"
            ;;
        unit|Unit|UNIT)
            TEST_TYPE="unit"
            ;;
        integration|Integration|INTEGRATION)
            TEST_TYPE="integration"
            ;;
        gaincomp|gain-comp|GAINCOMP)
            TEST_TYPE="gaincomp"
            ;;
        compliance|Compliance|COMPLIANCE)
            TEST_TYPE="compliance"
            ;;
        validate|Validate|VALIDATE)
            TEST_TYPE="validate"
            ;;
        all|All|ALL)
            TEST_TYPE="all"
            ;;
        [0-9]|[0-9][0-9])
            VALIDATE_STRICTNESS="$arg"
            ;;
        --help|-h)
            echo "Usage: ./scripts/test.sh [options] [test_type]"
            echo ""
            echo "Test types:"
            echo "  all          Run unit + integration + compliance (default)"
            echo "  unit         Run C++ unit tests only"
            echo "  integration  Run Python integration tests only"
            echo "  compliance   Run pluginval compliance tests only"
            echo "  validate     Run pluginval directly (default strictness 10)"
            echo "  validate 5   Run pluginval at specific strictness level"
            echo ""
            echo "Options:"
            echo "  -v, --verbose  Verbose output"
            exit 0
            ;;
    esac
done

echo -e "${YELLOW}=== Poser Test Runner ===${NC}"
echo "Test type: $TEST_TYPE"

# Ensure venv is set up
ensure_venv

# Check if plugin is built
PLUGIN_PATH="$HOME/Library/Audio/Plug-Ins/VST3/Poser.vst3"
if [ ! -d "$PLUGIN_PATH" ]; then
    echo -e "${RED}Plugin not found at $PLUGIN_PATH${NC}"
    echo "Run ./scripts/build.sh first"
    exit 1
fi

run_unit_tests() {
    echo -e "\n${BLUE}=== Running C++ Unit Tests ===${NC}"
    echo -e "${YELLOW}Building unit tests...${NC}"
    "$TESTS_DIR/unit/build.sh"
    pytest "$TESTS_DIR/unit" $VERBOSE
}

run_integration_tests() {
    echo -e "\n${BLUE}=== Running Integration Tests ===${NC}"
    pytest "$TESTS_DIR/integration" $VERBOSE
}

run_compliance_tests() {
    echo -e "\n${BLUE}=== Running Compliance Tests ===${NC}"
    pytest "$TESTS_DIR/compliance" $VERBOSE
}

run_gaincomp_test() {
    echo -e "\n${BLUE}=== Running Gain Compensation Test ===${NC}"
    python3 "$PROJECT_ROOT/tests/test_gain_comp.py"
}

run_validate() {
    local strictness="${VALIDATE_STRICTNESS:-10}"
    echo -e "\n${BLUE}=== Running pluginval (strictness $strictness) ===${NC}"

    local pluginval=""
    if command -v pluginval &> /dev/null; then
        pluginval="pluginval"
    elif [[ -x "/Applications/pluginval.app/Contents/MacOS/pluginval" ]]; then
        pluginval="/Applications/pluginval.app/Contents/MacOS/pluginval"
    elif [[ -x "/usr/local/bin/pluginval" ]]; then
        pluginval="/usr/local/bin/pluginval"
    else
        echo -e "${RED}pluginval not found${NC}"
        echo "Install from: https://github.com/Tracktion/pluginval"
        exit 1
    fi

    "$pluginval" --strictness-level "$strictness" --validate "$PLUGIN_PATH"
}

case "$TEST_TYPE" in
    unit)
        run_unit_tests
        ;;
    integration)
        run_integration_tests
        ;;
    compliance)
        run_compliance_tests
        ;;
    gaincomp)
        run_gaincomp_test
        ;;
    validate)
        run_validate
        ;;
    all)
        run_gaincomp_test
        run_unit_tests
        run_integration_tests
        run_compliance_tests
        ;;
esac

echo ""
echo -e "${GREEN}All tests passed!${NC}"
