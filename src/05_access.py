import pandas as pd
import geopandas as gpd
from config import GDB, WORK, TAB, CRS

RADIUS = 400    # meters, about a quarter mile

sides = gpd.read_file(WORK / 'gaps.gpkg', layer='sides')
sides['geometry'] = sides.geometry.interpolate(0.5, normalized=True)     # one point per street side
area = gpd.read_file(GDB, layer='study_area').to_crs(CRS).geometry.union_all()
cities = gpd.read_file(GDB, layer='study_area_city').to_crs(CRS).dissolve('NAME').reset_index()[['NAME', 'geometry']]


def first_column(df, options):
    for name in options:
        if name in df.columns:
            return name
    return df.columns[0]


def access(layer, name_options, kind):
    pts = gpd.read_file(GDB, layer=layer).to_crs(CRS).reset_index(drop=True)
    name_col = first_column(pts, name_options)
    city = gpd.sjoin(pts[['geometry']], cities, predicate='within', how='left')['NAME']
    pts['city'] = city[~city.index.duplicated()].reindex(pts.index)
    rows = []
    for i, p in pts.iterrows():
        circle = p.geometry.buffer(RADIUS)
        near = sides[sides.geometry.within(circle)]
        total = near['length_m'].sum()
        if total == 0:
            continue
        rows.append({
            'kind': kind, 'name': p[name_col], 'city': p['city'],
            'street_sides_km': round(total / 1000, 2),
            'gap_share_model': round(near.loc[~near['has_pred'], 'length_m'].sum() / total, 3),
            'gap_share_drcog': round(near.loc[~near['has_drcog'], 'length_m'].sum() / total, 3),
            # near the edge of the study area part of the circle is not measured
            'circle_inside_study_area': round(circle.intersection(area).area / circle.area, 2),
        })
    return pd.DataFrame(rows)


schools = access('schools_study_area', ['NAME', 'SCH_NAME', 'name'], 'school')
stops = access('stops_study_area', ['stop_name', 'STOP_NAME', 'name'], 'stop')
schools.sort_values('gap_share_model', ascending=False).to_csv(TAB / 'access_schools.csv', index=False)
stops.sort_values('gap_share_model', ascending=False).to_csv(TAB / 'access_stops.csv', index=False)

overall_model = sides.loc[~sides['has_pred'], 'length_m'].sum() / sides['length_m'].sum()
overall_drcog = sides.loc[~sides['has_drcog'], 'length_m'].sum() / sides['length_m'].sum()
both = pd.concat([schools, stops])
summary = both.groupby(['kind', 'city'])[['gap_share_model', 'gap_share_drcog']].agg(['mean', 'max', 'count']).round(3)
summary.to_csv(TAB / 'access_summary.csv')
print(f'Whole study area: gap share {overall_model:.1%} (model), {overall_drcog:.1%} (DRCOG)\n')
print(summary, '\n')
print('Ten places with the most gaps around them (model):')
print(both.sort_values('gap_share_model', ascending=False).head(10).to_string(index=False))