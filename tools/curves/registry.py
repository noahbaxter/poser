"""Mic registry — the one file to edit when adding or removing mics.

To add a mic:
  1. Add an entry to MICS below
  2. Run: python3 tools/curves/manage.py prepare
  3. Edit masks if needed (multiple curves)
  4. Run: python3 tools/curves/manage.py build

To remove a mic:
  Delete its entry from MICS.
"""

# slug → mic info
# - name:    Display name shown in the plugin UI
# - rh_id:   RecordingHacks numeric ID (for downloading source graph)
# - atk_csv: ATK lab measurement CSV (optional, takes priority over digitized)
MICS = {
    "sm57":       {"name": "SM57",       "rh_id": "0006", "atk_csv": "shure_sm57.csv"},
    "sm58":       {"name": "SM58",       "rh_id": "0253", "atk_csv": "shure_sm58.csv"},
    "sm7b":       {"name": "SM7B",       "rh_id": "0255", "atk_csv": "shure_sm7b.csv"},
    "c414":       {"name": "C414",       "rh_id": "0307", "atk_csv": "akg_c414_xlii.csv"},
    "u87":        {"name": "U87",        "rh_id": "0860", "atk_csv": "neumann_u87.csv"},
    "beta-52a":   {"name": "Beta 52A",   "rh_id": "0219"},
    "c451b":      {"name": "C451 B",     "rh_id": "0323"},
    "d112":       {"name": "D112",       "rh_id": "0335"},
    "re20":       {"name": "RE20",       "rh_id": "0417"},
    "r84":        {"name": "R84",        "rh_id": "0429"},
    "md421":      {"name": "MD421",      "rh_id": "0552"},
    "d6":         {"name": "D6",         "rh_id": "0567"},
    "coles-4038": {"name": "Coles 4038", "rh_id": "0701"},
    "m88-tg":     {"name": "M88 TG",     "rh_id": "1009"},
    "km184":      {"name": "KM184",      "rh_id": "1091"},
    "e906":       {"name": "e906",       "rh_id": "1184"},
}
