import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from config import GDB, RAW, WORK, TAB, FIG, CRS

MIN_KM = 1.0        # ignore block groups with less than this length of street sides inside the study area

shp = next(RAW.rglob('tl_2022_08_bg.shp'))
bg = gpd.read_file(shp).to_crs(CRS)[['GEOID', 'geometry']]
acs = pd.read_csv(RAW / 'census' / 'acs_2022_bg.csv', dtype={'GEOID': str})
acs['GEOID'] = acs['GEOID'].str.zfill(12)
bg = bg.merge(acs[['GEOID', 'B19013_001E', 'B01003_001E', 'pct_no_vehicle']], on='GEOID', how='left')
bg = bg.rename(columns={'B19013_001E': 'median_income', 'B01003_001E': 'population'})

area = gpd.read_file(GDB, layer='study_area').to_crs(CRS)
bg = bg[bg.intersects(area.geometry.union_all())].copy()
bg['share_inside'] = (bg.intersection(area.geometry.union_all()).area / bg.area).round(2)

sides = gpd.read_file(WORK / 'gaps.gpkg', layer='sides')
sides['geometry'] = sides.geometry.interpolate(0.5, normalized=True)
joined = gpd.sjoin(sides, bg[['GEOID', 'geometry']], predicate='within', how='inner')

joined['gap_model_m'] = joined['length_m'].where(~joined['has_pred'], 0)
joined['gap_drcog_m'] = joined['length_m'].where(~joined['has_drcog'], 0)
sums = joined.groupby('GEOID')[['length_m', 'gap_model_m', 'gap_drcog_m']].sum()
stats = pd.DataFrame({
    'street_sides_km': sums['length_m'] / 1000,
    'gap_share_model': sums['gap_model_m'] / sums['length_m'],
    'gap_share_drcog': sums['gap_drcog_m'] / sums['length_m'],
}).round(3).reset_index()
bg = bg.merge(stats, on='GEOID', how='left')
used = bg[bg['street_sides_km'] >= MIN_KM].copy()
used = used[used['share_inside'] >= 0.25]

used.drop(columns='geometry').to_csv(TAB / 'census_bg.csv', index=False)
used.to_file(WORK / 'census_bg.gpkg', driver='GPKG')
print(len(used), 'block groups used\n')

rows = []
for src in ('gap_share_model', 'gap_share_drcog'):
    for var in ('median_income', 'pct_no_vehicle'):
        d = used[[src, var]].dropna()
        rho, p = spearmanr(d[src], d[var]) if len(d) >= 4 else (float('nan'), float('nan'))
        rows.append({'gaps_from': src, 'compared_with': var, 'block_groups': len(d), 'spearman_rho': round(rho, 2), 'p_value': round(p, 3)})
corr = pd.DataFrame(rows)
corr.to_csv(TAB / 'census_correlation.csv', index=False)
print(corr.to_string(index=False))

fig, axes = plt.subplots(1, 2, figsize=(9, 4))
axes[0].scatter(used['median_income'] / 1000, used['gap_share_drcog'] * 100, color='#d95f02')
axes[0].set_xlabel('Median household income ($ thousand)')
axes[1].scatter(used['pct_no_vehicle'] * 100, used['gap_share_drcog'] * 100, color='#d95f02')
axes[1].set_xlabel('Households with no vehicle (%)')
for ax in axes:
    ax.set_ylabel('Street sides with no sidewalk (%)')
fig.suptitle('Sidewalk gaps and neighborhood characteristics, by block group')
plt.tight_layout()
plt.savefig(FIG / 'fig07_census.png', dpi=300, bbox_inches='tight')
print('Chart saved to', FIG / 'fig07_census.png')