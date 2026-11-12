import geopandas as gpd
import osmnx as ox
from config import GDB, WORK, CRS

area = gpd.read_file(GDB, layer='study_area')
poly = area.to_crs(4326).geometry.union_all()

# street types that normally need sidewalks; no freeways, alleys or service roads
flt = '["highway"~"^(residential|tertiary|secondary|primary|unclassified|living_street)$"]'
G = ox.graph_from_polygon(poly, custom_filter=flt, retain_all=True, truncate_by_edge=True)

edges = ox.graph_to_gdfs(G, nodes=False).reset_index()
# each two-way street is stored twice (once per direction); keep one copy
edges['pair'] = [tuple(sorted((u, v))) + (k,) for u, v, k in zip(edges['u'], edges['v'], edges['key'])]
edges = edges.drop_duplicates('pair')[['osmid', 'name', 'highway', 'geometry']]
for col in ('osmid', 'name', 'highway'):
    edges[col] = edges[col].astype(str)

edges = gpd.clip(edges.to_crs(CRS), area.to_crs(CRS))
edges = edges[edges.geometry.type.isin(['LineString', 'MultiLineString'])]
edges.to_file(WORK / 'roads_study.gpkg', driver='GPKG')
print(len(edges), 'street segments,', round(edges.length.sum() / 1000, 1), 'km saved')