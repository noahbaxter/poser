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
# - tag:     Sub-group tag for visual grouping on the ring (e.g. "kick")
MICS = {
    # Shure
    "sm57":       {"name": "SM57",       "groups": ["Drum", "Guit"],                 "rh_id": "0006", "atk_csv": "shure_sm57.csv"},
    "sm58":       {"name": "SM58",       "groups": ["Vox"],                          "rh_id": "0253", "atk_csv": "shure_sm58.csv"},
    "sm7b":       {"name": "SM7B",       "groups": ["Vox"],                          "rh_id": "0255", "atk_csv": "shure_sm7b.csv"},
    "sm81":       {"name": "SM81",       "groups": ["Drum", "Inst"],                 "rh_id": "0242"},
    "beta-52a":   {"name": "52A",        "groups": ["Kick"],                         "rh_id": "0219"},
    "beta-91a":   {"name": "91A",        "groups": ["Kick"],                         "rh_id": "1094"},
    # Sennheiser
    "md421":      {"name": "MD421",      "groups": ["Drum", "Guit"],                 "rh_id": "0552"},
    "e602":       {"name": "e602",       "groups": ["Kick"],                         "rh_id": "1340"},
    "e604":       {"name": "e604",       "groups": ["Drum"],                         "rh_id": "1394"},
    "e904":       {"name": "e904",       "groups": ["Drum"],                         "rh_id": "1320"},
    "e906":       {"name": "e906",       "groups": ["Guit"],                         "rh_id": "1184"},
    # Beyerdynamic
    "m88-tg":     {"name": "M88",        "groups": ["Drum", "Vox", "Kick", "Guit"],  "rh_id": "1009"},
    # Electro-Voice
    "re20":       {"name": "RE20",       "groups": ["Vox", "Kick", "Guit"],          "rh_id": "0417"},
    # AKG
    "c12":        {"name": "C12",        "groups": ["Vox", "Inst"],                  "rh_id": "0912"},
    "c414":       {"name": "C414",       "groups": ["Vox", "Drum", "Inst"],          "rh_id": "0307", "atk_csv": "akg_c414_xlii.csv"},
    "c451b":      {"name": "C451",       "groups": ["Drum", "Inst"],                 "rh_id": "0323"},
    "d112":       {"name": "D112",       "groups": ["Kick"],                         "rh_id": "0335"},
    "d12":        {"name": "D12",        "groups": ["Kick"],                         "rh_id": "1550"},
    "d2":         {"name": "D2",         "groups": ["Drum"],                         "rh_id": "0479"},
    "d4":         {"name": "D4",         "groups": ["Drum"],                         "rh_id": "0478"},
    "d6":         {"name": "D6",         "groups": ["Kick"],                         "rh_id": "0567"},
    # Neumann
    "u87":        {"name": "U87",        "groups": ["Vox", "Inst"],                  "rh_id": "0860", "atk_csv": "neumann_u87.csv"},
    "m147":       {"name": "M147",       "groups": ["Vox", "Inst"],                  "rh_id": "1215"},
    "km184":      {"name": "KM184",      "groups": ["Inst"],                         "rh_id": "1091"},
    # Royer
    "r121":       {"name": "R121",       "groups": ["Guit"],                         "rh_id": "0443"},
    # AEA
    "r84":        {"name": "R84",        "groups": ["Guit", "Inst"],                 "rh_id": "0429"},
    # Coles
    "coles-4038": {"name": "4038",       "groups": ["Guit", "Inst"],                 "rh_id": "0701"},
}

# Group display order
MIC_GROUPS = ["Kick", "Drum", "Vox", "Guit", "Inst"]
