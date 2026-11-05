import sys
import geopandas, shapely, osmnx, sklearn, pyogrio, rasterio, pandas
from config import ROOT, GDB

print('Python  ', sys.version.split()[0])
print('Using   ', sys.executable)
for m in (geopandas, shapely, osmnx, sklearn, pyogrio, rasterio, pandas):
    print(f'{m.__name__:<10}', m.__version__)
print('Project ', ROOT)
print('ArcGIS geodatabase found' if GDB.exists() else 'ArcGIS geodatabase not created yet (Step H)')