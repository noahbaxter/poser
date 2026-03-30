"""Terminal formatting helpers — ANSI colors with isatty() guard."""

import os
import sys

_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and os.environ.get("TERM") != "dumb"

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"


def _wrap(code, s):
    return f"{code}{s}{_RESET}" if _COLOR else str(s)


def bold(s):
    return _wrap(_BOLD, s)

def dim(s):
    return _wrap(_DIM, s)

def red(s):
    return _wrap(_RED, s)

def green(s):
    return _wrap(_GREEN, s)

def yellow(s):
    return _wrap(_YELLOW, s)

def cyan(s):
    return _wrap(_CYAN, s)

def ok(msg):
    return _wrap(_GREEN, f"  ✓ {msg}")

def warn(msg):
    return _wrap(_YELLOW, f"  ⚠ {msg}")

def err(msg):
    return _wrap(_RED, f"  ✗ {msg}")

def heading(msg):
    rule = "─" * 50
    return f"\n{_wrap(_BOLD, msg)}\n{_wrap(_DIM, rule)}" if _COLOR else f"\n{msg}\n{rule}"
