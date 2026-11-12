import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point
from shapely.ops import substring
from sklearn.metrics import cohen_kappa_score
from config import GDB, WORK, TAB, CRS, SEG_LEN, CORRIDOR, PROBE_STEP, MIN_HIT

roads = gpd.read_file(WORK / 'roads_study.gpkg').to_crs(CRS).explode(index_parts=False).reset_index(drop=True)
pred = gpd.read_file(GDB, layer='pred_sidewalk').to_crs(CRS)[['geometry']]
drcog = gpd.read_file(GDB, layer='drcog_sw_poly').to_crs(CRS)[['geometry']]
cities = gpd.read_file(GDB, layer='study_area_city').to_crs(CRS).dissolve('NAME').reset_index()[['NAME', 'geometry']]


def build(corridor):
    """Cut streets into short segments and draw probe lines out to each side."""
    segs, sides, probes = [], [], []
    seg_id = 0
    for _, road in roads.iterrows():
        line = road.geometry
        if line is None or line.length < 10:
            continue
        n = max(1, round(line.length / SEG_LEN))
        for k in range(n):
            seg = substring(line, k * line.length / n, (k + 1) * line.length / n)
            segs.append({'seg_id': seg_id, 'name': road.get('name'), 'highway': road.get('highway'),
                         'length_m': seg.length, 'geometry': seg})
            for d in np.arange(PROBE_STEP / 2, seg.length, PROBE_STEP):
                p = seg.interpolate(d)
                a, b = seg.interpolate(max(d - 0.5, 0)), seg.interpolate(min(d + 0.5, seg.length))
                tx, ty = b.x - a.x, b.y - a.y
                norm = (tx ** 2 + ty ** 2) ** 0.5
                if norm == 0:
                    continue
                nx, ny = -ty / norm, tx / norm          # points to the left of the street
                for side, s in (('left', 1), ('right', -1)):
                    probes.append({'seg_id': seg_id, 'side': side, 'geometry': LineString(
                        [(p.x + s * nx * 2, p.y + s * ny * 2), (p.x + s * nx * corridor, p.y + s * ny * corridor)])})
            m = seg.interpolate(0.5, normalized=True)
            a, b = seg.interpolate(0.45, normalized=True), seg.interpolate(0.55, normalized=True)
            tx, ty = b.x - a.x, b.y - a.y
            norm = (tx ** 2 + ty ** 2) ** 0.5 or 1
            nx, ny = -ty / norm, tx / norm
            for side, s in (('left', 1), ('right', -1)):
                sides.append({'seg_id': seg_id, 'side': side, 'length_m': seg.length,
                              'geometry': Point(m.x + s * nx * 8, m.y + s * ny * 8)})
            seg_id += 1
    return (gpd.GeoDataFrame(segs, crs=CRS), gpd.GeoDataFrame(sides, crs=CRS), gpd.GeoDataFrame(probes, crs=CRS))


def hit_share(probes, sidewalks):
    """Share of a side's probe lines that touch a sidewalk polygon."""
    probes = probes.reset_index(drop=True)
    hit_ids = gpd.sjoin(probes, sidewalks, predicate='intersects').index.unique()
    probes['hit'] = probes.index.isin(hit_ids)
    return probes.groupby(['seg_id', 'side'])['hit'].mean()


def classify(corridor, min_hit):
    segs, sides, probes = build(corridor)
    sides = sides.merge(hit_share(probes, pred).rename('share_pred').reset_index(), on=['seg_id', 'side'], how='left')
    sides = sides.merge(hit_share(probes, drcog).rename('share_drcog').reset_index(), on=['seg_id', 'side'], how='left')
    sides[['share_pred', 'share_drcog']] = sides[['share_pred', 'share_drcog']].fillna(0)
    sides['has_pred'] = sides['share_pred'] >= min_hit
    sides['has_drcog'] = sides['share_drcog'] >= min_hit
    city = gpd.sjoin(sides[['geometry']], cities, predicate='within', how='left')['NAME']
    sides['city'] = city[~city.index.duplicated()].reindex(sides.index)
    return segs, sides


segs, sides = classify(CORRIDOR, MIN_HIT)

# one row per street segment: how many of its two sides have a sidewalk
labels = {2: 'both sides', 1: 'one side', 0: 'no sidewalk'}
for src in ('pred', 'drcog'):
    count = sides.groupby('seg_id')[f'has_{src}'].sum()
    segs[f'sides_{src}'] = segs['seg_id'].map(count).fillna(0).astype(int)
    segs[f'class_{src}'] = segs[f'sides_{src}'].map(labels)
mid = gpd.GeoDataFrame(segs[['seg_id']], geometry=segs.geometry.interpolate(0.5, normalized=True), crs=CRS)
city = gpd.sjoin(mid, cities, predicate='within', how='left')['NAME']
segs['city'] = city[~city.index.duplicated()].reindex(segs.index)
both = sides.groupby('seg_id')['city'].nunique()
segs['on_city_line'] = segs['seg_id'].map(both).fillna(1) > 1

# for maps, draw each side as a line 6 m to the left or right of the street
lines = segs.set_index('seg_id').geometry
def side_line(row):
    off = lines[row['seg_id']].offset_curve(6 if row['side'] == 'left' else -6)
    return off if (off is not None and not off.is_empty) else lines[row['seg_id']]
sides_out = sides.copy()
sides_out['geometry'] = sides_out.apply(side_line, axis=1)
sides_out['status'] = np.select(
    [sides_out.has_pred & sides_out.has_drcog, ~sides_out.has_pred & ~sides_out.has_drcog, sides_out.has_pred],
    ['sidewalk in both', 'gap in both', 'model only'], default='DRCOG only')

out = WORK / 'gaps.gpkg'
segs.to_file(out, layer='segments', driver='GPKG')
sides_out.to_file(out, layer='sides', driver='GPKG')

# agreement between the model and DRCOG, side by side
confusion = pd.crosstab(sides['has_drcog'].map({True: 'DRCOG: sidewalk', False: 'DRCOG: gap'}),
                        sides['has_pred'].map({True: 'Model: sidewalk', False: 'Model: gap'}))
confusion.to_csv(TAB / 'gap_agreement.csv')
kappa = cohen_kappa_score(sides['has_drcog'], sides['has_pred'])
agree = (sides['has_drcog'] == sides['has_pred']).mean()
print(confusion, '\n')
print(f'{len(segs)} segments, {len(sides)} street sides')
print(f'Agreement {agree:.1%}, Cohen kappa {kappa:.2f}')

# sensitivity: does the picture change with other reasonable settings?
rows = []
for corridor in (15, 20, 25):
    for min_hit in (0.5, 0.6, 0.7):
        _, s = classify(corridor, min_hit)
        for src in ('pred', 'drcog'):
            gap_km = s.loc[~s[f'has_{src}']].groupby('city')['length_m'].sum() / 1000
            all_km = s.groupby('city')['length_m'].sum() / 1000
            for c in all_km.index:
                rows.append({'corridor_m': corridor, 'min_hit': min_hit, 'source': src, 'city': c,
                             'gap_share': round(gap_km.get(c, 0) / all_km[c], 3)})
sens = pd.DataFrame(rows).pivot_table(index=['corridor_m', 'min_hit'], columns=['source', 'city'], values='gap_share')
sens.to_csv(TAB / 'gap_sensitivity.csv')
print('\nShare of street sides with no sidewalk, under different settings:\n', sens)