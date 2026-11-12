import geopandas as gpd
import pandas as pd
from config import GDB, WORK, TAB, CRS

pred = gpd.read_file(GDB, layer='pred_sidewalk').to_crs(CRS)
truth = gpd.read_file(GDB, layer='drcog_sw_poly').to_crs(CRS)
cities = gpd.read_file(GDB, layer='study_area_city').to_crs(CRS).dissolve('NAME').reset_index()

p_all = pred.geometry.buffer(0).union_all()
t_all = truth.geometry.buffer(0).union_all()


def scores(p, t, name):
    inter = p.intersection(t).area
    P, T = p.area, t.area
    precision, recall = inter / P, inter / T
    return {
        'area': name,
        'predicted_m2': round(P), 'drcog_m2': round(T), 'overlap_m2': round(inter),
        'iou': inter / (P + T - inter),
        'precision': precision, 'recall': recall,
        'f1': 2 * precision * recall / (precision + recall),
        # tolerant version: a 1 m margin forgives small shifts between the two layers
        'precision_1m': p.intersection(t.buffer(1)).area / P,
        'recall_1m': t.intersection(p.buffer(1)).area / T,
    }


rows = [scores(p_all, t_all, 'Whole study area')]
for _, city in cities.iterrows():
    rows.append(scores(p_all.intersection(city.geometry), t_all.intersection(city.geometry), city['NAME']))

table = pd.DataFrame(rows).round(3)
table.to_csv(TAB / 'accuracy.csv', index=False)
print(table.to_string(index=False))

# error layers for the map: pieces at least 5 m2 that the other layer does not cover, even with a 1 m margin
errors = WORK / 'accuracy_errors.gpkg'
false_pos = gpd.GeoDataFrame(geometry=[p_all.difference(t_all.buffer(1))], crs=CRS).explode(index_parts=False)
false_neg = gpd.GeoDataFrame(geometry=[t_all.difference(p_all.buffer(1))], crs=CRS).explode(index_parts=False)
false_pos = false_pos[false_pos.area >= 5].assign(area_m2=lambda d: d.area.round(1))
false_neg = false_neg[false_neg.area >= 5].assign(area_m2=lambda d: d.area.round(1))
false_pos.to_file(errors, layer='false_positive', driver='GPKG')
false_neg.to_file(errors, layer='false_negative', driver='GPKG')
print(len(false_pos), 'false positive pieces and', len(false_neg), 'false negative pieces saved to', errors)