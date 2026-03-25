import pytest
import sys
import os
from pathlib import Path

TESTS_DIR = Path(__file__).parent
sys.path.insert(0, str(TESTS_DIR))  # Allow subdirectories to import utils
PROJECT_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"


def get_platform_plugin_path():
    """Get the default plugin path for the current platform."""
    env_path = os.environ.get("AUDIOPLUGIN_VST3_PATH")
    if env_path:
        return Path(env_path)

    if sys.platform == "darwin":
        return Path.home() / "Library/Audio/Plug-Ins/VST3/AudioPlugin.vst3"
    elif sys.platform == "win32":
        return Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Common Files/VST3/AudioPlugin.vst3"
    else:  # Linux
        return Path.home() / ".vst3/AudioPlugin.vst3"


def _skip_pedalboard_on_windows():
    """Skip test if pedalboard can't load VST3 on this platform."""
    if sys.platform == "win32":
        pytest.skip("pedalboard VST3 loading not supported on Windows CI")


@pytest.fixture
def plugin_path():
    """Path to the installed VST3 plugin."""
    _skip_pedalboard_on_windows()
    path = get_platform_plugin_path()
    if not path.exists():
        pytest.skip(f"Plugin not found at {path}. Run ./scripts/build.sh first.")
    return str(path)


@pytest.fixture
def unit_tests_binary():
    """Path to the C++ unit tests binary."""
    if sys.platform == "win32":
        path = TESTS_DIR / "unit/build/Release/unit_tests.exe"
    else:
        path = TESTS_DIR / "unit/build/unit_tests_artefacts/Release/unit_tests"
    if not path.exists():
        pytest.skip(f"Unit tests binary not found at {path}. Build with cmake first.")
    return str(path)


@pytest.fixture
def pluginval_path():
    """Path to pluginval executable."""
    import shutil

    # First check if it's in PATH
    pluginval = shutil.which("pluginval")
    if pluginval:
        return pluginval

    # Check common locations
    if sys.platform == "darwin":
        paths = [
            "/Applications/pluginval.app/Contents/MacOS/pluginval",
            "/usr/local/bin/pluginval.app/Contents/MacOS/pluginval",
            "/usr/local/bin/pluginval",
            Path.home() / "bin/pluginval",
        ]
    elif sys.platform == "win32":
        paths = [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "pluginval/pluginval.exe",
            Path.home() / "bin/pluginval.exe",
        ]
    else:  # Linux
        paths = [
            "/usr/local/bin/pluginval",
            Path.home() / "bin/pluginval",
        ]

    for p in paths:
        if Path(p).exists():
            return str(p)
    pytest.skip("pluginval not found. Install from https://github.com/Tracktion/pluginval")


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return FIXTURES_DIR
