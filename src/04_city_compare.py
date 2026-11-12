import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from scipy.stats import chi2_contingency
from config import GDB, WORK, TAB, FIG, CRS

sides = gpd.read_file(WORK / 'gaps.gpkg', layer='sides')
sides = sides[sides['city'].notna()]
segs = gpd.read_file(WORK / 'gaps.gpkg', layer='segments')
cities = gpd.read_file(GDB, layer='study_area_city').to_crs(CRS).dissolve('NAME')
area_km2 = cities.area / 1e6

# 1. street sides: how much of each city's street frontage has a sidewalk
rows = []
for src, label in (('pred', 'Model'), ('drcog', 'DRCOG')):
    for city, d in sides.groupby('city'):
        total = d['length_m'].sum() / 1000
        gap = d.loc[~d[f'has_{src}'], 'length_m'].sum() / 1000
        rows.append({'source': label, 'city': city, 'street_sides_km': round(total, 1), 'gap_km': round(gap, 1),
                     'gap_share': round(gap / total, 3), 'gap_km_per_km2': round(gap / area_km2[city], 2),
                     'sides_total': len(d), 'sides_gap': int((~d[f'has_{src}']).sum())})
table = pd.DataFrame(rows)
table.to_csv(TAB / 'city_compare.csv', index=False)
print(table.to_string(index=False), '\n')

# 2. is the difference between the cities bigger than chance? (rough guide only)
for src, label in (('pred', 'Model'), ('drcog', 'DRCOG')):
    counts = pd.crosstab(sides['city'], sides[f'has_{src}'])
    chi2, p, _, _ = chi2_contingency(counts)
    print(f'{label}: chi-square = {chi2:.1f}, p = {p:.4f}')

# 3. street segments: both sides, one side or none (streets on the city line are left out)
inside = segs[segs['city'].notna() & ~segs['on_city_line']]
classes = ['both sides', 'one side', 'no sidewalk']
seg_rows = []
for src, label in (('pred', 'Model'), ('drcog', 'DRCOG')):
    share = inside.groupby(['city', f'class_{src}'])['length_m'].sum().unstack(fill_value=0)
    share = share.div(share.sum(axis=1), axis=0).reindex(columns=classes, fill_value=0)
    seg_rows.append(share.round(3).assign(source=label).reset_index())
seg_table = pd.concat(seg_rows)[['source', 'city'] + classes]
seg_table.to_csv(TAB / 'city_compare_segments.csv', index=False)
print('\nShare of street length by class:\n', seg_table.to_string(index=False))

# 4. chart for the report
fig, ax = plt.subplots(figsize=(6, 4))
pivot = table.pivot(index='city', columns='source', values='gap_share') * 100
pivot.plot.bar(ax=ax, rot=0, color=['#8a8a8a', '#d95f02'])
ax.set_ylabel('Street sides with no sidewalk (%)')
ax.set_xlabel('')
ax.set_title('Sidewalk gaps by city')
for bars in ax.containers:
    ax.bar_label(bars, fmt='%.1f', padding=2)
plt.tight_layout()
plt.savefig(FIG / 'fig05_city_compare.png', dpi=300, bbox_inches='tight')
print('\nChart saved to', FIG / 'fig05_city_compare.png')