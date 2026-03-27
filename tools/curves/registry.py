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
# - groups:  List of UI groups this mic belongs to (can appear in multiple)
# - rh_id:   RecordingHacks numeric ID (for downloading source graph)
# - atk_csv: ATK lab measurement CSV (optional, takes priority over digitized)
MICS = {
    "sm57":       {"name": "SM57",       "groups": ["Drum", "Inst"],   "rh_id": "0006", "atk_csv": "shure_sm57.csv"},
    "sm58":       {"name": "SM58",       "groups": ["Vox"],           "rh_id": "0253", "atk_csv": "shure_sm58.csv"},
    "sm7b":       {"name": "SM7B",       "groups": ["Vox"],           "rh_id": "0255", "atk_csv": "shure_sm7b.csv"},
    "c414":       {"name": "C414",       "groups": ["Vox", "Drum"],    "rh_id": "0307", "atk_csv": "akg_c414_xlii.csv"},
    "u87":        {"name": "U87",        "groups": ["Vox"],           "rh_id": "0860", "atk_csv": "neumann_u87.csv"},
    "beta-52a":   {"name": "52A",         "groups": ["Drum"],          "rh_id": "0219", "tag": "kick"},
    "c451b":      {"name": "C451 B",     "groups": ["Inst"],          "rh_id": "0323"},
    "d112":       {"name": "D112",       "groups": ["Drum"],          "rh_id": "0335", "tag": "kick"},
    "re20":       {"name": "RE20",       "groups": ["Vox"],           "rh_id": "0417"},
    "r84":        {"name": "R84",        "groups": ["Inst"],          "rh_id": "0429"},
    "md421":      {"name": "MD421",      "groups": ["Drum", "Inst"],  "rh_id": "0552"},
    "d6":         {"name": "D6",         "groups": ["Drum"],          "rh_id": "0567", "tag": "kick"},
    "coles-4038": {"name": "Coles 4038", "groups": ["Inst"],          "rh_id": "0701"},
    "m88-tg":     {"name": "M88 TG",     "groups": ["Inst"],          "rh_id": "1009"},
    "km184":      {"name": "KM184",      "groups": ["Inst"],          "rh_id": "1091"},
    "e906":       {"name": "e906",       "groups": ["Inst"],          "rh_id": "1184"},
}

# Group display order
MIC_GROUPS = ["Drum", "Vox", "Inst"]
