from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
WORK = ROOT / 'data' / 'working'
GDB = WORK / 'sidewalk_arcgis' / 'sidewalk_arcgis.gdb'   # made by ArcGIS Pro in Step H
FIG = ROOT / 'outputs' / 'figures'
TAB = ROOT / 'outputs' / 'tables'

CRS = 26913          # NAD83 / UTM zone 13N, meters
CORRIDOR = 20        # meters searched on each side of a street
SEG_LEN = 30         # meters per street segment
MIN_AREA_PER_M = 0.75
SEED = 42            # fixed seed for the Street View sample

for p in (RAW, WORK, FIG, TAB):
    p.mkdir(parents=True, exist_ok=True)