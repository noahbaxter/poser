"""Centralized path constants for curve data directories."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DATA = REPO / "data"

# Source-grouped directories
DATASHEET_ORIGINALS = DATA / "curves" / "datasheet" / "originals"
DATASHEET_MASKS     = DATA / "curves" / "datasheet" / "masks"
DATASHEET_GUIDES    = DATA / "curves" / "datasheet" / "guides"
DATASHEET_CURVES    = DATA / "curves" / "datasheet" / "curves"

RH_ORIGINALS = DATA / "curves" / "recordinghacks" / "originals"
RH_MASKS     = DATA / "curves" / "recordinghacks" / "masks"
RH_CURVES    = DATA / "curves" / "recordinghacks" / "curves"

ATK_ORIGINALS = DATA / "curves" / "atk" / "originals"
ATK_CURVES    = DATA / "curves" / "atk" / "curves"

COMPILED = DATA / "curves" / "compiled"
COMPONENTS_JSON = COMPILED / "extracted_components.json"
HEADER_OUTPUT = REPO / "src" / "CurveData.h"

# IR (unchanged)
IR_DIR = DATA / "ir"


# Slug-based path helpers
def datasheet_original(slug): return DATASHEET_ORIGINALS / f"{slug}.png"
def datasheet_mask(slug):     return DATASHEET_MASKS / f"{slug}.png"
def datasheet_guide(slug):    return DATASHEET_GUIDES / f"{slug}.json"
def datasheet_curve(slug):    return DATASHEET_CURVES / f"{slug}.json"
def rh_original(slug):        return RH_ORIGINALS / f"{slug}.png"
def rh_mask(slug):             return RH_MASKS / f"{slug}.png"
def rh_curve(slug):            return RH_CURVES / f"{slug}.json"
def atk_original(slug):       return ATK_ORIGINALS / f"{slug}.csv"
def atk_curve(slug):          return ATK_CURVES / f"{slug}.json"
def compiled_curve(slug):     return COMPILED / f"{slug}.json"


def find_curve(slug):
    """Find the best available digitized curve JSON for a slug.

    Priority: ATK > datasheet > recordinghacks.
    Returns the Path if found, None otherwise.
    """
    for path in [atk_curve(slug), datasheet_curve(slug), rh_curve(slug)]:
        if path.exists():
            return path
    return None


def all_curves(slug):
    """Return dict of {source: path} for all available curve JSONs."""
    result = {}
    for source, path in [("atk", atk_curve(slug)),
                         ("datasheet", datasheet_curve(slug)),
                         ("recordinghacks", rh_curve(slug))]:
        if path.exists():
            result[source] = path
    return result
