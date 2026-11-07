import os
import pandas as pd
import requests
from config import RAW, ROOT

# 1. Read the Census API key from the .env file in the project folder
key = None
env_file = ROOT / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8-sig').splitlines():
        name, _, value = line.partition('=')
        if name.strip() == 'CENSUS_API_KEY':
            key = value.strip().strip('"').strip("'")
key = key or os.environ.get('CENSUS_API_KEY')
if not key:
    raise SystemExit(f'No Census API key found. Expected it in {env_file}')

# 2. What to download
VARS = 'NAME,B19013_001E,B01003_001E,B08201_001E,B08201_002E'
BASE = 'https://api.census.gov/data/2022/acs/acs5'

# 3. Download block groups for Denver, Adams and Arapahoe counties
frames = []
for county in ('031', '001', '005'):
    params = {
        'get': VARS,
        'for': 'block group:*',
        'in': ['state:08', f'county:{county}', 'tract:*'],
        'key': key,
    }
    r = requests.get(BASE, params=params, timeout=60)
    if r.status_code != 200 or not r.text.startswith('['):
        print('Census API problem for county', county)
        print('URL:', r.url.replace(key, 'KEY'))
        print('Reply:', r.text[:500])
        raise SystemExit(1)
    rows = r.json()
    frames.append(pd.DataFrame(rows[1:], columns=rows[0]))

# 4. Clean up and save
acs = pd.concat(frames, ignore_index=True)
acs['GEOID'] = acs['state'] + acs['county'] + acs['tract'] + acs['block group']
for col in ('B19013_001E', 'B01003_001E', 'B08201_001E', 'B08201_002E'):
    acs[col] = pd.to_numeric(acs[col], errors='coerce')
acs.loc[acs['B19013_001E'] < 0, 'B19013_001E'] = None   # -666666666 means no estimate
acs['pct_no_vehicle'] = acs['B08201_002E'] / acs['B08201_001E']

out = RAW / 'census' / 'acs_2022_bg.csv'
out.parent.mkdir(parents=True, exist_ok=True)
acs.to_csv(out, index=False)
print(len(acs), 'block groups saved to', out)