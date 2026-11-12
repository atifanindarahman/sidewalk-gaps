import math
import numpy as np
import pandas as pd
import geopandas as gpd
from config import WORK, TAB, CRS, SEED

PER_GROUP = 5      # 4 groups x 5 = 20 street sides; aim to finish at least 50

sides = gpd.read_file(WORK / 'gaps.gpkg', layer='sides')
segs = gpd.read_file(WORK / 'gaps.gpkg', layer='segments').set_index('seg_id')
sides = sides[sides['city'].notna() & (sides['length_m'] >= 20)].copy()
sides['model'] = np.where(sides['has_pred'], 'sidewalk', 'gap')

# the same number of street sides from each city and each model answer, drawn with a fixed seed
picks = pd.concat([g.sample(min(PER_GROUP, len(g)), random_state=SEED)
                   for _, g in sides.groupby(['city', 'model'])])
picks = picks.sample(frac=1, random_state=SEED).reset_index(drop=True)   # shuffle, so you cannot guess the group
picks['check_id'] = range(1, len(picks) + 1)

# where to stand (middle of the street) and which way to look (toward that side)
stand = gpd.GeoSeries(segs.loc[picks['seg_id']].geometry.interpolate(0.5, normalized=True).values, crs=CRS).to_crs(4326)
look = gpd.GeoSeries(picks.geometry.interpolate(0.5, normalized=True).values, crs=CRS).to_crs(4326)

def heading(a, b):
    lat1, lat2, dlon = math.radians(a.y), math.radians(b.y), math.radians(b.x - a.x)
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return round(math.degrees(math.atan2(y, x)) % 360)

picks['lat'] = [round(p.y, 6) for p in stand]
picks['lon'] = [round(p.x, 6) for p in stand]
picks['heading'] = [heading(a, b) for a, b in zip(stand, look)]
picks['street_view'] = [
    f'https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}&heading={h}&pitch=-10'
    for lat, lon, h in zip(picks['lat'], picks['lon'], picks['heading'])]
picks['street'] = segs.loc[picks['seg_id'], 'name'].values

# the sheet you fill in has no model or DRCOG answers, so your judgment stays independent
sheet = picks[['check_id', 'street', 'lat', 'lon', 'heading', 'street_view']].copy()
sheet['observed'] = ''          # type: yes, no, or unclear
sheet['capture_date'] = ''      # the month and year shown in Street View
sheet['notes'] = ''
sheet_path = TAB / 'streetview_sheet.csv'
if sheet_path.exists():
    raise SystemExit(f'{sheet_path} already exists. Delete or rename it first, so your typed answers are not overwritten.')
sheet.to_csv(sheet_path, index=False)

# the answer key stays closed until you have finished checking
picks[['check_id', 'seg_id', 'side', 'city', 'has_pred', 'has_drcog']].to_csv(TAB / 'streetview_key.csv', index=False)
picks[['check_id', 'geometry']].to_file(WORK / 'streetview_points.gpkg', driver='GPKG')
print(len(sheet), 'street sides to check. Open', sheet_path)
print(picks.groupby(['city', 'model']).size())