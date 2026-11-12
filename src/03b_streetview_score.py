import pandas as pd
from config import TAB

sheet = pd.read_csv(TAB / 'streetview_sheet.csv')
key = pd.read_csv(TAB / 'streetview_key.csv')
df = sheet.merge(key, on='check_id')
df['observed'] = df['observed'].astype(str).str.strip().str.lower()
usable = df[df['observed'].isin(['yes', 'no'])].copy()
usable['truth'] = usable['observed'] == 'yes'
print(len(df), 'rows,', len(usable), 'usable (yes or no),', (df['observed'] == 'unclear').sum(), 'unclear,',
      (~df['observed'].isin(['yes', 'no', 'unclear'])).sum(), 'not filled in')


def report(d, col, label):
    said_gap, said_sw = d[~d[col]], d[d[col]]
    return {
        'source': label, 'checked': len(d),
        'overall_agreement': (d[col] == d['truth']).mean(),
        # of the sides it called a gap, how many really have no sidewalk
        'gaps_confirmed': (~said_gap['truth']).mean() if len(said_gap) else None,
        'gaps_called': len(said_gap),
        # of the sides it called a sidewalk, how many really have one
        'sidewalks_confirmed': said_sw['truth'].mean() if len(said_sw) else None,
        'sidewalks_called': len(said_sw),
    }


rows = []
for name, d in [('All', usable)] + list(usable.groupby('city')):
    rows.append({'area': name, **report(d, 'has_pred', 'Model')})
    rows.append({'area': name, **report(d, 'has_drcog', 'DRCOG')})
table = pd.DataFrame(rows).round(2)
table.to_csv(TAB / 'streetview_results.csv', index=False)
print(table.to_string(index=False))

wrong = usable[usable['has_pred'] != usable['truth']]
wrong[['check_id', 'street', 'city', 'has_pred', 'has_drcog', 'observed', 'notes', 'street_view']].to_csv(
    TAB / 'streetview_model_errors.csv', index=False)
print(len(wrong), 'model errors listed in streetview_model_errors.csv')